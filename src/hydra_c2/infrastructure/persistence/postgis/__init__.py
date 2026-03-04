"""PostGIS persistence adapters for HYDRA-C2."""

from __future__ import annotations

from hydra_c2.infrastructure.persistence.postgis.connection import (
    dispose_engine,
    get_engine,
    get_session,
    get_session_factory,
)
from hydra_c2.infrastructure.persistence.postgis.models import (
    ActorModel,
    Base,
    EventModel,
    GeofenceModel,
    TransmissionModel,
)
from hydra_c2.infrastructure.persistence.postgis.repository import (
    PostGISActorRepository,
    PostGISEventRepository,
    PostGISGeofenceRepository,
    PostGISTransmissionRepository,
)

__all__ = [
    "Base",
    "ActorModel",
    "EventModel",
    "TransmissionModel",
    "GeofenceModel",
    "get_engine",
    "get_session_factory",
    "get_session",
    "dispose_engine",
    "PostGISActorRepository",
    "PostGISEventRepository",
    "PostGISTransmissionRepository",
    "PostGISGeofenceRepository",
]
