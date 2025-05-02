from fastapi import FastAPI, Depends, HTTPException, status, Request
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import re
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from datetime import timedelta
from typing import Dict, Any, Optional # Import Dict and Any for type hinting
import qrcode
import io
import base64
from fastapi.responses import StreamingResponse, JSONResponse
import socket

from backend.jsondb import get_collection, set_collection
import backend.auth as auth

# Assuming auth.py is in the same directory or accessible via python path
# We will import specific items as needed later

# APScheduler instance
scheduler = AsyncIOScheduler()

# Use FastAPI lifespan to start/stop the scheduler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the scheduler when the app starts
    scheduler.start()
    yield
    # Shutdown the scheduler when the app stops
    scheduler.shutdown()

# Create FastAPI app with lifespan
app = FastAPI(title="Finger Bot Backend", lifespan=lifespan)

def parse_repeat_to_cron(repeat: str):
    # Very basic parser: "Daily" -> every day, "Wednesdays" -> day_of_week=wed, "Weekdays" -> mon-fri
    repeat = repeat.lower()
    if repeat == "daily":
        return CronTrigger()
    if repeat == "weekdays":
        return CronTrigger(day_of_week="mon-fri")
    m = re.match(r"(\w+)days", repeat)
    if m:
        day = m.group(1)[:3]
        return CronTrigger(day_of_week=day)
    return None  # fallback, run once

# Function to send action to device via WebSocket
async def send_tcp_action(device_id, action, metadata=None, retry=True):
    """
    Send an action to a device.
    This function is called by the scheduler for scheduled actions.
    
    Format matches what the MicroPython code expects:
    {
        "action": "press",
        "params": {...}  # Optional parameters
    }
    """
    try:
        # Get the device's WebSocket connection if available
        ws = device_ws_connections.get(device_id)
        if ws:
            # If device is connected via WebSocket, send the action directly
            # Format the message to match what the MicroPython code expects
            await ws.send_json({
                "action": action,
                "params": metadata or {}  # Use "params" instead of "metadata" to match MicroPython code
            })
            return {"status": "sent", "method": "websocket"}
        else:
            # Device not connected via WebSocket
            # Could implement HTTP fallback or other notification mechanism here
            print(f"Device {device_id} not connected for action: {action}")
            return {"status": "offline", "message": "Device not connected"}
    except Exception as e:
        print(f"Error sending action to device {device_id}: {e}")
        if retry:
            # Could implement retry logic here
            pass
        return {"status": "error", "message": str(e)}

def schedule_action_job(schedule_id, device_id, action, time_str, repeat):
    hour, minute = map(int, time_str.split(":"))
    trigger = parse_repeat_to_cron(repeat)
    if trigger is None:
        # fallback: run once at the next occurrence of the time
        from datetime import datetime, timedelta
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)
        scheduler.add_job(send_tcp_action, "date", run_date=run_time, args=[device_id, action, {"scheduled": True}, False], id=schedule_id, replace_existing=True)
    else:
        print(f"trigger is none, will schedule to {hour}:{minute}")
        scheduler.add_job(send_tcp_action, trigger, args=[device_id, action, {"scheduled": True}, False], id=schedule_id, replace_existing=True, hour=hour, minute=minute)

# Configure CORS
origins = [
    "http://localhost:5173",  # Default Vite dev server port
    "http://127.0.0.1:5173",
    "http://192.168.101.33:5173",
    "http://localhost:3000",  # Example for a different frontend
    "http://192.168.101.33:3000",
    "http://127.0.0.1:3000",
    "https://rested-annually-tiger.ngrok-free.app",
    "https://finger.astroianu.dev"
    # Add other origins if needed (e.g., your production frontend URL)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Finger Bot Backend"}

# --- Pydantic Models for User Data ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str # Frontend calls it password_needs_at_least_8_chars

class UserInDB(BaseModel):
    email: EmailStr
    hashed_password: str

class UserPublic(BaseModel):
    email: EmailStr

# --- JSON "DB" storage ---

def get_users_db():
    return get_collection("users")

def set_users_db(data):
    set_collection("users", data)

def get_devices_db():
    return get_collection("devices")

def set_devices_db(data):
    set_collection("devices", data)

def get_schedules_db():
    return get_collection("schedules")

def set_schedules_db(data):
    set_collection("schedules", data)
from uuid import uuid4

class DeviceCreate(BaseModel):
    name: str
    device_id: Optional[str] = None

class DeviceInDB(BaseModel):
    id: str
    name: str
    owner: str  # email of the user who registered the device

class DevicePublic(BaseModel):
    id: str
    name: str

class DeviceSetupInfo(BaseModel):
    ssid: str
    password: str
    server_host: str
    server_port: int = 12345

fake_devices_db: Dict[str, DeviceInDB] = {}
from datetime import time

from typing import Literal
class ScheduleCreate(BaseModel):
    device_id: str
    action: Literal["press"]
    time: str  # "HH:MM" format
    repeat: str  # e.g., "Wednesdays", "Daily", "Weekdays"

class ScheduleInDB(BaseModel):
    id: str
    device_id: str
    owner: str
    action: str
    time: str
    repeat: str

class SchedulePublic(BaseModel):
    id: str
    device_id: str
    action: str
    time: str
    repeat: str

fake_schedules_db: Dict[str, ScheduleInDB] = {}


# --- Authentication Endpoints ---

@app.post("/register", response_model=UserPublic)
async def register_user(user: UserCreate):
    users_db = get_users_db()
    if user.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    hashed_password = auth.get_password_hash(user.password)
    user_in_db = {"email": user.email, "hashed_password": hashed_password}
    users_db[user.email] = user_in_db
    set_users_db(users_db)
    return UserPublic(email=user.email)

@app.post("/token", response_model=auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    users_db = get_users_db()
    user = users_db.get(form_data.username)
    if not user or not auth.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Dependency override for auth
async def override_get_user_db():
    return get_users_db()

app.dependency_overrides[auth.get_user_db] = override_get_user_db

@app.get("/users/me", response_model=UserPublic)
async def read_users_me(current_user: dict = Depends(auth.get_current_active_user)):
    return UserPublic(email=current_user["email"])


# --- Device Management Endpoints ---

from fastapi import Security

@app.post("/devices", response_model=DevicePublic)
async def create_device(
    device: DeviceCreate,
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    
    # Use provided device_id (MAC address) or generate a new UUID
    device_id = device.device_id if device.device_id else str(uuid4())
    
    # Check if device_id already exists
    for existing_device in devices_db.values():
        if existing_device.get("id") == device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device ID already registered",
            )
    
    device_in_db = {"id": device_id, "name": device.name, "owner": current_user["email"]}
    devices_db[device_id] = device_in_db
    set_devices_db(devices_db)
    return DevicePublic(id=device_id, name=device.name)

# --- Device Setup Endpoints ---

@app.get("/devices/qr/{device_mac}")
async def generate_device_qr(
    device_mac: str,
    request: Request,
    current_user: dict = Depends(auth.get_current_active_user)
):
    """Generate a QR code for device setup"""
    # Get the base URL from the request
    base_url = str(request.base_url)
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    
    # Create the setup URL that will be encoded in the QR code
    setup_url = f"{base_url}/device-setup?mac={device_mac}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(setup_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to bytes buffer
    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)
    
    # Return QR code image
    return StreamingResponse(buffer, media_type="image/png")

@app.get("/devices/qr/{device_mac}/base64")
async def generate_device_qr_base64(
    device_mac: str,
    request: Request,
    current_user: dict = Depends(auth.get_current_active_user)
):
    """Generate a QR code for device setup and return as base64"""
    # Get the base URL from the request
    base_url = str(request.base_url)
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    
    # Create the setup URL that will be encoded in the QR code
    setup_url = f"{base_url}/device-setup?mac={device_mac}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(setup_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to bytes buffer
    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)
    
    # Convert to base64
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # Return base64 encoded QR code
    return {"qr_code": qr_base64}

@app.get("/server-info")
async def get_server_info(
    request: Request,
    current_user: dict = Depends(auth.get_current_active_user)
):
    """Get server information for device setup"""
    # Check if SERVER_HOST is set in app state (passed from server.py)
    if hasattr(app.state, 'server_host'):
        # Parse the SERVER_HOST value which is in format "hostname" or "hostname:port"
        server_host = app.state.server_host
        if hasattr(app.state, 'server_port'):
            host = server_host
            port = app.state.server_port
        elif ':' in server_host:
            host, port_str = server_host.split(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 12345  # Default port if parsing fails
        else:
            host = server_host
            port = 12345  # Default port if not specified
            
        return {
            "host": host,
            "port": port
        }
    
    # Fallback to original behavior if server_host is not set
    # Use the address the client used to reach the backend (e.g., ngrok domain)
    base_url = str(request.base_url)
    # Remove trailing slash if present
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    # Extract host (and port if present)
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    host = parsed.hostname
    port = parsed.port

    # Check if we're running as part of the unified server
    from fastapi import FastAPI
    import inspect

    frame = inspect.currentframe()
    while frame:
        if 'app' in frame.f_locals and isinstance(frame.f_locals['app'], FastAPI) and hasattr(frame.f_locals['app'], 'state') and hasattr(frame.f_locals['app'].state, 'tcp_port'):
            return {
                "host": host,
                "port": frame.f_locals['app'].state.tcp_port
            }
        frame = frame.f_back

    return {
        "host": host,
        "port": port if port else 12345  # Use port from URL if present, else default
    }

@app.get("/devices", response_model=list[DevicePublic])
async def list_devices(
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    return [
        DevicePublic(id=d["id"], name=d["name"])
        for d in devices_db.values()
        if d["owner"] == current_user["email"]
    ]

@app.get("/devices/{device_id}", response_model=DevicePublic)
async def get_device(
    device_id: str,
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    device = devices_db.get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    return DevicePublic(id=device["id"], name=device["name"])

@app.put("/devices/{device_id}", response_model=DevicePublic)
async def update_device(
    device_id: str,
    device_update: DeviceCreate,
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    device = devices_db.get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    device["name"] = device_update.name
    devices_db[device_id] = device
    set_devices_db(devices_db)
    return DevicePublic(id=device["id"], name=device["name"])

@app.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: str,
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    device = devices_db.get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    del devices_db[device_id]
    set_devices_db(devices_db)
    return

# --- Schedule Management Endpoints ---

@app.post("/schedules", response_model=SchedulePublic)
async def create_schedule(
    schedule: ScheduleCreate,
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    schedules_db = get_schedules_db()
    device = devices_db.get(schedule.device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    schedule_id = str(uuid4())
    schedule_in_db = {
        "id": schedule_id,
        "device_id": schedule.device_id,
        "owner": current_user["email"],
        "action": schedule.action,
        "time": schedule.time,
        "repeat": schedule.repeat,
    }
    schedules_db[schedule_id] = schedule_in_db
    set_schedules_db(schedules_db)
    # Schedule the job
    schedule_action_job(schedule_id, schedule.device_id, schedule.action, schedule.time, schedule.repeat)
    return SchedulePublic(
        id=schedule_id,
        device_id=schedule.device_id,
        action=schedule.action,
        time=schedule.time,
        repeat=schedule.repeat,
    )

@app.get("/schedules", response_model=list[SchedulePublic])
async def list_schedules(
    current_user: dict = Depends(auth.get_current_active_user)
):
    schedules_db = get_schedules_db()
    return [
        SchedulePublic(
            id=s["id"],
            device_id=s["device_id"],
            action=s["action"],
            time=s["time"],
            repeat=s["repeat"],
        )
        for s in schedules_db.values()
        if s["owner"] == current_user["email"]
    ]

@app.get("/schedules/{schedule_id}", response_model=SchedulePublic)
async def get_schedule(
    schedule_id: str,
    current_user: dict = Depends(auth.get_current_active_user)
):
    schedules_db = get_schedules_db()
    schedule = schedules_db.get(schedule_id)
    if not schedule or schedule["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return SchedulePublic(
        id=schedule["id"],
        device_id=schedule["device_id"],
        action=schedule["action"],
        time=schedule["time"],
        repeat=schedule["repeat"],
    )

@app.put("/schedules/{schedule_id}", response_model=SchedulePublic)
async def update_schedule(
    schedule_id: str,
    schedule_update: ScheduleCreate,
    current_user: dict = Depends(auth.get_current_active_user)
):
    schedules_db = get_schedules_db()
    devices_db = get_devices_db()
    schedule = schedules_db.get(schedule_id)
    if not schedule or schedule["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    device = devices_db.get(schedule_update.device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    schedule["device_id"] = schedule_update.device_id
    schedule["action"] = schedule_update.action
    schedule["time"] = schedule_update.time
    schedule["repeat"] = schedule_update.repeat
    schedules_db[schedule_id] = schedule
    set_schedules_db(schedules_db)
    # Reschedule the job
    schedule_action_job(schedule_id, schedule_update.device_id, schedule_update.action, schedule_update.time, schedule_update.repeat)
    return SchedulePublic(
        id=schedule["id"],
        device_id=schedule["device_id"],
        action=schedule["action"],
        time=schedule["time"],
        repeat=schedule["repeat"],
    )

@app.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    current_user: dict = Depends(auth.get_current_active_user)
):
    schedules_db = get_schedules_db()
    schedule = schedules_db.get(schedule_id)
    if not schedule or schedule["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    del schedules_db[schedule_id]
    set_schedules_db(schedules_db)
    # Remove the job from the scheduler
    try:
        scheduler.remove_job(schedule_id)
    except Exception:
        pass
    return

# --- Device HTTP & WebSocket Communication Logic ---

from fastapi import Body, WebSocket, WebSocketDisconnect
from typing import Dict

# In-memory mapping: device_id -> last known status
device_status = {}

# In-memory mapping: device_id -> WebSocket connection
device_ws_connections: Dict[str, WebSocket] = {}

@app.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(
    device_id: str,
    status: dict = Body(...),
):
    """
    Endpoint for ESP device to send heartbeat/status updates.
    """
    device_status[device_id] = status
    return {"status": "ok"}

@app.post("/devices/{device_id}/action-result")
async def device_action_result(
    device_id: str,
    result: dict = Body(...),
):
    """
    Endpoint for ESP device to send action results.
    """
    # Store or process the result as needed
    return {"status": "ok"}

@app.websocket("/ws/device/{device_id}")
async def device_ws(device_id: str, websocket: WebSocket):
    """
    WebSocket endpoint for ESP device to receive actions in real time.
    """
    await websocket.accept()
    device_ws_connections[device_id] = websocket
    try:
        while True:
            # Wait for any message from device (could be a ping or status)
            data = await websocket.receive_text()
            # Optionally process incoming data from device
    except WebSocketDisconnect:
        pass
    finally:
        # Remove connection on disconnect
        if device_id in device_ws_connections:
            del device_ws_connections[device_id]

@app.post("/devices/{device_id}/send-action")
async def send_action_to_device(
    device_id: str,
    action: dict = Body(...),
):
    """
    Endpoint for backend/frontend to send an action to a device in real time.
    
    Expected input format:
    {
        "action": "press",
        "params": {...}  # Optional parameters
    }
    """
    ws = device_ws_connections.get(device_id)
    if ws:
        # Ensure the message format matches what the MicroPython code expects
        # The action dict should already have "action" and optionally "params" fields
        await ws.send_json(action)
        return {"status": "sent"}
    else:
        return {"status": "offline", "message": "Device not connected via WebSocket"}

# The rest of the API (frontend/backend) can now interact with devices via these HTTP and WebSocket endpoints.

if __name__ == "__main__":
    import uvicorn
    # Note: Running directly like this is mainly for simple testing.
    # Use `uvicorn backend.main:app --reload` from the project root for development.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=3)
