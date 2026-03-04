"""Domain Entity: Actor — Core entity in the HYDRA-C2 knowledge graph.

An Actor represents any entity observed in the operational environment:
friendly forces, hostile elements, neutral civilians, or unknown contacts.
This is the central node in Neo4j's property graph model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class Affiliation(str, Enum):
    """MIL-STD-2525B standard affiliations."""

    FRIENDLY = "FRIENDLY"
    HOSTILE = "HOSTILE"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class ActorType(str, Enum):
    """Classification of observed actors."""

    PERSON = "PERSON"
    VEHICLE = "VEHICLE"
    AIRCRAFT = "AIRCRAFT"
    VESSEL = "VESSEL"
    UAV = "UAV"
    EQUIPMENT = "EQUIPMENT"
    UNIT = "UNIT"
    TRANSMISSION_SOURCE = "TRANSMISSION_SOURCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GeoPosition:
    """WGS84 geographic position (value object)."""

    latitude: float
    longitude: float
    altitude_m: Optional[float] = None

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"Invalid latitude: {self.latitude}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"Invalid longitude: {self.longitude}")

    def to_wkt(self) -> str:
        """Convert to Well-Known Text for PostGIS."""
        if self.altitude_m is not None:
            return f"POINTZ({self.longitude} {self.latitude} {self.altitude_m})"
        return f"POINT({self.longitude} {self.latitude})"


@dataclass
class Actor:
    """Core domain entity representing an observed actor."""

    id: UUID = field(default_factory=uuid4)
    callsign: str = ""
    actor_type: ActorType = ActorType.UNKNOWN
    affiliation: Affiliation = Affiliation.UNKNOWN
    position: Optional[GeoPosition] = None
    speed_mps: Optional[float] = None
    course_deg: Optional[float] = None
    source: str = "MANUAL"  # ATAK | MESH | SDR | MANUAL
    first_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    confidence: float = 0.5  # 0.0 ~ 1.0
    metadata: dict = field(default_factory=dict)

    def update_position(self, position: GeoPosition, timestamp: Optional[datetime] = None) -> None:
        """Update actor's last known position."""
        self.position = position
        self.last_seen = timestamp or datetime.now(UTC)

    def is_stale(self, max_age_seconds: int = 3600) -> bool:
        """Check if actor data is stale."""
        age = (datetime.now(UTC) - self.last_seen).total_seconds()
        return age > max_age_seconds

    @property
    def mil_std_2525b_sidc(self) -> str:
        """Generate a basic MIL-STD-2525B Symbol Identification Code."""
        affiliation_map = {
            Affiliation.FRIENDLY: "F",
            Affiliation.HOSTILE: "H",
            Affiliation.NEUTRAL: "N",
            Affiliation.UNKNOWN: "U",
        }
        return f"S{affiliation_map[self.affiliation]}GP------"
