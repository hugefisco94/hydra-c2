"""HYDRA-C2 Dependency Injection Container.

Central composition root that wires infrastructure implementations
to domain interfaces. Follows Clean Architecture: this is the ONLY
place where concrete classes are imported and composed.

Usage:
    container = Container(get_settings())
    await container.startup()
    use_case = container.ingest_cot_use_case()
    ...
    await container.shutdown()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

from hydra_c2.config import Settings
from hydra_c2.domain.interfaces.messaging import MessagePublisher, MessageSubscriber
from hydra_c2.domain.interfaces.repositories import (
    ActorRepository,
    EventRepository,
    GeofenceRepository,
    TransmissionRepository,
)

logger = structlog.get_logger()


@dataclass
class Container:
    """Dependency injection container — composition root.

    Initializes all infrastructure components and provides
    factory methods for use cases with pre-wired dependencies.
    """

    settings: Settings

    # Infrastructure instances (initialized on startup)
    _actor_repo: Optional[ActorRepository] = field(default=None, init=False)
    _event_repo: Optional[EventRepository] = field(default=None, init=False)
    _transmission_repo: Optional[TransmissionRepository] = field(default=None, init=False)
    _geofence_repo: Optional[GeofenceRepository] = field(default=None, init=False)
    _publisher: Optional[MessagePublisher] = field(default=None, init=False)
    _subscriber: Optional[MessageSubscriber] = field(default=None, init=False)

    async def startup(self) -> None:
        """Initialize all infrastructure connections."""
        logger.info("container_starting", app=self.settings.app_name)

        # --- PostGIS repositories ---
        from hydra_c2.infrastructure.persistence.postgis.connection import get_engine, get_session_factory
        from hydra_c2.infrastructure.persistence.postgis.repository import (
            PostGISActorRepository,
            PostGISEventRepository,
            PostGISGeofenceRepository,
            PostGISTransmissionRepository,
        )

        session_factory = get_session_factory(self.settings)
        self._actor_repo = PostGISActorRepository(session_factory)
        self._event_repo = PostGISEventRepository(session_factory)
        self._transmission_repo = PostGISTransmissionRepository(session_factory)
        self._geofence_repo = PostGISGeofenceRepository(session_factory)
        logger.info("postgis_initialized", host=self.settings.postgis.host)

        # --- Neo4j graph service ---
        from hydra_c2.infrastructure.persistence.neo4j.connection import create_neo4j_driver
        from hydra_c2.infrastructure.persistence.neo4j.graph_service import Neo4jGraphService

        neo4j_driver = create_neo4j_driver(self.settings.neo4j)
        self._graph_service = Neo4jGraphService(neo4j_driver)
        logger.info("neo4j_initialized", uri=self.settings.neo4j.uri)

        # --- MQTT messaging ---
        from hydra_c2.infrastructure.messaging.mqtt.client import MqttPublisher, MqttSubscriber

        self._publisher = MqttPublisher(
            host=self.settings.mqtt.host,
            port=self.settings.mqtt.port,
        )
        self._subscriber = MqttSubscriber(
            host=self.settings.mqtt.host,
            port=self.settings.mqtt.port,
        )
        await self._publisher.connect()
        await self._subscriber.connect()
        logger.info("mqtt_initialized", host=self.settings.mqtt.host)

        logger.info("container_started")

    async def shutdown(self) -> None:
        """Gracefully shutdown all infrastructure connections."""
        logger.info("container_shutting_down")

        if self._publisher:
            await self._publisher.disconnect()
        if self._subscriber:
            await self._subscriber.disconnect()

        logger.info("container_shutdown_complete")

    # --- Repository accessors ---

    @property
    def actor_repo(self) -> ActorRepository:
        """Get the actor repository."""
        assert self._actor_repo is not None, "Container not started"
        return self._actor_repo

    @property
    def event_repo(self) -> EventRepository:
        """Get the event repository."""
        assert self._event_repo is not None, "Container not started"
        return self._event_repo

    @property
    def transmission_repo(self) -> TransmissionRepository:
        """Get the transmission repository."""
        assert self._transmission_repo is not None, "Container not started"
        return self._transmission_repo

    @property
    def geofence_repo(self) -> GeofenceRepository:
        """Get the geofence repository."""
        assert self._geofence_repo is not None, "Container not started"
        return self._geofence_repo

    @property
    def publisher(self) -> MessagePublisher:
        """Get the message publisher."""
        assert self._publisher is not None, "Container not started"
        return self._publisher

    @property
    def subscriber(self) -> MessageSubscriber:
        """Get the message subscriber."""
        assert self._subscriber is not None, "Container not started"
        return self._subscriber

    # --- Use case factories ---

    def ingest_cot_use_case(self) -> "IngestCotUseCase":
        """Create CoT ingestion use case with wired dependencies."""
        from hydra_c2.application.use_cases.ingest_cot import IngestCotUseCase

        return IngestCotUseCase(
            actor_repo=self.actor_repo,
            event_repo=self.event_repo,
            publisher=self.publisher,
        )
