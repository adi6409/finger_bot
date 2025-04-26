from sqlalchemy import Column, String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from backend.db import Base

class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    devices = relationship("Device", back_populates="owner_rel")
    schedules = relationship("Schedule", back_populates="owner_rel")

class Device(Base):
    __tablename__ = "devices"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner = Column(String, ForeignKey("users.email"), nullable=False)

    owner_rel = relationship("User", back_populates="devices")
    schedules = relationship("Schedule", back_populates="device_rel")

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(String, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    owner = Column(String, ForeignKey("users.email"), nullable=False)
    action = Column(String, nullable=False)
    time = Column(String, nullable=False)  # "HH:MM"
    repeat = Column(String, nullable=False)

    device_rel = relationship("Device", back_populates="schedules")
    owner_rel = relationship("User", back_populates="schedules")
