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
    role = Column(String(20), default="user")  # superadmin | user
    is_active = Column(Boolean, default=True)
    app_access = Column(JSON, nullable=False, default=lambda: {"scraper": True, "universe": False})
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="user")


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = {"schema": IDENTITY_SCHEMA} if IDENTITY_SCHEMA else {}

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey(f"{IDENTITY_USER_TABLE}.id"), nullable=True, index=True)
    action = Column(String(30), nullable=False)   # login | create_run | stop_run | continue_run | account/profile changes
    detail = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="activities")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey(f"{IDENTITY_USER_TABLE}.id"), nullable=True)
    crawler_id = Column(String(50), nullable=False)
    status = Column(String(20), default="queued")  # queued | running | success | failed | stopped
    params = Column(Text, default="{}")            # JSON: column, limit, fresh, show, ...
    input_path = Column(Text, nullable=True)
    output_path = Column(Text, nullable=True)
    log_path = Column(Text, nullable=True)
    pid = Column(Integer, nullable=True)
    waiting_for_human = Column(Boolean, default=False)
    progress_done = Column(Integer, nullable=True)
    progress_total = Column(Integer, nullable=True)
    returncode = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="runs")
