"""PostGIS repository implementations for domain persistence interfaces."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, TypeVar
from uuid import UUID, uuid4

import structlog
from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import and_, cast, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from hydra_c2.domain.entities.actor import Actor, ActorType, Affiliation, GeoPosition
from hydra_c2.domain.entities.event import Confidence, Event, EventType, Transmission
from hydra_c2.domain.interfaces.repositories import (
    ActorRepository,
    EventRepository,
    GeofenceRepository,
    TransmissionRepository,
)
from hydra_c2.infrastructure.persistence.postgis.connection import get_session_factory
from hydra_c2.infrastructure.persistence.postgis.models import ActorModel, EventModel, GeofenceModel

logger = structlog.get_logger()

EnumT = TypeVar("EnumT", bound=Enum)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _enum_or_default(enum_cls: type[EnumT], raw_value: str | None, default: EnumT) -> EnumT:
    if raw_value is None:
        return default
    try:
        return enum_cls(raw_value)
    except ValueError:
        return default


def _point_from_position(position: GeoPosition | None, include_altitude: bool) -> WKTElement | None:
    if position is None:
        return None
    if include_altitude and position.altitude_m is not None:
        return WKTElement(f"POINTZ({position.longitude} {position.latitude} {position.altitude_m})", srid=4326)
    return WKTElement(f"POINT({position.longitude} {position.latitude})", srid=4326)


def _position_from_coords(
    latitude: float | None, longitude: float | None, altitude: float | None = None
) -> GeoPosition | None:
    if latitude is None or longitude is None:
        return None
    return GeoPosition(latitude=latitude, longitude=longitude, altitude_m=altitude)


class PostGISActorRepository(ActorRepository):
    """PostGIS-backed implementation of ``ActorRepository``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()

    async def save(self, actor: Actor) -> None:
        if actor.position is None:
            raise ValueError("Actor position is required for PostGIS persistence")

        payload = dict(actor.metadata)
        payload.setdefault("actor_type", actor.actor_type.value)
        payload.setdefault("affiliation", actor.affiliation.value)
        payload.setdefault("first_seen", _ensure_utc(actor.first_seen).isoformat())
        values = {
            "actor_id": actor.id,
            "callsign": actor.callsign,
            "team": actor.affiliation.value,
            "geom": _point_from_position(actor.position, include_altitude=True),
            "speed_mps": actor.speed_mps,
            "course_deg": actor.course_deg,
            "source": actor.source,
            "confidence": actor.confidence,
            "metadata": payload,
            "recorded_at": _ensure_utc(actor.last_seen),
        }

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(insert(ActorModel).values(**values))
        logger.debug("postgis_actor_saved", actor_id=str(actor.id), callsign=actor.callsign)

    async def find_by_id(self, actor_id: UUID) -> Actor | None:
        stmt = (
            select(
                ActorModel,
                func.ST_Y(ActorModel.geom).label("latitude"),
                func.ST_X(ActorModel.geom).label("longitude"),
                func.ST_Z(ActorModel.geom).label("altitude"),
            )
            .where(ActorModel.actor_id == actor_id)
            .order_by(ActorModel.recorded_at.desc())
            .limit(1)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.first()

        if row is None:
            return None
        return self._actor_from_row(row)

    async def find_by_callsign(self, callsign: str) -> Actor | None:
        stmt = (
            select(
                ActorModel,
                func.ST_Y(ActorModel.geom).label("latitude"),
                func.ST_X(ActorModel.geom).label("longitude"),
                func.ST_Z(ActorModel.geom).label("altitude"),
            )
            .where(ActorModel.callsign == callsign)
            .order_by(ActorModel.recorded_at.desc())
            .limit(1)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.first()

        if row is None:
            return None
        return self._actor_from_row(row)

    async def find_recent(self, limit: int = 100) -> Sequence[Actor]:
        subq = (
            select(ActorModel.actor_id, func.max(ActorModel.recorded_at).label('max_time'))
            .group_by(ActorModel.actor_id)
            .subquery()
        )
        stmt = (
            select(
                ActorModel,
                func.ST_Y(ActorModel.geom).label('latitude'),
                func.ST_X(ActorModel.geom).label('longitude'),
                func.ST_Z(ActorModel.geom).label('altitude'),
            )
            .join(subq, and_(ActorModel.actor_id == subq.c.actor_id, ActorModel.recorded_at == subq.c.max_time))
            .order_by(ActorModel.recorded_at.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()
        return [self._actor_from_row(row) for row in rows]

    async def find_within_radius(self, center: GeoPosition, radius_meters: float) -> Sequence[Actor]:
        center_point = func.ST_SetSRID(func.ST_MakePoint(center.longitude, center.latitude), 4326)
        spatial_filter = func.ST_DWithin(
            cast(ActorModel.geom, Geography),
            cast(center_point, Geography),
            radius_meters,
        )
        stmt = select(
            ActorModel,
            func.ST_Y(ActorModel.geom).label("latitude"),
            func.ST_X(ActorModel.geom).label("longitude"),
            func.ST_Z(ActorModel.geom).label("altitude"),
        ).where(spatial_filter)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        latest_by_actor: dict[UUID, Any] = {}
        for row in rows:
            model = row[0]
            existing = latest_by_actor.get(model.actor_id)
            if existing is None or model.recorded_at > existing[0].recorded_at:
                latest_by_actor[model.actor_id] = row

        return [self._actor_from_row(row) for row in latest_by_actor.values()]

    async def find_co_located(
        self, actor_id: UUID, time_window_seconds: int = 7200, distance_meters: float = 100.0
    ) -> Sequence[Actor]:
        reference_stmt = (
            select(ActorModel).where(ActorModel.actor_id == actor_id).order_by(ActorModel.recorded_at.desc()).limit(1)
        )
        async with self._session_factory() as session:
            reference_result = await session.execute(reference_stmt)
            reference = reference_result.scalar_one_or_none()
            if reference is None:
                return []

            start_ts = reference.recorded_at - timedelta(seconds=time_window_seconds)
            end_ts = reference.recorded_at + timedelta(seconds=time_window_seconds)
            spatial_filter = func.ST_DWithin(
                cast(ActorModel.geom, Geography),
                cast(reference.geom, Geography),
                distance_meters,
            )
            stmt = (
                select(
                    ActorModel,
                    func.ST_Y(ActorModel.geom).label("latitude"),
                    func.ST_X(ActorModel.geom).label("longitude"),
                    func.ST_Z(ActorModel.geom).label("altitude"),
                )
                .where(
                    and_(
                        ActorModel.actor_id != actor_id,
                        ActorModel.recorded_at >= start_ts,
                        ActorModel.recorded_at <= end_ts,
                        spatial_filter,
                    )
                )
                .order_by(ActorModel.recorded_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.all()

        latest_by_actor: dict[UUID, Any] = {}
        for row in rows:
            model = row[0]
            if model.actor_id not in latest_by_actor:
                latest_by_actor[model.actor_id] = row

        return [self._actor_from_row(row) for row in latest_by_actor.values()]

    async def find_network(self, actor_id: UUID, max_depth: int = 3) -> Sequence[Actor]:
        visited: set[UUID] = {actor_id}
        frontier: set[UUID] = {actor_id}
        discovered: dict[UUID, Actor] = {}

        for _ in range(max_depth):
            if not frontier:
                break
            next_frontier: set[UUID] = set()
            for node_id in frontier:
                neighbors = await self.find_co_located(node_id)
                for neighbor in neighbors:
                    if neighbor.id in visited:
                        continue
                    visited.add(neighbor.id)
                    discovered[neighbor.id] = neighbor
                    next_frontier.add(neighbor.id)
            frontier = next_frontier

        return list(discovered.values())

    def _actor_from_row(self, row: Any) -> Actor:
        model: ActorModel = row[0]
        metadata = dict(model.metadata_json or {})
        position = _position_from_coords(
            latitude=row.latitude,
            longitude=row.longitude,
            altitude=row.altitude,
        )
        actor_type_raw = metadata.get("actor_type")
        affiliation_raw = metadata.get("affiliation")
        actor_type = _enum_or_default(
            ActorType,
            actor_type_raw if isinstance(actor_type_raw, str) else None,
            ActorType.UNKNOWN,
        )
        affiliation = _enum_or_default(
            Affiliation,
            affiliation_raw if isinstance(affiliation_raw, str) else None,
            Affiliation.UNKNOWN,
        )
        first_seen_raw = metadata.get("first_seen")
        first_seen = (
            _ensure_utc(datetime.fromisoformat(first_seen_raw))
            if isinstance(first_seen_raw, str)
            else model.recorded_at
        )

        return Actor(
            id=model.actor_id,
            callsign=model.callsign,
            actor_type=actor_type,
            affiliation=affiliation,
            position=position,
            speed_mps=model.speed_mps,
            course_deg=model.course_deg,
            source=model.source,
            first_seen=_ensure_utc(first_seen),
            last_seen=_ensure_utc(model.recorded_at),
            confidence=model.confidence,
            metadata=metadata,
        )


class PostGISEventRepository(EventRepository):
    """PostGIS-backed implementation of ``EventRepository``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()

    async def save(self, event: Event) -> None:
        metadata = dict(event.metadata)
        metadata["domain_id"] = str(event.id)
        metadata["description"] = event.description
        metadata["confidence"] = event.confidence.value
        metadata["actor_ids"] = [str(actor_id) for actor_id in event.actor_ids]

        values = {
            "detector": event.source,
            "det_type": event.event_type.value,
            "freq_mhz": metadata.get("freq_mhz"),
            "bearing_deg": metadata.get("bearing_deg"),
            "power_dbm": metadata.get("power_dbm"),
            "geom": _point_from_position(event.location, include_altitude=False),
            "target_geom": None,
            "metadata": metadata,
            "detected_at": _ensure_utc(event.timestamp),
        }

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(insert(EventModel).values(**values))
        logger.debug("postgis_event_saved", event_id=str(event.id), event_type=event.event_type.value)

    async def find_by_id(self, event_id: UUID) -> Event | None:
        stmt = (
            select(
                EventModel,
                func.ST_Y(EventModel.geom).label("latitude"),
                func.ST_X(EventModel.geom).label("longitude"),
            )
            .where(EventModel.metadata_json["domain_id"].astext == str(event_id))
            .order_by(EventModel.detected_at.desc())
            .limit(1)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.first()

        if row is None:
            return None
        return self._event_from_row(row)

    async def find_in_area(
        self,
        center: GeoPosition,
        radius_meters: float,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Sequence[Event]:
        center_point = func.ST_SetSRID(func.ST_MakePoint(center.longitude, center.latitude), 4326)
        conditions: list[Any] = [
            func.ST_DWithin(cast(EventModel.geom, Geography), cast(center_point, Geography), radius_meters)
        ]
        if start_time is not None:
            conditions.append(EventModel.detected_at >= _ensure_utc(start_time))
        if end_time is not None:
            conditions.append(EventModel.detected_at <= _ensure_utc(end_time))

        stmt = (
            select(
                EventModel,
                func.ST_Y(EventModel.geom).label("latitude"),
                func.ST_X(EventModel.geom).label("longitude"),
            )
            .where(and_(*conditions))
            .order_by(EventModel.detected_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [self._event_from_row(row) for row in rows]

    async def find_by_actor(self, actor_id: UUID) -> Sequence[Event]:
        actor_id_text = str(actor_id)
        stmt = (
            select(
                EventModel,
                func.ST_Y(EventModel.geom).label("latitude"),
                func.ST_X(EventModel.geom).label("longitude"),
            )
            .where(cast(EventModel.metadata_json, JSONB).contains({"actor_ids": [actor_id_text]}))
            .order_by(EventModel.detected_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [self._event_from_row(row) for row in rows]

    def _event_from_row(self, row: Any) -> Event:
        model: EventModel = row[0]
        metadata = dict(model.metadata_json or {})
        domain_id = metadata.get("domain_id")
        event_id = UUID(domain_id) if isinstance(domain_id, str) else uuid4()
        event_type = _enum_or_default(EventType, model.det_type, EventType.OBSERVATION)
        confidence_raw = metadata.get("confidence")
        confidence = _enum_or_default(
            Confidence,
            confidence_raw if isinstance(confidence_raw, str) else None,
            Confidence.MEDIUM,
        )
        actor_ids_raw = metadata.get("actor_ids")
        actor_ids: list[UUID] = []
        if isinstance(actor_ids_raw, list):
            actor_ids = [UUID(raw_id) for raw_id in actor_ids_raw if isinstance(raw_id, str)]
        description_raw = metadata.get("description")
        description = description_raw if isinstance(description_raw, str) else ""
        location = _position_from_coords(row.latitude, row.longitude)

        return Event(
            id=event_id,
            event_type=event_type,
            timestamp=_ensure_utc(model.detected_at),
            location=location,
            description=description,
            confidence=confidence,
            source=model.detector,
            actor_ids=actor_ids,
            metadata=metadata,
        )


class PostGISTransmissionRepository(TransmissionRepository):
    """PostGIS-backed implementation of ``TransmissionRepository``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()

    async def save(self, transmission: Transmission) -> None:
        metadata = dict(transmission.metadata)
        metadata["domain_id"] = str(transmission.id)
        metadata["bandwidth_khz"] = transmission.bandwidth_khz
        metadata["modulation"] = transmission.modulation

        values = {
            "detector": transmission.source_sdr,
            "det_type": EventType.TRANSMISSION.value,
            "freq_mhz": transmission.frequency_mhz,
            "bearing_deg": transmission.bearing_deg,
            "power_dbm": transmission.power_dbm,
            "geom": None,
            "target_geom": _point_from_position(transmission.location, include_altitude=False),
            "metadata": metadata,
            "detected_at": _ensure_utc(transmission.timestamp),
        }

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(insert(EventModel).values(**values))
        logger.debug(
            "postgis_transmission_saved", transmission_id=str(transmission.id), freq_mhz=transmission.frequency_mhz
        )

    async def find_by_frequency(self, freq_mhz: float, tolerance_mhz: float = 0.025) -> Sequence[Transmission]:
        lower_bound = freq_mhz - tolerance_mhz
        upper_bound = freq_mhz + tolerance_mhz
        stmt = (
            select(
                EventModel,
                func.ST_Y(EventModel.target_geom).label("latitude"),
                func.ST_X(EventModel.target_geom).label("longitude"),
            )
            .where(
                and_(
                    EventModel.freq_mhz.is_not(None),
                    EventModel.freq_mhz >= lower_bound,
                    EventModel.freq_mhz <= upper_bound,
                )
            )
            .order_by(EventModel.detected_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [self._transmission_from_row(row) for row in rows]

    async def find_bearings_for_triangulation(
        self, freq_mhz: float, time_window_seconds: int = 300
    ) -> Sequence[Transmission]:
        since = datetime.now(UTC) - timedelta(seconds=time_window_seconds)
        stmt = (
            select(
                EventModel,
                func.ST_Y(EventModel.target_geom).label("latitude"),
                func.ST_X(EventModel.target_geom).label("longitude"),
            )
            .where(
                and_(
                    EventModel.freq_mhz == freq_mhz,
                    EventModel.bearing_deg.is_not(None),
                    EventModel.detected_at >= since,
                )
            )
            .order_by(EventModel.detected_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [self._transmission_from_row(row) for row in rows]

    async def find_recent(self, limit: int = 100) -> Sequence[Transmission]:
        """Get most recently detected transmissions."""
        stmt = (
            select(
                EventModel,
                func.ST_Y(EventModel.target_geom).label("latitude"),
                func.ST_X(EventModel.target_geom).label("longitude"),
            )
            .where(EventModel.det_type == "TRANSMISSION")
            .order_by(EventModel.detected_at.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [self._transmission_from_row(row) for row in rows]

    def _transmission_from_row(self, row: Any) -> Transmission:
        model: EventModel = row[0]
        metadata = dict(model.metadata_json or {})
        domain_id = metadata.get("domain_id")
        transmission_id = UUID(domain_id) if isinstance(domain_id, str) else uuid4()
        location = _position_from_coords(row.latitude, row.longitude)
        bandwidth_raw = metadata.get("bandwidth_khz")
        bandwidth_khz = float(bandwidth_raw) if isinstance(bandwidth_raw, (int, float)) else None

        return Transmission(
            id=transmission_id,
            frequency_mhz=float(model.freq_mhz or 0.0),
            bandwidth_khz=bandwidth_khz,
            power_dbm=model.power_dbm,
            modulation=str(metadata.get("modulation", "UNKNOWN")),
            bearing_deg=model.bearing_deg,
            location=location,
            source_sdr=model.detector,
            timestamp=_ensure_utc(model.detected_at),
            metadata=metadata,
        )


class PostGISGeofenceRepository(GeofenceRepository):
    """PostGIS-backed implementation of ``GeofenceRepository``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or get_session_factory()

    async def check_breach(self, position: GeoPosition) -> Sequence[dict[str, object]]:
        point = func.ST_SetSRID(func.ST_MakePoint(position.longitude, position.latitude), 4326)
        stmt = select(GeofenceModel).where(
            and_(
                GeofenceModel.active.is_(True),
                func.ST_DWithin(cast(GeofenceModel.geom, Geography), cast(point, Geography), 0.0),
            )
        )

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            fences = result.scalars().all()

        return [
            {
                "id": fence.id,
                "name": fence.name,
                "fence_type": fence.fence_type,
                "active": fence.active,
                "metadata": dict(fence.metadata_json or {}),
            }
            for fence in fences
        ]

    async def create_geofence(self, name: str, polygon_wkt: str, fence_type: str = "ALERT") -> UUID:
        geofence_id = uuid4()
        values = {
            "id": geofence_id,
            "name": name,
            "fence_type": fence_type,
            "geom": WKTElement(polygon_wkt, srid=4326),
            "active": True,
            "created_by": "system",
            "metadata": {},
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(insert(GeofenceModel).values(**values))
        logger.info("postgis_geofence_created", geofence_id=str(geofence_id), name=name, fence_type=fence_type)
        return geofence_id


__all__ = [
    "PostGISActorRepository",
    "PostGISEventRepository",
    "PostGISTransmissionRepository",
    "PostGISGeofenceRepository",
]
