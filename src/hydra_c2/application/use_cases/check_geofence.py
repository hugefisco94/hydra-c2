"""Application Use Case: Detect geofence breaches for actor positions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import structlog

from hydra_c2.domain.entities.actor import GeoPosition
from hydra_c2.domain.entities.event import Confidence, Event, EventType
from hydra_c2.domain.interfaces.messaging import MessagePublisher
from hydra_c2.domain.interfaces.repositories import EventRepository, GeofenceRepository

logger = structlog.get_logger(__name__)


@dataclass
class CheckGeofenceResult:
    """Result of geofence breach evaluation."""

    actor_id: UUID | None = None
    breached_geofences: list[dict[str, object]] = field(default_factory=list)
    breach_event_id: UUID | None = None
    success: bool = True
    error: str | None = None


class CheckGeofenceUseCase:
    """Check actor position against active geofences and emit alerts."""

    def __init__(
        self,
        geofence_repo: GeofenceRepository,
        event_repo: EventRepository,
        publisher: MessagePublisher,
    ) -> None:
        self._geofence_repo: GeofenceRepository = geofence_repo
        self._event_repo: EventRepository = event_repo
        self._publisher: MessagePublisher = publisher

    async def execute(self, actor_id: UUID, position: GeoPosition) -> CheckGeofenceResult:
        """Evaluate one actor position for geofence breaches."""
        try:
            breached = [dict(item) for item in await self._geofence_repo.check_breach(position)]
            if not breached:
                logger.info("geofence_clear", actor_id=str(actor_id))
                return CheckGeofenceResult(actor_id=actor_id, breached_geofences=[])

            event = Event(
                event_type=EventType.GEOFENCE_BREACH,
                timestamp=datetime.now(UTC),
                location=position,
                description="Actor entered breached geofence boundary",
                confidence=Confidence.HIGH,
                source="GEOFENCE",
                actor_ids=[actor_id],
                metadata={"breached_geofences": breached},
            )
            await self._event_repo.save(event)

            await self._publisher.publish(
                "hydra/event/geofence_breach",
                {
                    "event_id": str(event.id),
                    "event_type": event.event_type.value,
                    "actor_id": str(actor_id),
                    "position": {
                        "latitude": position.latitude,
                        "longitude": position.longitude,
                        "altitude_m": position.altitude_m,
                    },
                    "breached_geofences": breached,
                    "timestamp": event.timestamp.isoformat(),
                },
            )

            logger.info(
                "geofence_breach_detected",
                actor_id=str(actor_id),
                breach_count=len(breached),
                event_id=str(event.id),
            )
            return CheckGeofenceResult(
                actor_id=actor_id,
                breached_geofences=breached,
                breach_event_id=event.id,
            )
        except Exception as exc:
            logger.exception("geofence_check_failed", actor_id=str(actor_id), error=str(exc))
            return CheckGeofenceResult(actor_id=actor_id, success=False, error=str(exc))
