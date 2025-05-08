"""
Pydantic models for the Finger Bot backend.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, Literal

# --- User Models ---

class UserCreate(BaseModel):
    """Model for user registration data."""
    email: EmailStr
    password: str  # Frontend calls it password_needs_at_least_8_chars

class UserInDB(BaseModel):
    """Model for user data stored in the database."""
    email: EmailStr
    hashed_password: str

class UserPublic(BaseModel):
    """Model for user data returned to clients."""
    email: EmailStr

# --- Device Models ---

class DeviceCreate(BaseModel):
    """Model for device creation data."""
    name: str
    device_id: Optional[str] = None

class DeviceInDB(BaseModel):
    """Model for device data stored in the database."""
    id: str
    name: str
    owner: str  # email of the user who registered the device

class DevicePublic(BaseModel):
    """Model for device data returned to clients."""
    id: str
    name: str

class DeviceSetupInfo(BaseModel):
    """Model for device setup information."""
    ssid: str
    password: str
    server_host: str
    server_port: int = 12345

# --- Schedule Models ---

class ScheduleCreate(BaseModel):
    """Model for schedule creation data."""
    device_id: str
    action: Literal["press"]
    time: str  # "HH:MM" format
    repeat: str  # e.g., "Wednesdays", "Daily", "Weekdays"

class ScheduleInDB(BaseModel):
    """Model for schedule data stored in the database."""
    id: str
    device_id: str
    owner: str
    action: str
    time: str
    repeat: str

class SchedulePublic(BaseModel):
    """Model for schedule data returned to clients."""
    id: str
    device_id: str
    action: str
    time: str
    repeat: str
