import logging
import re
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

import backend.auth as auth
from backend.jsondb import get_collection, set_collection
from backend.models import (
    UserCreate, UserPublic,
    DeviceCreate, DevicePublic,
    ScheduleCreate, SchedulePublic
)

# ——————————————————————————————
# Scheduler & Logger setup
# ——————————————————————————————
local_tz = timezone("Asia/Jerusalem")
scheduler = AsyncIOScheduler(timezone=local_tz)
logger = logging.getLogger("fingerbot")
logging.basicConfig(level=logging.INFO)

# In-memory mappings
device_status: Dict[str, Dict[str, Any]] = {}
device_ws_connections: Dict[str, WebSocket] = {}

# ——————————————————————————————
# FastAPI app and scheduler lifecycle
# ——————————————————————————————
app = FastAPI(
    title="Finger Bot Backend",
    description="API for Finger Bot device management and scheduling",
    version="1.0.0",
)

@app.on_event("startup")
async def start_scheduler():
    logger.info("Starting APScheduler…")
    scheduler.start()

@app.on_event("shutdown")
async def stop_scheduler():
    logger.info("Shutting down APScheduler…")
    scheduler.shutdown()

# ——————————————————————————————
# Core scheduled task
# ——————————————————————————————
async def send_tcp_action(
    device_id: str,
    action: str,
    metadata: Optional[Dict[str, Any]] = None,
    retry: bool = True
) -> Dict[str, Any]:
    logger.info(f"[scheduled] Sending action '{action}' to device {device_id}")
    ws = device_ws_connections.get(device_id)
    if ws:
        await ws.send_json({"action": action, "params": metadata or {}})
        return {"status": "sent", "method": "websocket"}
    else:
        logger.warning(f"[scheduled] Device {device_id} not connected")
        return {"status": "offline", "message": "Device not connected"}

def schedule_action_job(
    schedule_id: str,
    device_id: str,
    action: str,
    time_str: str,
    repeat: str
) -> None:
    hour, minute = map(int, time_str.split(":"))
    now = datetime.now(local_tz)

    if not repeat or repeat.lower() == "once":
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
        cron_args = {"hour": hour, "minute": minute, "timezone": local_tz}
        rpt = repeat.lower()
        if rpt == "daily":
            pass
        elif rpt == "weekdays":
            cron_args["day_of_week"] = "mon-fri"
        else:
            cron_args["day_of_week"] = rpt
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
# JSON-DB helpers
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
# CORS configuration
# ——————————————————————————————
origins = [
    "http://localhost:5173","http://127.0.0.1:5173",
    "http://localhost:3000","http://127.0.0.1:3000",
    "http://192.168.101.33:5173","http://192.168.101.33:3000",
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
# Authentication endpoints
# ——————————————————————————————
@app.post("/register", response_model=UserPublic)
async def register_user(user: UserCreate):
    users = get_users_db()
    if user.email in users:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed = auth.get_password_hash(user.password)
    users[user.email] = {"email": user.email, "hashed_password": hashed}
    set_users_db(users)
    return UserPublic(email=user.email)

@app.post("/token", response_model=auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    users = get_users_db()
    u = users.get(form_data.username)
    if not u or not auth.verify_password(form_data.password, u["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = auth.create_access_token(data={"sub": u["email"]}, expires_delta=expires)
    return {"access_token": token, "token_type": "bearer"}

app.dependency_overrides[auth.get_user_db] = lambda: get_users_db()

@app.get("/users/me", response_model=UserPublic)
async def read_users_me(current_user: dict = Depends(auth.get_current_active_user)):
    return UserPublic(email=current_user["email"])

# ——————————————————————————————
# Device endpoints
# ——————————————————————————————
@app.post("/devices", response_model=DevicePublic)
async def create_device(device: DeviceCreate, current_user: dict = Depends(auth.get_current_active_user)):
    devices = get_devices_db()
    device_id = device.device_id or str(uuid4())
    if any(d.get("id") == device_id for d in devices.values()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device ID already registered")
    devices[device_id] = {"id": device_id, "name": device.name, "owner": current_user["email"]}
    set_devices_db(devices)
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
    d = get_devices_db().get(device_id)
    if not d or d["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    return DevicePublic(id=d["id"], name=d["name"])

@app.put("/devices/{device_id}", response_model=DevicePublic)
async def update_device(device_id: str, upd: DeviceCreate, current_user: dict = Depends(auth.get_current_active_user)):
    devices = get_devices_db()
    d = devices.get(device_id)
    if not d or d["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    d["name"] = upd.name
    devices[device_id] = d
    set_devices_db(devices)
    return DevicePublic(id=device_id, name=d["name"])

@app.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: str, current_user: dict = Depends(auth.get_current_active_user)):
    devices = get_devices_db()
    d = devices.get(device_id)
    if not d or d["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    del devices[device_id]
    set_devices_db(devices)

# ——————————————————————————————
# Schedule endpoints
# ——————————————————————————————
@app.post("/schedules", response_model=SchedulePublic)
async def create_schedule(schedule: ScheduleCreate, current_user: dict = Depends(auth.get_current_active_user)):
    devices = get_devices_db()
    if schedule.device_id not in devices or devices[schedule.device_id]["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    sch_db = get_schedules_db()
    sid = str(uuid4())
    rpt = (
        ",".join(schedule.repeat)
        if isinstance(schedule.repeat, list) and schedule.repeat
        else (schedule.repeat or "Once")
    )
    sch_db[sid] = {
        "id": sid,
        "device_id": schedule.device_id,
        "owner": current_user["email"],
        "action": schedule.action,
        "time": schedule.time,
        "repeat": rpt,
    }
    set_schedules_db(sch_db)
    logger.info(f"Created schedule: {sch_db[sid]}")
    schedule_action_job(sid, schedule.device_id, schedule.action, schedule.time, rpt)
    return SchedulePublic(**sch_db[sid])

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
async def update_schedule(schedule_id: str, upd: ScheduleCreate, current_user: dict = Depends(auth.get_current_active_user)):
    sch_db = get_schedules_db()
    s = sch_db.get(schedule_id)
    devs = get_devices_db()
    if not s or s["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if upd.device_id not in devs or devs[upd.device_id]["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Device not found")
    rpt = (
        ",".join(upd.repeat)
        if isinstance(upd.repeat, list) and upd.repeat
        else (upd.repeat or "Once")
    )
    s.update({
        "device_id": upd.device_id,
        "action": upd.action,
        "time": upd.time,
        "repeat": rpt
    })
    set_schedules_db(sch_db)
    schedule_action_job(schedule_id, upd.device_id, upd.action, upd.time, rpt)
    return SchedulePublic(**s)

@app.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str, current_user: dict = Depends(auth.get_current_active_user)):
    sch_db = get_schedules_db()
    s = sch_db.get(schedule_id)
    if not s or s["owner"] != current_user["email"]:
        raise HTTPException(status_code=404, detail="Schedule not found")
    del sch_db[schedule_id]
    set_schedules_db(sch_db)
    try:
        scheduler.remove_job(schedule_id)
    except Exception:
        pass

# ——————————————————————————————
# WebSocket & heartbeat endpoints
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
