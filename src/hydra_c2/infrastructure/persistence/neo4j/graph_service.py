"""Neo4j graph service for relationship-centric operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from neo4j import AsyncDriver
from neo4j.graph import Node
import structlog
from structlog.typing import FilteringBoundLogger

from hydra_c2.domain.entities.actor import Actor

logger: FilteringBoundLogger = structlog.get_logger()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _datetime_str(value: datetime) -> str:
    return _as_utc(value).isoformat()


class Neo4jGraphService:
    """Service object for managing Actor/Event graph relationships in Neo4j."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver: AsyncDriver = driver

    async def upsert_actor_node(self, actor: Actor) -> None:
        """Create or update an Actor node and its properties."""
        latitude = actor.position.latitude if actor.position is not None else None
        longitude = actor.position.longitude if actor.position is not None else None

        params: dict[str, object] = {
            "id": str(actor.id),
            "callsign": actor.callsign,
            "actor_type": actor.actor_type.value,
            "affiliation": actor.affiliation.value,
            "source": actor.source,
            "speed_mps": actor.speed_mps,
            "course_deg": actor.course_deg,
            "confidence": actor.confidence,
            "metadata": actor.metadata,
            "first_seen": _datetime_str(actor.first_seen),
            "last_seen": _datetime_str(actor.last_seen),
            "updated_at": _datetime_str(datetime.now(UTC)),
            "latitude": latitude,
            "longitude": longitude,
        }

        query = """
        MERGE (a:Actor {id: $id})
        SET a.callsign = $callsign,
            a.type = $actor_type,
            a.affiliation = $affiliation,
            a.source = $source,
            a.speed_mps = $speed_mps,
            a.course_deg = $course_deg,
            a.confidence = $confidence,
            a.metadata = $metadata,
            a.first_seen = datetime($first_seen),
            a.last_seen = datetime($last_seen),
            a.updated_at = datetime($updated_at)
        FOREACH (_ IN CASE WHEN $latitude IS NULL OR $longitude IS NULL THEN [] ELSE [1] END |
            SET a.location = point({latitude: $latitude, longitude: $longitude})
        )
        """

        async with self._driver.session() as session:
            _ = await session.run(query, params)

        logger.debug("neo4j_actor_upserted", actor_id=str(actor.id), callsign=actor.callsign)

    async def create_observed_event(self, actor_id: UUID, event_id: UUID) -> None:
        """Create OBSERVED_AT relationship from Actor to Event."""
        query = """
        MATCH (a:Actor {id: $actor_id})
        MATCH (e:Event {id: $event_id})
        MERGE (a)-[r:OBSERVED_AT]->(e)
        SET r.created_at = datetime($created_at)
        """
        params = {
            "actor_id": str(actor_id),
            "event_id": str(event_id),
            "created_at": _datetime_str(datetime.now(UTC)),
        }

        async with self._driver.session() as session:
            _ = await session.run(query, params)

        logger.debug("neo4j_observed_event_created", actor_id=str(actor_id), event_id=str(event_id))

    async def create_co_located(
        self,
        actor1_id: UUID,
        actor2_id: UUID,
        timestamp: datetime,
        distance_m: float,
    ) -> None:
        """Create CO_LOCATED_WITH relationship between two Actor nodes."""
        query = """
        MATCH (a1:Actor {id: $actor1_id})
        MATCH (a2:Actor {id: $actor2_id})
        WHERE a1.id <> a2.id
        WITH CASE WHEN a1.id < a2.id THEN [a1, a2] ELSE [a2, a1] END AS pair
        MERGE (pair[0])-[r:CO_LOCATED_WITH {timestamp: datetime($timestamp)}]->(pair[1])
        SET r.distance_m = $distance_m,
            r.updated_at = datetime($updated_at)
        """
        params = {
            "actor1_id": str(actor1_id),
            "actor2_id": str(actor2_id),
            "timestamp": _datetime_str(timestamp),
            "distance_m": distance_m,
            "updated_at": _datetime_str(datetime.now(UTC)),
        }

        async with self._driver.session() as session:
            _ = await session.run(query, params)

        logger.debug(
            "neo4j_co_located_created",
            actor1_id=str(actor1_id),
            actor2_id=str(actor2_id),
            distance_m=distance_m,
        )

    async def create_communicated(self, actor1_id: UUID, actor2_id: UUID, freq_mhz: float) -> None:
        """Create COMMUNICATED_WITH relationship between two Actor nodes."""
        query = """
        MATCH (a1:Actor {id: $actor1_id})
        MATCH (a2:Actor {id: $actor2_id})
        WHERE a1.id <> a2.id
        WITH CASE WHEN a1.id < a2.id THEN [a1, a2] ELSE [a2, a1] END AS pair
        MERGE (pair[0])-[r:COMMUNICATED_WITH {freq_mhz: $freq_mhz}]->(pair[1])
        SET r.last_detected = datetime($last_detected)
        """
        params = {
            "actor1_id": str(actor1_id),
            "actor2_id": str(actor2_id),
            "freq_mhz": freq_mhz,
            "last_detected": _datetime_str(datetime.now(UTC)),
        }

        async with self._driver.session() as session:
            _ = await session.run(query, params)

        logger.debug(
            "neo4j_communicated_created",
            actor1_id=str(actor1_id),
            actor2_id=str(actor2_id),
            freq_mhz=freq_mhz,
        )

    async def find_network(self, actor_id: UUID, max_depth: int = 3) -> list[Node]:
        """Find Actor nodes connected within max variable-length depth."""
        depth = max(1, min(max_depth, 6))
        if depth == 1:
            query = """
            MATCH (seed:Actor {id: $actor_id})
            MATCH (seed)-[*1..1]-(connected:Actor)
            WHERE connected.id <> $actor_id
            RETURN DISTINCT connected
            """
        elif depth == 2:
            query = """
            MATCH (seed:Actor {id: $actor_id})
            MATCH (seed)-[*1..2]-(connected:Actor)
            WHERE connected.id <> $actor_id
            RETURN DISTINCT connected
            """
        elif depth == 3:
            query = """
            MATCH (seed:Actor {id: $actor_id})
            MATCH (seed)-[*1..3]-(connected:Actor)
            WHERE connected.id <> $actor_id
            RETURN DISTINCT connected
            """
        elif depth == 4:
            query = """
            MATCH (seed:Actor {id: $actor_id})
            MATCH (seed)-[*1..4]-(connected:Actor)
            WHERE connected.id <> $actor_id
            RETURN DISTINCT connected
            """
        elif depth == 5:
            query = """
            MATCH (seed:Actor {id: $actor_id})
            MATCH (seed)-[*1..5]-(connected:Actor)
            WHERE connected.id <> $actor_id
            RETURN DISTINCT connected
            """
        else:
            query = """
            MATCH (seed:Actor {id: $actor_id})
            MATCH (seed)-[*1..6]-(connected:Actor)
            WHERE connected.id <> $actor_id
            RETURN DISTINCT connected
            """
        params = {
            "actor_id": str(actor_id),
        }

        async with self._driver.session() as session:
            result = await session.run(query, params)
            records = await result.data()

        return [record["connected"] for record in records if isinstance(record.get("connected"), Node)]

    async def find_co_located(
        self,
        actor_id: UUID,
        time_window: int = 7200,
        distance: float = 100.0,
    ) -> list[Node]:
        """Find Actor nodes co-located in a temporal+spatial window."""
        window_start = datetime.now(UTC) - timedelta(seconds=time_window)

        query = """
        MATCH (seed:Actor {id: $actor_id})-[r:CO_LOCATED_WITH]-(other:Actor)
        WHERE r.timestamp >= datetime($window_start)
          AND r.distance_m <= $distance
          AND other.id <> $actor_id
        RETURN DISTINCT other
        """
        params = {
            "actor_id": str(actor_id),
            "window_start": _datetime_str(window_start),
            "distance": distance,
        }

        async with self._driver.session() as session:
            result = await session.run(query, params)
            records = await result.data()

        return [record["other"] for record in records if isinstance(record.get("other"), Node)]
