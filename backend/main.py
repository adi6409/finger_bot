from fastapi import FastAPI, Depends, HTTPException, status, Request
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
from fastapi.responses import StreamingResponse

from backend.jsondb import get_collection, set_collection
import backend.auth as auth

# Assuming auth.py is in the same directory or accessible via python path
# We will import specific items as needed later

app = FastAPI(title="Finger Bot Backend")

# APScheduler instance
scheduler = AsyncIOScheduler()
scheduler.start()

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
    device_id = str(uuid4())
    device_in_db = {"id": device_id, "name": device.name, "owner": current_user["email"]}
    devices_db[device_id] = device_in_db
    set_devices_db(devices_db)
    return DevicePublic(id=device_id, name=device.name)

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

# --- TODO: Add Schedule Management Endpoints ---

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

# --- TCP Device Communication Logic ---

import asyncio
import socket
import struct
import json

# In-memory mapping: device_id -> TCP connection info
tcp_device_connections = {}  # device_id: (reader, writer)

# Start a background task to accept TCP device connections
@app.on_event("startup")
async def start_tcp_server():
    # On startup, load all schedules and add jobs
    schedules_db = get_schedules_db()
    for s in schedules_db.values():
        try:
            schedule_action_job(s["id"], s["device_id"], s["action"], s["time"], s["repeat"])
        except Exception as e:
            print(f"Failed to schedule job for {s['id']}: {e}")

    async def handle_device(reader, writer):
        # For demo: expect device to send its device_id as the first message
        try:
            # Read length-prefixed JSON
            length_bytes = await reader.readexactly(2)
            length = struct.unpack(">H", length_bytes)[0]
            data = await reader.readexactly(length)
            msg = json.loads(data.decode())
            device_id = msg.get("device_id")
            if not device_id:
                writer.close()
                await writer.wait_closed()
                return
            tcp_device_connections[device_id] = (reader, writer)
            print(f"Device {device_id} connected via TCP")
            while True:
                await asyncio.sleep(1)  # Keep connection alive
        except Exception as e:
            print("TCP device disconnected or error:", e)
        finally:
            # Remove device from mapping
            for dev_id, (r, w) in list(tcp_device_connections.items()):
                if w is writer:
                    del tcp_device_connections[dev_id]
                    break
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def tcp_server():
        server = await asyncio.start_server(handle_device, "0.0.0.0", 12345)
        print("TCP device server listening on 0.0.0.0:12345")
        async with server:
            await server.serve_forever()

    asyncio.create_task(tcp_server())

# Send an action to a device over TCP
async def send_tcp_action(device_id: str, action: str, params: dict, wait_for_response: bool):
    conn = tcp_device_connections.get(device_id)
    print("Got conn")
    if not conn:
        print("Not conn!")
        raise HTTPException(status_code=503, detail="Device not connected via TCP")
    reader, writer = conn
    reqid = str(uuid4())
    params["req_id"] = reqid
    msg = json.dumps({"action": action, "params": params})
    msg_bytes = msg.encode()
    length = struct.pack(">H", len(msg_bytes))
    try:
        writer.write(length + msg_bytes)
        await writer.drain()
        if wait_for_response:
            length_bytes = await reader.readexactly(2)
            length = struct.unpack(">H", length_bytes)[0]
            data = await reader.readexactly(length)
            msg = json.loads(data.decode())
            if msg.get("action") == f"{action}_result":
                params = msg.get("params")
                result = params.get("result")
                return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send action: {e}")

# API endpoint to send an action to a device
@app.post("/devices/{device_id}/action")
async def send_device_action(
    device_id: str,
    action: dict,  # expects {"action": "toggle_on"} etc.
    current_user: dict = Depends(auth.get_current_active_user)
):
    devices_db = get_devices_db()
    print("got devices")
    device = devices_db.get(device_id)
    print("Got device!")
    act = action.get("action", "")
    if not device or device["owner"] != current_user["email"]:
        print("Not device or not owner!")
        raise HTTPException(status_code=404, detail="Device not found")
    result = await send_tcp_action(device_id, action.get("action", ""), {}, True)
    print(f"result of {act}: {result}")
    return {"status": "done", "result": f"{result}"}

if __name__ == "__main__":
    import uvicorn
    # Note: Running directly like this is mainly for simple testing.
    # Use `uvicorn backend.main:app --reload` from the project root for development.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=3)
