"""Domain Interface: Repository contracts (Dependency Inversion Principle).

These abstract interfaces define the persistence contracts that infrastructure
implementations (PostGIS, Neo4j) must fulfill. The domain layer NEVER depends
on concrete database implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from hydra_c2.domain.entities.actor import Actor, GeoPosition
from hydra_c2.domain.entities.event import Event, Transmission


class ActorRepository(ABC):
    """Contract for Actor persistence (PostGIS + Neo4j dual-write)."""

    @abstractmethod
    async def save(self, actor: Actor) -> None:
        """Persist an actor to both spatial and graph stores."""
        ...

    @abstractmethod
    async def find_by_id(self, actor_id: UUID) -> Optional[Actor]:
        """Retrieve actor by unique identifier."""
        ...

    @abstractmethod
    async def find_by_callsign(self, callsign: str) -> Optional[Actor]:
        """Retrieve actor by tactical callsign."""
        ...

    @abstractmethod
    async def find_within_radius(self, center: GeoPosition, radius_meters: float) -> Sequence[Actor]:
        """Spatial query: find all actors within radius of a point (PostGIS)."""
        ...

    @abstractmethod
    async def find_co_located(
        self, actor_id: UUID, time_window_seconds: int = 7200, distance_meters: float = 100.0
    ) -> Sequence[Actor]:
        """Graph query: find actors co-located within time window (Neo4j)."""
        ...

    @abstractmethod
    async def find_network(self, actor_id: UUID, max_depth: int = 3) -> Sequence[Actor]:
        """Graph traversal: find actors connected through relationships (Neo4j)."""
        ...


class EventRepository(ABC):
    """Contract for Event persistence."""

    @abstractmethod
    async def save(self, event: Event) -> None:
        """Persist an event."""
        ...

    @abstractmethod
    async def find_by_id(self, event_id: UUID) -> Optional[Event]:
        """Retrieve event by unique identifier."""
        ...

    @abstractmethod
    async def find_in_area(
        self,
        center: GeoPosition,
        radius_meters: float,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Sequence[Event]:
        """Spatiotemporal query: events in area within time range."""
        ...

    @abstractmethod
    async def find_by_actor(self, actor_id: UUID) -> Sequence[Event]:
        """Find all events involving a specific actor."""
        ...


class TransmissionRepository(ABC):
    """Contract for RF Transmission persistence (SDR Layer 0 data)."""

    @abstractmethod
    async def save(self, transmission: Transmission) -> None:
        """Persist a detected transmission."""
        ...

    @abstractmethod
    async def find_by_frequency(self, freq_mhz: float, tolerance_mhz: float = 0.025) -> Sequence[Transmission]:
        """Find transmissions on a specific frequency."""
        ...

    @abstractmethod
    async def find_bearings_for_triangulation(
        self, freq_mhz: float, time_window_seconds: int = 300
    ) -> Sequence[Transmission]:
        """Find bearing data suitable for triangulation (KrakenSDR multi-station)."""
        ...


class GeofenceRepository(ABC):
    """Contract for Geofence management (PostGIS)."""

    @abstractmethod
    async def check_breach(self, position: GeoPosition) -> Sequence[dict]:
        """Check if position intersects any active geofence."""
        ...

    @abstractmethod
    async def create_geofence(self, name: str, polygon_wkt: str, fence_type: str = "ALERT") -> UUID:
        """Create a new geofence polygon."""
        ...
