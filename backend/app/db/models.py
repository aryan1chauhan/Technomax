

from sqlalchemy import Column, Integer, String, Float, Boolean, ARRAY, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    fcm_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    hospital_type = Column(String(20), nullable=False, server_default="both")
    has_icu = Column(Boolean, nullable=False, server_default="false")
    specialists = Column(JSON, default=dict)
    district = Column(String, nullable=True, index=True)

class Availability(Base):
    __tablename__ = "availabilities"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    beds = Column(Integer, default=0)
    icu = Column(Integer, default=0)
    doctors = Column(Integer, default=0)
    equipment = Column(ARRAY(String), default=[])
    accepting = Column(Boolean, default=True)
    specialists = Column(JSONB, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    condition = Column(String)
    custom_condition = Column(String, nullable=True)
    equipment_needed = Column(ARRAY(String), default=[])
    ambulance_lat = Column(Float)
    ambulance_lng = Column(Float)
    assigned_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    final_score = Column(Float)
    distance_km = Column(Float)
    eta_minutes = Column(Integer)
    notes = Column(String, nullable=True)
    status = Column(String, nullable=False, default="dispatched")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CaseEvent(Base):
    __tablename__ = "case_events"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    status = Column(String, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String, nullable=True)
    note = Column(String, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    actual_eta_minutes = Column(Integer, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    case_id               = Column(String, nullable=False, index=True)
    condition_type        = Column(String, nullable=True)
    severity_score        = Column(Integer, nullable=True)
    ambulance_lat         = Column(Float, nullable=True)
    ambulance_lng         = Column(Float, nullable=True)
    selected_hospital_id  = Column(Integer, nullable=True)
    selected_hospital_name= Column(String, nullable=True)
    score                 = Column(Float, default=0.0, nullable=True)
    score_breakdown       = Column(JSONB, nullable=True)
    vitals                = Column(JSONB, nullable=True)
    required_equipment    = Column(ARRAY(String), nullable=True)
    ambulance_equipment   = Column(ARRAY(String), nullable=True)
    all_hospitals         = Column(JSONB, nullable=True)
    timestamp             = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DecisionCandidate(Base):
    __tablename__ = "decision_candidates"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    rank_position = Column(Integer, nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    eta_minutes = Column(Float, nullable=False, default=0.0)
    distance_km = Column(Float, nullable=True)
    available_beds_snapshot = Column(Integer, nullable=False, default=0)
    icu_beds_snapshot = Column(Integer, nullable=False, default=0)
    is_selected = Column(Boolean, nullable=False, default=False)
    score_breakdown = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    target_url = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    signature = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    next_attempt_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_status_code = Column(Integer, nullable=True)
    last_error = Column(String, nullable=True)
    response_body = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    channel = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    target = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=1)
    is_dlq = Column(Boolean, nullable=False, default=False)
    fallback_from_id = Column(Integer, ForeignKey("notification_deliveries.id"), nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CaseMessage(Base):
    __tablename__ = "case_messages"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

