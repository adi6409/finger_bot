import logging
import re
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

import backend.auth as auth
from backend.jsondb import get_collection, set_collection
from backend.models import (
    UserCreate, UserInDB, UserPublic,
    DeviceCreate, DeviceInDB, DevicePublic, DeviceSetupInfo,
    ScheduleCreate, ScheduleInDB, SchedulePublic
)

# ——————————————————————————————
# Scheduler & Logger setup
# ——————————————————————————————
local_tz = timezone("Asia/Jerusalem")
scheduler = AsyncIOScheduler(timezone=local_tz)
scheduler.start()  # start immediately so jobs won't be added "tentatively"
logger = logging.getLogger("fingerbot")
logging.basicConfig(level=logging.INFO)

# In-memory mappings
device_status: Dict[str, Dict[str, Any]] = {}            # device_id -> last known status
device_ws_connections: Dict[str, WebSocket] = {}         # device_id -> WebSocket connection

# ——————————————————————————————
# FastAPI app with shutdown hook
# ——————————————————————————————
app = FastAPI(
    title="Finger Bot Backend",
    description="API for Finger Bot device management and scheduling",
    version="1.0.0",
)

@app.on_event("shutdown")
async def stop_scheduler():
    logger.info("Shutting down APScheduler…")
    scheduler.shutdown()

# ——————————————————————————————
# Core functions
# ——————————————————————————————
async def send_tcp_action(device_id: str, action: str, metadata: Optional[Dict[str, Any]] = None, retry: bool = True) -> Dict[str, Any]:
    """
    Called by APScheduler to send an action to a device via WebSocket.
    """
    logger.info(f"[scheduled] Sending action '{action}' to device {device_id}")
    ws = device_ws_connections.get(device_id)
    if ws:
        await ws.send_json({
            "action": action,
            "params": metadata or {}
        })
        return {"status": "sent", "method": "websocket"}
    else:
        logger.warning(f"[scheduled] Device {device_id} not connected")
        return {"status": "offline", "message": "Device not connected"}

def schedule_action_job(schedule_id: str, device_id: str, action: str, time_str: str, repeat: str) -> None:
    """
    Schedule a job in APScheduler for either a one-off or recurring action.
    """
    hour, minute = map(int, time_str.split(":"))
    now = datetime.now(local_tz)

    if not repeat or repeat.lower() == "once":
        # One-off job
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)
        scheduler.add_job(
            send_tcp_action,
            "date",
            run_date=run_time,
            args=[device_id, action, {"scheduled": True}, False],
            id=schedule_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled one-off job {schedule_id} at {run_time.isoformat()}")
    else:
        # Recurring job
        cron_args = {"hour": hour, "minute": minute, "timezone": local_tz}
        rpt = repeat.lower()
        if rpt == "daily":
            pass
        elif rpt == "weekdays":
            cron_args["day_of_week"] = "mon-fri"
        else:
            cron_args["day_of_week"] = rpt  # e.g. "mon", "tue,wed", etc.

        scheduler.add_job(
            send_tcp_action,
            "cron",
            args=[device_id, action, {"scheduled": True}, False],
            id=schedule_id,
            replace_existing=True,
            **cron_args
        )
        logger.info(f"Scheduled recurring job {schedule_id} ({repeat}) at {hour:02d}:{minute:02d}")

    logger.debug(f"Current jobs: {scheduler.get_jobs()}")

# ——————————————————————————————
# JSON DB helpers
# ——————————————————————————————
def get_users_db() -> Dict[str, Any]:
    return get_collection("users")

def set_users_db(data: Dict[str, Any]) -> None:
    set_collection("users", data)

def get_devices_db() -> Dict[str, Any]:
    return get_collection("devices")

def set_devices_db(data: Dict[str, Any]) -> None:
    set_collection("devices", data)

def get_schedules_db() -> Dict[str, Any]:
    return get_collection("schedules")

def set_schedules_db(data: Dict[str, Any]) -> None:
    set_collection("schedules", data)

# ——————————————————————————————
# Configure CORS
# ——————————————————————————————
origins = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://192.168.101.33:5173", "http://192.168.101.33:3000",
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

# ——————————————————————————————
# Authentication Endpoints
# ——————————————————————————————
@app.post("/register", response_model=UserPublic)
async def register_user(user: UserCreate):
    users_db = get_users_db()
    if user.email in users_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed = auth.get_password_hash(user.password)
    users_db[user.email] = {"email": user.email, "hashed_password": hashed}
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
            headers={"WWW-Authenticate": "Bearer"}
        )
    expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = auth.create_access_token(data={"sub": user["email"]}, expires_delta=expires)
    return {"access_token": token, "token_type": "bearer"}

async def override_get_user_db():
    return get_users_db()

app.dependency_overrides[auth.get_user_db] = override_get_user_db

@app.get("/users/me", response_model=UserPublic)
async def read_users_me(current_user: dict = Depends(auth.get_current_active_user)):
    return UserPublic(email=current_user["email"])

# ——————————————————————————————
# Device Management Endpoints
# ——————————————————————————————
@app.post("/devices", response_model=DevicePublic)
async def create_device(device: DeviceCreate, current_user: dict = Depends(auth.get_current_active_user)):
    devices_db = get_devices_db()
    device_id = device.device_id or str(uuid4())
    if any(d.get("id") == device_id for d in devices_db.values()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device ID already registered")
    devices_db[device_id] = {"id": device_id, "name": device.name, "owner": current_user["email"]}
    set_devices_db(devices_db)
    return DevicePublic(id=device_id, name=device.name)

@app.get("/devices", response_model=list[DevicePublic])
async def list_devices(current_user: dict = Depends(auth.get_current_active_user)):
    return [
        DevicePublic(id=d["id"], name=d["name"])
        for d in get_devices_db().values()
        if d["owner"] == current_user["email"]
    ]

@app.get("/devices/{device_id}", response_model=DevicePublic)
async def get_device(device_id: str, current_user: dict = Depends(auth.get_current_active_user)):
    device = get_devices_db().get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    return DevicePublic(id=device["id"], name=device["name"])

@app.put("/devices/{device_id}", response_model=DevicePublic)
async def update_device(device_id: str, device_update: DeviceCreate, current_user: dict = Depends(auth.get_current_active_user)):
    devices_db = get_devices_db()
    device = devices_db.get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    device["name"] = device_update.name
    devices_db[device_id] = device
    set_devices_db(devices_db)
    return DevicePublic(id=device_id, name=device["name"])

@app.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: str, current_user: dict = Depends(auth.get_current_active_user)):
    devices_db = get_devices_db()
    device = devices_db.get(device_id)
    if not device or device["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    del devices_db[device_id]
    set_devices_db(devices_db)

# ——————————————————————————————
# Server Info Endpoint
# ——————————————————————————————
@app.get("/server-info")
async def get_server_info(request: Request, current_user: dict = Depends(auth.get_current_active_user)):
    if hasattr(app.state, 'server_host'):
        host = app.state.server_host
        port = getattr(app.state, 'server_port', 12345)
        return {"host": host, "port": port}
    base_url = str(request.base_url).rstrip("/")
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    return {"host": parsed.hostname, "port": parsed.port or 12345}

# ——————————————————————————————
# Time Endpoint
# ——————————————————————————————
@app.get("/time")
async def get_time():
    return {"time": datetime.now(local_tz).isoformat()}

# ——————————————————————————————
# Schedule Management Endpoints
# ——————————————————————————————
@app.post("/schedules", response_model=SchedulePublic)
async def create_schedule(schedule: ScheduleCreate, current_user: dict = Depends(auth.get_current_active_user)):
    devices_db = get_devices_db()
    if schedule.device_id not in devices_db or devices_db[schedule.device_id]["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")

    schedules_db = get_schedules_db()
    schedule_id = str(uuid4())
    repeat_str = ",".join(schedule.repeat) if isinstance(schedule.repeat, list) and schedule.repeat else (schedule.repeat or "Once")

    schedules_db[schedule_id] = {
        "id": schedule_id,
        "device_id": schedule.device_id,
        "owner": current_user["email"],
        "action": schedule.action,
        "time": schedule.time,
        "repeat": repeat_str,
    }
    set_schedules_db(schedules_db)

    logger.info(f"Created schedule: {schedules_db[schedule_id]}")
    schedule_action_job(schedule_id, schedule.device_id, schedule.action, schedule.time, repeat_str)
    return SchedulePublic(id=schedule_id, device_id=schedule.device_id, action=schedule.action, time=schedule.time, repeat=repeat_str)

@app.get("/schedules", response_model=list[SchedulePublic])
async def list_schedules(current_user: dict = Depends(auth.get_current_active_user)):
    return [
        SchedulePublic(**s)
        for s in get_schedules_db().values()
        if s["owner"] == current_user["email"]
    ]

@app.get("/schedules/{schedule_id}", response_model=SchedulePublic)
async def get_schedule(schedule_id: str, current_user: dict = Depends(auth.get_current_active_user)):
    s = get_schedules_db().get(schedule_id)
    if not s or s["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return SchedulePublic(**s)

@app.put("/schedules/{schedule_id}", response_model=SchedulePublic)
async def update_schedule(schedule_id: str, schedule_update: ScheduleCreate, current_user: dict = Depends(auth.get_current_active_user)):
    schedules_db = get_schedules_db()
    s = schedules_db.get(schedule_id)
    devices_db = get_devices_db()
    if not s or s["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule_update.device_id not in devices_db or devices_db[schedule_update.device_id]["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")

    repeat_str = ",".join(schedule_update.repeat) if isinstance(schedule_update.repeat, list) and schedule_update.repeat else (schedule_update.repeat or "Once")
    s.update({
        "device_id": schedule_update.device_id,
        "action": schedule_update.action,
        "time": schedule_update.time,
        "repeat": repeat_str
    })
    set_schedules_db(schedules_db)
    schedule_action_job(schedule_id, schedule_update.device_id, schedule_update.action, schedule_update.time, repeat_str)
    return SchedulePublic(**s)

@app.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str, current_user: dict = Depends(auth.get_current_active_user)):
    schedules_db = get_schedules_db()
    s = schedules_db.get(schedule_id)
    if not s or s["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    del schedules_db[schedule_id]
    set_schedules_db(schedules_db)
    try:
        scheduler.remove_job(schedule_id)
    except Exception:
        pass

# ——————————————————————————————
# Device HTTP & WebSocket Communication
# ——————————————————————————————
@app.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, status: dict = Body(...)):
    device_status[device_id] = status
    return {"status": "ok"}

@app.post("/devices/{device_id}/action-result")
async def device_action_result(device_id: str, result: dict = Body(...)):
    return {"status": "ok"}

@app.websocket("/ws/device/{device_id}")
async def device_ws(device_id: str, websocket: WebSocket):
    await websocket.accept()
    device_ws_connections[device_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        device_ws_connections.pop(device_id, None)

@app.post("/devices/{device_id}/send-action")
async def send_action_to_device(device_id: str, action: dict = Body(...)):
    ws = device_ws_connections.get(device_id)
    if ws:
        await ws.send_json(action)
        return {"status": "sent"}
    else:
        return {"status": "offline", "message": "Device not connected via WebSocket"}

# ——————————————————————————————
# Entry point
# ——————————————————————————————
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
