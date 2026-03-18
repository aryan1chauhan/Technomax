from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    lat = Column(Float)
    lng = Column(Float)

class Availability(Base):
    __tablename__ = "availabilities"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    beds = Column(Integer, default=0)
    icu = Column(Integer, default=0)
    doctors = Column(Integer, default=0)
    equipment = Column(ARRAY(String), default=[])
    accepting = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    condition = Column(String)
    equipment_needed = Column(ARRAY(String), default=[])
    ambulance_lat = Column(Float)
    ambulance_lng = Column(Float)
    assigned_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    final_score = Column(Float)
    distance_km = Column(Float)
    eta_minutes = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
