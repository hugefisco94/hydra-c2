"""Neo4j repository for Actor graph queries and node retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from neo4j import AsyncDriver
from neo4j.graph import Node
from neo4j.spatial import WGS84Point
from neo4j.time import DateTime as Neo4jDateTime
import structlog
from structlog.typing import FilteringBoundLogger

from hydra_c2.domain.entities.actor import Actor, ActorType, Affiliation, GeoPosition
from hydra_c2.domain.interfaces.repositories import ActorRepository
from hydra_c2.infrastructure.persistence.neo4j.graph_service import Neo4jGraphService

logger: FilteringBoundLogger = structlog.get_logger()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _coerce_datetime(value: object, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, Neo4jDateTime):
        return _as_utc(value.to_native())
    return _as_utc(fallback)


def _coerce_metadata(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _coerce_affiliation(value: object) -> Affiliation:
    if isinstance(value, str):
        try:
            return Affiliation(value)
        except ValueError:
            return Affiliation.UNKNOWN
    return Affiliation.UNKNOWN


def _coerce_actor_type(value: object) -> ActorType:
    if isinstance(value, str):
        try:
            return ActorType(value)
        except ValueError:
            return ActorType.UNKNOWN
    return ActorType.UNKNOWN


def _node_to_actor(node: Node) -> Actor:
    location = node.get("location")
    position: GeoPosition | None = None
    if isinstance(location, WGS84Point):
        position = GeoPosition(latitude=float(location.latitude), longitude=float(location.longitude))

    now_utc = datetime.now(UTC)
    first_seen = _coerce_datetime(node.get("first_seen"), now_utc)
    last_seen = _coerce_datetime(node.get("last_seen"), now_utc)

    speed_value = node.get("speed_mps")
    speed_mps = float(speed_value) if isinstance(speed_value, (int, float)) else None

    course_value = node.get("course_deg")
    course_deg = float(course_value) if isinstance(course_value, (int, float)) else None

    confidence_value = node.get("confidence")
    confidence = float(confidence_value) if isinstance(confidence_value, (int, float)) else 0.5

    id_value = node.get("id")
    callsign_value = node.get("callsign")
    source_value = node.get("source")

    if not isinstance(id_value, str):
        raise ValueError("Actor node is missing required string property: id")
    if not isinstance(callsign_value, str):
        callsign_value = ""
    if not isinstance(source_value, str):
        source_value = "MANUAL"

    return Actor(
        id=UUID(id_value),
        callsign=callsign_value,
        actor_type=_coerce_actor_type(node.get("type")),
        affiliation=_coerce_affiliation(node.get("affiliation")),
        position=position,
        speed_mps=speed_mps,
        course_deg=course_deg,
        source=source_value,
        first_seen=first_seen,
        last_seen=last_seen,
        confidence=confidence,
        metadata=_coerce_metadata(node.get("metadata")),
    )


class Neo4jActorRepository(ActorRepository):
    """Neo4j-backed Actor repository with graph traversal methods."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver: AsyncDriver = driver
        self._graph_service: Neo4jGraphService = Neo4jGraphService(driver)

    async def save(self, actor: Actor) -> None:
        """Persist Actor node in Neo4j graph store."""
        await self._graph_service.upsert_actor_node(actor)

    async def find_by_id(self, actor_id: UUID) -> Actor | None:
        """Retrieve Actor by unique identifier."""
        query = """
        MATCH (a:Actor {id: $actor_id})
        RETURN a
        LIMIT 1
        """
        params = {"actor_id": str(actor_id)}

        async with self._driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()

        if record is None:
            return None

        node = record.get("a")
        if not isinstance(node, Node):
            return None
        return _node_to_actor(node)

    async def find_by_callsign(self, callsign: str) -> Actor | None:
        """Retrieve Actor by tactical callsign."""
        query = """
        MATCH (a:Actor {callsign: $callsign})
        RETURN a
        LIMIT 1
        """
        params = {"callsign": callsign}

        async with self._driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()

        if record is None:
            return None

        node = record.get("a")
        if not isinstance(node, Node):
            return None
        return _node_to_actor(node)

    async def find_within_radius(self, center: GeoPosition, radius_meters: float) -> Sequence[Actor]:
        """Find actors within radius using Neo4j point distance."""
        query = """
        MATCH (a:Actor)
        WHERE a.location IS NOT NULL
          AND point.distance(a.location, point({latitude: $lat, longitude: $lon})) <= $radius_meters
        RETURN a
        """
        params = {
            "lat": center.latitude,
            "lon": center.longitude,
            "radius_meters": radius_meters,
        }

        async with self._driver.session() as session:
            result = await session.run(query, params)
            records = await result.data()

        actors: list[Actor] = []
        for record in records:
            node = record.get("a")
            if isinstance(node, Node):
                actors.append(_node_to_actor(node))
        return actors

    async def find_co_located(
        self,
        actor_id: UUID,
        time_window_seconds: int = 7200,
        distance_meters: float = 100.0,
    ) -> Sequence[Actor]:
        """Graph query for nearby actors in temporal+distance window."""
        nodes = await self._graph_service.find_co_located(
            actor_id=actor_id,
            time_window=time_window_seconds,
            distance=distance_meters,
        )
        return [_node_to_actor(node) for node in nodes]

    async def find_network(self, actor_id: UUID, max_depth: int = 3) -> Sequence[Actor]:
        """Graph traversal for connected actor network."""
        nodes = await self._graph_service.find_network(actor_id=actor_id, max_depth=max_depth)
        return [_node_to_actor(node) for node in nodes]
