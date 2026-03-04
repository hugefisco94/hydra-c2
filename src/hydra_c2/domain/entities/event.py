"""Domain Entity: Event — Observed events in the operational environment.

Events capture discrete occurrences: observations, transmissions, movements,
incidents. They form the temporal backbone of the knowledge graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from hydra_c2.domain.entities.actor import GeoPosition


class EventType(str, Enum):
    """Classification of operational events."""

    OBSERVATION = "OBSERVATION"
    TRANSMISSION = "TRANSMISSION"
    MOVEMENT = "MOVEMENT"
    INCIDENT = "INCIDENT"
    GEOFENCE_BREACH = "GEOFENCE_BREACH"
    RF_ANOMALY = "RF_ANOMALY"
    COMMS_INTERCEPT = "COMMS_INTERCEPT"


class Confidence(str, Enum):
    """Intelligence confidence levels."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class Event:
    """Domain entity representing an observed event."""

    id: UUID = field(default_factory=uuid4)
    event_type: EventType = EventType.OBSERVATION
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    location: Optional[GeoPosition] = None
    description: str = ""
    confidence: Confidence = Confidence.MEDIUM
    source: str = "MANUAL"
    actor_ids: list[UUID] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def involves_actor(self, actor_id: UUID) -> bool:
        """Check if a specific actor is involved in this event."""
        return actor_id in self.actor_ids

    def add_actor(self, actor_id: UUID) -> None:
        """Associate an actor with this event."""
        if actor_id not in self.actor_ids:
            self.actor_ids.append(actor_id)


@dataclass
class Transmission:
    """Domain entity for RF transmission events (Layer 0 → Layer 4)."""

    id: UUID = field(default_factory=uuid4)
    frequency_mhz: float = 0.0
    bandwidth_khz: Optional[float] = None
    power_dbm: Optional[float] = None
    modulation: str = "UNKNOWN"
    bearing_deg: Optional[float] = None  # DoA from KrakenSDR
    location: Optional[GeoPosition] = None  # Estimated source position
    source_sdr: str = "UNKNOWN"  # KRAKEN | RTLSDR | HACKRF
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)

    @property
    def is_direction_finding(self) -> bool:
        """Check if this transmission has bearing data (KrakenSDR RDF)."""
        return self.bearing_deg is not None
