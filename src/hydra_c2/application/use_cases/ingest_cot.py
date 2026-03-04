"""Application Use Case: Ingest Cursor on Target (CoT) events.

This is the primary data ingestion pipeline for Layer 3.
TAK Server → CoT XML → Parse → Normalize → Route to PostGIS + Neo4j + MQTT.

Follows Clean Architecture: depends only on domain interfaces, never on
concrete infrastructure implementations.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from hydra_c2.domain.entities.actor import Actor, Affiliation, ActorType, GeoPosition
from hydra_c2.domain.entities.event import Event, EventType, Confidence
from hydra_c2.domain.interfaces.messaging import MessagePublisher
from hydra_c2.domain.interfaces.repositories import ActorRepository, EventRepository


@dataclass
class CotIngestResult:
    """Result of CoT event ingestion."""

    actor_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    event_type: str = ""
    callsign: str = ""
    position: Optional[GeoPosition] = None
    success: bool = True
    error: Optional[str] = None


class IngestCotUseCase:
    """Ingest and process Cursor on Target XML events.

    This use case:
    1. Parses CoT XML (MIL-STD format from ATAK/TAK Server)
    2. Extracts actor position and metadata
    3. Creates/updates Actor entity
    4. Creates Event entity
    5. Publishes to message bus for downstream consumers
    6. Persists to PostGIS (spatial) + Neo4j (graph)
    """

    def __init__(
        self,
        actor_repo: ActorRepository,
        event_repo: EventRepository,
        publisher: MessagePublisher,
    ) -> None:
        self._actor_repo = actor_repo
        self._event_repo = event_repo
        self._publisher = publisher

    async def execute(self, cot_xml: str) -> CotIngestResult:
        """Process a single CoT XML event."""
        try:
            parsed = self._parse_cot(cot_xml)
            if parsed is None:
                return CotIngestResult(success=False, error="Failed to parse CoT XML")

            actor = await self._upsert_actor(parsed)
            event = self._create_event(parsed, actor.id)

            await self._actor_repo.save(actor)
            await self._event_repo.save(event)

            await self._publisher.publish(
                f"hydra/cot/{parsed.get('type', 'unknown')}",
                {
                    "actor_id": str(actor.id),
                    "event_id": str(event.id),
                    "callsign": actor.callsign,
                    "lat": actor.position.latitude if actor.position else None,
                    "lon": actor.position.longitude if actor.position else None,
                    "type": parsed.get("type", ""),
                    "timestamp": event.timestamp.isoformat(),
                },
            )

            return CotIngestResult(
                actor_id=actor.id,
                event_id=event.id,
                event_type=parsed.get("type", ""),
                callsign=actor.callsign,
                position=actor.position,
            )

        except Exception as e:
            return CotIngestResult(success=False, error=str(e))

    def _parse_cot(self, cot_xml: str) -> Optional[dict[str, Any]]:
        """Parse CoT XML into structured dict.

        CoT XML format:
        <event version="2.0" type="a-f-G-U-C" uid="..." time="..." start="..." stale="...">
            <point lat="..." lon="..." hae="..." ce="..." le="..."/>
            <detail>
                <contact callsign="ALPHA-1"/>
                <__group name="Cyan" role="Team Member"/>
                <track speed="..." course="..."/>
            </detail>
        </event>
        """
        try:
            root = ET.fromstring(cot_xml)
        except ET.ParseError:
            return None

        if root.tag != "event":
            return None

        point = root.find("point")
        detail = root.find("detail")
        contact = detail.find("contact") if detail is not None else None
        track = detail.find("track") if detail is not None else None
        group = detail.find("__group") if detail is not None else None

        result: dict[str, Any] = {
            "uid": root.get("uid", ""),
            "type": root.get("type", ""),
            "time": root.get("time", ""),
            "stale": root.get("stale", ""),
        }

        if point is not None:
            result["lat"] = float(point.get("lat", 0))
            result["lon"] = float(point.get("lon", 0))
            result["hae"] = float(point.get("hae", 0))

        if contact is not None:
            result["callsign"] = contact.get("callsign", "")

        if track is not None:
            result["speed"] = float(track.get("speed", 0))
            result["course"] = float(track.get("course", 0))

        if group is not None:
            result["team"] = group.get("name", "")
            result["role"] = group.get("role", "")

        return result

    async def _upsert_actor(self, parsed: dict[str, Any]) -> Actor:
        """Create or update an Actor from parsed CoT data."""
        callsign = parsed.get("callsign", parsed.get("uid", "UNKNOWN"))

        existing = await self._actor_repo.find_by_callsign(callsign)
        if existing:
            actor = existing
        else:
            actor = Actor(callsign=callsign)

        cot_type = parsed.get("type", "")
        actor.affiliation = self._resolve_affiliation(cot_type)
        actor.actor_type = self._resolve_actor_type(cot_type)
        actor.source = "ATAK"

        if "lat" in parsed and "lon" in parsed:
            actor.update_position(
                GeoPosition(
                    latitude=parsed["lat"],
                    longitude=parsed["lon"],
                    altitude_m=parsed.get("hae"),
                )
            )

        if "speed" in parsed:
            actor.speed_mps = parsed["speed"]
        if "course" in parsed:
            actor.course_deg = parsed["course"]

        return actor

    @staticmethod
    def _resolve_affiliation(cot_type: str) -> Affiliation:
        """Resolve MIL-STD-2525B affiliation from CoT type string.

        CoT type format: a-{affiliation}-{battle dimension}-{function}
        """
        parts = cot_type.split("-")
        if len(parts) >= 2:
            aff_map = {
                "f": Affiliation.FRIENDLY,
                "h": Affiliation.HOSTILE,
                "n": Affiliation.NEUTRAL,
                "u": Affiliation.UNKNOWN,
            }
            return aff_map.get(parts[1].lower(), Affiliation.UNKNOWN)
        return Affiliation.UNKNOWN

    @staticmethod
    def _resolve_actor_type(cot_type: str) -> ActorType:
        """Resolve actor type from CoT type string.

        Battle dimensions: G=Ground, A=Air, S=Sea, U=Subsurface
        """
        parts = cot_type.split("-")
        if len(parts) >= 3:
            dim_map = {"G": ActorType.PERSON, "A": ActorType.AIRCRAFT, "S": ActorType.VESSEL, "U": ActorType.VESSEL}
            return dim_map.get(parts[2].upper(), ActorType.UNKNOWN)
        return ActorType.UNKNOWN

    @staticmethod
    def _create_event(parsed: dict[str, Any], actor_id: UUID) -> Event:
        """Create an Event entity from parsed CoT data."""
        position = None
        if "lat" in parsed and "lon" in parsed:
            position = GeoPosition(
                latitude=parsed["lat"],
                longitude=parsed["lon"],
                altitude_m=parsed.get("hae"),
            )

        return Event(
            event_type=EventType.OBSERVATION,
            location=position,
            description=f"CoT event: {parsed.get('type', 'unknown')}",
            confidence=Confidence.HIGH,
            source="ATAK",
            actor_ids=[actor_id],
            metadata=parsed,
        )
