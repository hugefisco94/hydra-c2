"""PostGIS SQLAlchemy models for HYDRA-C2 persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import REAL, BigInteger, Boolean, DateTime, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for PostGIS persistence models."""


class ActorModel(Base):
    """Maps the ``pli_history`` table storing actor position history."""

    __tablename__ = "pli_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    callsign: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    team: Mapped[str | None] = mapped_column(String(32), nullable=True)
    geom: Mapped[WKBElement] = mapped_column(Geometry(geometry_type="POINTZ", srid=4326), nullable=False)
    speed_mps: Mapped[float | None] = mapped_column(REAL, nullable=True)
    course_deg: Mapped[float | None] = mapped_column(REAL, nullable=True)
    battery_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="ATAK")
    confidence: Mapped[float] = mapped_column(REAL, nullable=False, default=0.5)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class EventModel(Base):
    """Maps the ``sdr_detections`` table for generic operational events."""

    __tablename__ = "sdr_detections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    detector: Mapped[str] = mapped_column(String(32), nullable=False)
    det_type: Mapped[str] = mapped_column(String(32), nullable=False)
    freq_mhz: Mapped[float | None] = mapped_column(nullable=True)
    bearing_deg: Mapped[float | None] = mapped_column(REAL, nullable=True)
    power_dbm: Mapped[float | None] = mapped_column(REAL, nullable=True)
    geom: Mapped[WKBElement | None] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    target_geom: Mapped[WKBElement | None] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


# Transmission persistence uses the same physical table as EventModel.
TransmissionModel = EventModel


class GeofenceModel(Base):
    """Maps the ``geofences`` table used for breach checks and management."""

    __tablename__ = "geofences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    fence_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ALERT")
    geom: Mapped[WKBElement] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


__all__ = [
    "Base",
    "ActorModel",
    "EventModel",
    "TransmissionModel",
    "GeofenceModel",
]
