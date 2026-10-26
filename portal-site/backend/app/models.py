from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base, engine

IDENTITY_SCHEMA = "global" if engine.dialect.name == "postgresql" else None
IDENTITY_USER_TABLE = "global.users" if IDENTITY_SCHEMA else "users"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": IDENTITY_SCHEMA} if IDENTITY_SCHEMA else {}

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(100), default="")
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    app_access = Column(JSON, nullable=False, default=lambda: {"scraper": True, "universe": False})
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = {"schema": IDENTITY_SCHEMA} if IDENTITY_SCHEMA else {}

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey(f"{IDENTITY_USER_TABLE}.id"), nullable=True, index=True)
    action = Column(String(30), nullable=False)
    detail = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="activities")