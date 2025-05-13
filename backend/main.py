"""
FastAPI backend for Finger Bot application.
Provides API endpoints for user authentication, device management, and scheduling.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import timedelta, datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4
import re
from backend.jsondb import get_collection, set_collection
import backend.auth as auth
from backend.models import (
    UserCreate, UserInDB, UserPublic,
    DeviceCreate, DeviceInDB, DevicePublic, DeviceSetupInfo,
    ScheduleCreate, ScheduleInDB, SchedulePublic
)

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
app = FastAPI(
    title="Finger Bot Backend",
    description="API for Finger Bot device management and scheduling",
    version="1.0.0",
    lifespan=lifespan
)

def parse_repeat_to_cron(repeat: str) -> Optional[CronTrigger]:
    """
    Convert a human-readable repeat pattern to a CronTrigger.
    
    Args:
        repeat: String like "Daily", "Weekdays", "Wednesdays", or abbreviated day names like "mon", "tue"
        
    Returns:
        CronTrigger object or None if pattern not recognized
    """
    repeat = repeat.lower()
    if repeat == "daily":
        return CronTrigger()
    if repeat == "weekdays":
        return CronTrigger(day_of_week="mon-fri")
    
    # Handle abbreviated day names (mon, tue, wed, etc.)
    day_abbrevs = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    if repeat in day_abbrevs:
        return CronTrigger(day_of_week=repeat)
    
    # Handle comma-separated day abbreviations (mon,tue,wed)
    if "," in repeat:
        days = [day.strip() for day in repeat.split(",")]
        if all(day in day_abbrevs for day in days):
            return CronTrigger(day_of_week=",".join(days))
    
    # Original pattern matching for "mondays", "tuesdays", etc.
    m = re.match(r"(\w+)days", repeat)
    if m:
        day = m.group(1)[:3]
        return CronTrigger(day_of_week=day)
    
    return None  # fallback, run once

async def send_tcp_action(device_id: str, action: str, metadata: Optional[Dict[str, Any]] = None, retry: bool = True) -> Dict[str, Any]:
    """
    Send an action to a device via WebSocket.
    This function is called by the scheduler for scheduled actions.
    
    Args:
        device_id: The ID of the device to send the action to
        action: The action to perform (e.g., "press")
        metadata: Optional parameters for the action
        retry: Whether to retry on failure
        
    Returns:
        Dict with status information
    
    Format matches what the MicroPython code expects:
    {
        "action": "press",
        "params": {...}  # Optional parameters
    }
    """
    print(f"Sending action to device {device_id}: {action} with metadata: {metadata}")
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
            print(f"Device {device_id} not connected for action: {action}")
            return {"status": "offline", "message": "Device not connected"}
    except Exception as e:
        print(f"Error sending action to device {device_id}: {e}")
        if retry:
            # Could implement retry logic here
            pass
        return {"status": "error", "message": str(e)}

def schedule_action_job(schedule_id: str, device_id: str, action: str, time_str: str, repeat: str) -> None:
    hour, minute = map(int, time_str.split(":"))
    trigger = parse_repeat_to_cron(repeat)

    print(f"Scheduling job {schedule_id} for device {device_id} at {time_str} with repeat: {repeat}")
    
    if trigger is None:
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)
        scheduler.add_job(
            send_tcp_action,
            "date",
            run_date=run_time,
            args=[device_id, action, {"scheduled": True}, False],
            id=schedule_id,
            replace_existing=True
        )
    else:
        # FIX: set hour/minute directly in the CronTrigger
        trigger = CronTrigger(day_of_week=trigger.fields[4].expressions[0], hour=hour, minute=minute)
        scheduler.add_job(
            send_tcp_action,
            trigger=trigger,
            args=[device_id, action, {"scheduled": True}, False],
            id=schedule_id,
            replace_existing=True
        )
    
    print(f"Jobs: {scheduler.get_jobs()}")


# Configure CORS
origins = [
    # Development servers
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # Next.js dev server
    "http://127.0.0.1:3000",
    
    # Local network testing
    "http://192.168.101.33:5173",
    "http://192.168.101.33:3000",
    
    # Production domains
    "https://rested-annually-tiger.ngrok-free.app",
    "https://finger.astroianu.dev"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- JSON "DB" storage functions ---

def get_users_db() -> Dict[str, Any]:
    """Get the users collection from the JSON database."""
    return get_collection("users")

def set_users_db(data: Dict[str, Any]) -> None:
    """Save the users collection to the JSON database."""
    set_collection("users", data)

def get_devices_db() -> Dict[str, Any]:
    """Get the devices collection from the JSON database."""
    return get_collection("devices")

def set_devices_db(data: Dict[str, Any]) -> None:
    """Save the devices collection to the JSON database."""
    set_collection("devices", data)

def get_schedules_db() -> Dict[str, Any]:
    """Get the schedules collection from the JSON database."""
    return get_collection("schedules")

def set_schedules_db(data: Dict[str, Any]) -> None:
    """Save the schedules collection to the JSON database."""
    set_collection("schedules", data)

# --- API Routes ---

@app.get("/")
async def read_root():
    """Root endpoint that returns a welcome message."""
    return {"message": "Welcome to the Finger Bot Backend"}


# --- Authentication Endpoints ---

@app.post("/register", response_model=UserPublic)
async def register_user(user: UserCreate):
    """
    Register a new user with email and password.
    
    Args:
        user: User creation data with email and password
        
    Returns:
        The created user's public information
        
    Raises:
        HTTPException: If the email is already registered
    """
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
    """
    Authenticate a user and return an access token.
    
    Args:
        form_data: OAuth2 form with username (email) and password
        
    Returns:
        Access token for the authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
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
    """Override the auth module's get_user_db function to use our JSON DB."""
    return get_users_db()

app.dependency_overrides[auth.get_user_db] = override_get_user_db

@app.get("/users/me", response_model=UserPublic)
async def read_users_me(current_user: dict = Depends(auth.get_current_active_user)):
    """
    Get the current authenticated user's information.
    
    Args:
        current_user: The authenticated user from the token
        
    Returns:
        The user's public information
    """
    return UserPublic(email=current_user["email"])


# --- Device Management Endpoints ---

@app.post("/devices", response_model=DevicePublic)
async def create_device(
    device: DeviceCreate,
    current_user: dict = Depends(auth.get_current_active_user)
):
    """
    Register a new device for the authenticated user.
    
    Args:
        device: Device creation data with name and optional device_id
        current_user: The authenticated user
        
    Returns:
        The created device's public information
        
    Raises:
        HTTPException: If the device ID is already registered
    """
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
    """
    List all devices belonging to the authenticated user.
    
    Args:
        current_user: The authenticated user
        
    Returns:
        List of devices owned by the user
    """
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
    """
    Get a specific device by ID.
    
    Args:
        device_id: The ID of the device to retrieve
        current_user: The authenticated user
        
    Returns:
        The device's public information
        
    Raises:
        HTTPException: If the device is not found or doesn't belong to the user
    """
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
    """
    Update a device's information.
    
    Args:
        device_id: The ID of the device to update
        device_update: The updated device data
        current_user: The authenticated user
        
    Returns:
        The updated device's public information
        
    Raises:
        HTTPException: If the device is not found or doesn't belong to the user
    """
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
    """
    Delete a device.
    
    Args:
        device_id: The ID of the device to delete
        current_user: The authenticated user
        
    Returns:
        No content on successful deletion
        
    Raises:
        HTTPException: If the device is not found or doesn't belong to the user
    """
    devices_db = get_devices_db()
    device = devices_db.get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    del devices_db[device_id]
    set_devices_db(devices_db)
    return


@app.get("/time")
async def get_time():
    """
    Get the current server time.
    
    Returns:
        The current server time in ISO format
    """
    return {"time": datetime.now().isoformat()}

# --- Schedule Management Endpoints ---

@app.post("/schedules", response_model=SchedulePublic)
async def create_schedule(
    schedule: ScheduleCreate,
    current_user: dict = Depends(auth.get_current_active_user)
):
    """
    Create a new schedule for a device.
    
    Args:
        schedule: Schedule creation data with device_id, action, time, and repeat pattern
        current_user: The authenticated user
        
    Returns:
        The created schedule's public information
        
    Raises:
        HTTPException: If the device is not found or doesn't belong to the user
    """
    devices_db = get_devices_db()
    schedules_db = get_schedules_db()
    device = devices_db.get(schedule.device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    schedule_id = str(uuid4())
    # Normalize repeat to string
    if isinstance(schedule.repeat, list):
        if len(schedule.repeat) == 0:
            repeat_str = "Once"
        else:
            repeat_str = ",".join(schedule.repeat)
    else:
        repeat_str = schedule.repeat
    schedule_in_db = {
        "id": schedule_id,
        "device_id": schedule.device_id,
        "owner": current_user["email"],
        "action": schedule.action,
        "time": schedule.time,
        "repeat": repeat_str,
    }
    schedules_db[schedule_id] = schedule_in_db
    set_schedules_db(schedules_db)
    print(f"Created schedule: {schedule_in_db}")
    # Schedule the job
    schedule_action_job(schedule_id, schedule.device_id, schedule.action, schedule.time, repeat_str)
    return SchedulePublic(
        id=schedule_id,
        device_id=schedule.device_id,
        action=schedule.action,
        time=schedule.time,
        repeat=repeat_str,
    )

@app.get("/schedules", response_model=list[SchedulePublic])
async def list_schedules(
    current_user: dict = Depends(auth.get_current_active_user)
):
    """
    List all schedules belonging to the authenticated user.
    
    Args:
        current_user: The authenticated user
        
    Returns:
        List of schedules owned by the user
    """
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
    """
    Get a specific schedule by ID.
    
    Args:
        schedule_id: The ID of the schedule to retrieve
        current_user: The authenticated user
        
    Returns:
        The schedule's public information
        
    Raises:
        HTTPException: If the schedule is not found or doesn't belong to the user
    """
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
    """
    Update a schedule's information.
    
    Args:
        schedule_id: The ID of the schedule to update
        schedule_update: The updated schedule data
        current_user: The authenticated user
        
    Returns:
        The updated schedule's public information
        
    Raises:
        HTTPException: If the schedule or device is not found or doesn't belong to the user
    """
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
    # Normalize repeat to string
    if isinstance(schedule_update.repeat, list):
        if len(schedule_update.repeat) == 0:
            repeat_str = "Once"
        else:
            repeat_str = ",".join(schedule_update.repeat)
    else:
        repeat_str = schedule_update.repeat
    schedule["repeat"] = repeat_str
    schedules_db[schedule_id] = schedule
    set_schedules_db(schedules_db)
    # Reschedule the job
    schedule_action_job(schedule_id, schedule_update.device_id, schedule_update.action, schedule_update.time, repeat_str)
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
    """
    Delete a schedule.
    
    Args:
        schedule_id: The ID of the schedule to delete
        current_user: The authenticated user
        
    Returns:
        No content on successful deletion
        
    Raises:
        HTTPException: If the schedule is not found or doesn't belong to the user
    """
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

# In-memory mappings
device_status: Dict[str, Dict[str, Any]] = {}  # device_id -> last known status
device_ws_connections: Dict[str, WebSocket] = {}  # device_id -> WebSocket connection

@app.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(
    device_id: str,
    status: dict = Body(...),
):
    """
    Endpoint for ESP device to send heartbeat/status updates.
    """
    # TODO: Move heartbeat logic from device to wss
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
    # TODO: Handle action results
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
            # TODO: Handle incoming messages from device
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

if __name__ == "__main__":
    import uvicorn
    # Note: Running directly like this is mainly for simple testing.
    # Use `python server.py` to run the unified server.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=3)
