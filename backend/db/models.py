"""Database models for platform persistence layer."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, ARRAY, Text
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    case_id               = Column(String, unique=True, nullable=False, index=True)
    condition_type        = Column(String, nullable=True)
    severity_score        = Column(Integer, nullable=True)
    ambulance_lat         = Column(Float, nullable=True)
    ambulance_lng         = Column(Float, nullable=True)
    selected_hospital_id  = Column(Integer, nullable=True)
    selected_hospital_name= Column(String, nullable=True)
    score                 = Column(Float, default=0.0, nullable=True)
    score_breakdown       = Column(JSON, nullable=True)
    vitals                = Column(JSON, nullable=True)
    required_equipment    = Column(ARRAY(Text), nullable=True)
    ambulance_equipment   = Column(ARRAY(Text), nullable=True)
    all_hospitals         = Column(JSON, nullable=True)
    timestamp             = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
