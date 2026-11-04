from datetime import datetime, timezone

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Table, Text, UniqueConstraint, func)
from sqlalchemy.orm import relationship

from .db import Base, engine

APP_SCHEMA = "universe" if engine.dialect.name == "postgresql" else None
IDENTITY_SCHEMA = "global" if engine.dialect.name == "postgresql" else None
VEHICLE_TABLE = "universe.vehicle" if APP_SCHEMA else "vehicle"
VIN_TABLE = "universe.vin" if APP_SCHEMA else "vin"
OEM_TABLE = "universe.oem" if APP_SCHEMA else "oem"
PARTSLINK_TABLE = "universe.partslink" if APP_SCHEMA else "partslink"
INTERCHANGE_TABLE = "universe.interchange" if APP_SCHEMA else "interchange"

OEM_VIN = Table(
    "oem_vin",
    Base.metadata,
    Column("id_oem", ForeignKey(f"{OEM_TABLE}.id", ondelete="CASCADE"), primary_key=True),
    Column("id_vin", ForeignKey(f"{VIN_TABLE}.id", ondelete="CASCADE"), primary_key=True),
    schema=APP_SCHEMA,
)
OEM_PARTSLINK = Table(
    "oem_partslink",
    Base.metadata,
    Column("id_oem", ForeignKey(f"{OEM_TABLE}.id", ondelete="CASCADE"), primary_key=True),
    Column("id_partslink", ForeignKey(f"{PARTSLINK_TABLE}.id", ondelete="CASCADE"), primary_key=True),
    schema=APP_SCHEMA,
)
OEM_INTERCHANGE = Table(
    "oem_interchange",
    Base.metadata,
    Column("id_oem", ForeignKey(f"{OEM_TABLE}.id", ondelete="CASCADE"), primary_key=True),
    Column("id_interchange", ForeignKey(f"{INTERCHANGE_TABLE}.id", ondelete="CASCADE"), primary_key=True),
    schema=APP_SCHEMA,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vehicle(Base):
    __tablename__ = "vehicle"
    __table_args__ = (
        UniqueConstraint("year", "make_key", "model_key", name="uq_vehicle_year_make_model"),
        CheckConstraint("year >= 1886 AND year <= 2100", name="ck_vehicle_year_range"),
        Index("ix_vehicle_make_model", "make_key", "model_key"),
        {"schema": APP_SCHEMA} if APP_SCHEMA else {},
    )

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    make = Column(String(100), nullable=False)
    model = Column(String(150), nullable=False)
    make_key = Column(String(100), nullable=False)
    model_key = Column(String(150), nullable=False)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    vins = relationship("Vin", back_populates="vehicle", cascade="all, delete-orphan", passive_deletes=True)


class Vin(Base):
    __tablename__ = "vin"
    __table_args__ = (
        UniqueConstraint("id_vehicle", "vin_key", name="uq_vin_vehicle_vin"),
        Index("ix_vin_key", "vin_key"),
        {"schema": APP_SCHEMA} if APP_SCHEMA else {},
    )

    id = Column(Integer, primary_key=True)
    id_vehicle = Column(ForeignKey(f"{VEHICLE_TABLE}.id", ondelete="CASCADE"), nullable=False, index=True)
    vin = Column(String(32), nullable=False)
    vin_key = Column(String(32), nullable=False)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    vehicle = relationship("Vehicle", back_populates="vins")
    oems = relationship("Oem", secondary=OEM_VIN, back_populates="vins")


class Oem(Base):
    __tablename__ = "oem"
    __table_args__ = (
        UniqueConstraint("oem_key", name="uq_oem_key"),
        {"schema": APP_SCHEMA} if APP_SCHEMA else {},
    )

    id = Column(Integer, primary_key=True)
    oem = Column(String(150), nullable=False)
    oem_key = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    vins = relationship("Vin", secondary=OEM_VIN, back_populates="oems")
    partslinks = relationship("Partslink", secondary=OEM_PARTSLINK, back_populates="oems")
    interchanges = relationship("Interchange", secondary=OEM_INTERCHANGE, back_populates="oems")


class Partslink(Base):
    __tablename__ = "partslink"
    __table_args__ = (
        UniqueConstraint("partslink_key", name="uq_partslink_key"),
        Index("ix_partslink_key", "partslink_key"),
        {"schema": APP_SCHEMA} if APP_SCHEMA else {},
    )

    id = Column(Integer, primary_key=True)
    partslink = Column(String(150), nullable=False)
    partslink_key = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    oems = relationship("Oem", secondary=OEM_PARTSLINK, back_populates="partslinks")


class Interchange(Base):
    __tablename__ = "interchange"
    __table_args__ = (
        UniqueConstraint("interchange_key", name="uq_interchange_key"),
        Index("ix_interchange_key", "interchange_key"),
        {"schema": APP_SCHEMA} if APP_SCHEMA else {},
    )

    id = Column(Integer, primary_key=True)
    interchange = Column(String(150), nullable=False)
    interchange_key = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    oems = relationship("Oem", secondary=OEM_INTERCHANGE, back_populates="interchanges")


class CccMarketRecord(Base):
    __tablename__ = "ccc_market_data"
    __table_args__ = (
        UniqueConstraint("oem", "vin", "crawl_date", "market_index", name="uq_ccc_market_oem_vin_date_index"),
        Index("ix_ccc_market_crawl_date", "crawl_date"),
        {"schema": APP_SCHEMA} if APP_SCHEMA else {},
    )

    id = Column(Integer, primary_key=True)
    oem = Column(String(150), nullable=False)
    vin = Column(String(32), nullable=False)
    crawl_date = Column(DateTime(timezone=True), nullable=False)
    market_index = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=False, default="")
    vendor = Column(Text, nullable=False, default="")
    market_data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Activity(Base):
    __tablename__ = "activities" if APP_SCHEMA else "universe_activities"
    __table_args__ = {"schema": APP_SCHEMA} if APP_SCHEMA else {}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(50), nullable=False)
    detail = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)