"""Application Use Case: Triangulate RF source from multi-station bearings."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog

from hydra_c2.domain.entities.actor import Actor, ActorType, GeoPosition
from hydra_c2.domain.entities.event import Transmission
from hydra_c2.domain.interfaces.messaging import MessagePublisher
from hydra_c2.domain.interfaces.repositories import ActorRepository, TransmissionRepository

logger = structlog.get_logger(__name__)


@dataclass
class TriangulationResult:
    """Result of RF source triangulation."""

    estimated_actor_id: UUID | None = None
    estimated_position: GeoPosition | None = None
    bearings_used: int = 0
    success: bool = True
    error: str | None = None


class TriangulateSourceUseCase:
    """Estimate RF source location from bearing observations.

    Uses a 2D least-squares intersection of bearing lines in a local lat/lon
    plane approximation. Requires at least two bearing observations with
    station positions.
    """

    def __init__(
        self,
        transmission_repo: TransmissionRepository,
        actor_repo: ActorRepository,
        publisher: MessagePublisher,
    ) -> None:
        self._transmission_repo: TransmissionRepository = transmission_repo
        self._actor_repo: ActorRepository = actor_repo
        self._publisher: MessagePublisher = publisher

    async def execute(self, frequency_mhz: float, time_window_seconds: int = 300) -> TriangulationResult:
        """Triangulate source location for one RF frequency window."""
        try:
            transmissions = list(
                await self._transmission_repo.find_bearings_for_triangulation(
                    frequency_mhz,
                    time_window_seconds=time_window_seconds,
                )
            )
            lines = [t for t in transmissions if t.location is not None and t.bearing_deg is not None]
            if len(lines) < 2:
                return TriangulationResult(
                    success=False,
                    error="Need at least 2 bearing lines for triangulation",
                    bearings_used=len(lines),
                )

            estimated_position = self._least_squares_intersection(lines)

            actor = Actor(
                callsign=f"TX-{frequency_mhz:.3f}MHz",
                actor_type=ActorType.TRANSMISSION_SOURCE,
                position=estimated_position,
                source="SDR",
                first_seen=datetime.now(UTC),
                last_seen=datetime.now(UTC),
                metadata={
                    "frequency_mhz": frequency_mhz,
                    "time_window_seconds": time_window_seconds,
                    "bearings_used": len(lines),
                },
            )
            await self._actor_repo.save(actor)

            await self._publisher.publish(
                "hydra/sdr/triangulation",
                {
                    "actor_id": str(actor.id),
                    "frequency_mhz": frequency_mhz,
                    "time_window_seconds": time_window_seconds,
                    "estimated_position": {
                        "latitude": estimated_position.latitude,
                        "longitude": estimated_position.longitude,
                        "altitude_m": estimated_position.altitude_m,
                    },
                    "bearings_used": len(lines),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            logger.info(
                "triangulation_completed",
                actor_id=str(actor.id),
                frequency_mhz=frequency_mhz,
                bearings_used=len(lines),
            )
            return TriangulationResult(
                estimated_actor_id=actor.id,
                estimated_position=estimated_position,
                bearings_used=len(lines),
            )
        except Exception as exc:
            logger.exception("triangulation_failed", error=str(exc), frequency_mhz=frequency_mhz)
            return TriangulationResult(success=False, error=str(exc))

    @staticmethod
    def _least_squares_intersection(transmissions: list[Transmission]) -> GeoPosition:
        """Compute least-squares line intersection in a local 2D plane."""
        sum_a11 = 0.0
        sum_a12 = 0.0
        sum_a22 = 0.0
        sum_b1 = 0.0
        sum_b2 = 0.0

        for transmission in transmissions:
            position = transmission.location
            bearing = transmission.bearing_deg
            if position is None or bearing is None:
                continue

            theta = math.radians(bearing)
            nx = math.cos(theta)
            ny = -math.sin(theta)
            c = nx * position.longitude + ny * position.latitude

            sum_a11 += nx * nx
            sum_a12 += nx * ny
            sum_a22 += ny * ny
            sum_b1 += c * nx
            sum_b2 += c * ny

        determinant = (sum_a11 * sum_a22) - (sum_a12 * sum_a12)
        if abs(determinant) < 1e-9:
            raise ValueError("Bearing geometry is degenerate for triangulation")

        lon = ((sum_b1 * sum_a22) - (sum_b2 * sum_a12)) / determinant
        lat = ((sum_a11 * sum_b2) - (sum_a12 * sum_b1)) / determinant
        return GeoPosition(latitude=lat, longitude=lon)
