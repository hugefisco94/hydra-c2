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
from typing import Any, Optional

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

    # L0 – KrakenSDR Radio Direction Finding
    _kraken_adapter: Optional[Any] = field(default=None, init=False)
    # L1 – TAK/CoT Client
    _tak_client: Optional[Any] = field(default=None, init=False)
    # L2 – Meshtastic LoRa Mesh
    _meshtastic_adapter: Optional[Any] = field(default=None, init=False)
    # L5 – ML Analytics Engine
    _ml_engine: Optional[Any] = field(default=None, init=False)

    # L3 – Intelligence Retrieval (ColBERT MaxSim + OSINT + Kill Web Fusion)
    _intel_retriever: Optional[Any] = field(default=None, init=False)
    _intel_collector: Optional[Any] = field(default=None, init=False)
    _intel_fusion: Optional[Any] = field(default=None, init=False)
    # L4 – OODA Decision Engine (Boyd Loop + In-Context Co-player Inference)
    _co_player_engine: Optional[Any] = field(default=None, init=False)
    _ooda_engine: Optional[Any] = field(default=None, init=False)
    # L6 – Harness Orchestration (Utah/Inngest think → act → observe)
    _harness: Optional[Any] = field(default=None, init=False)

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

        # --- L0: KrakenSDR ---
        from hydra_c2.infrastructure.sdr.kraken import KrakenSdrAdapter

        self._kraken_adapter = KrakenSdrAdapter(
            host=getattr(self.settings, "kraken_host", "127.0.0.1"),
            port=getattr(self.settings, "kraken_port", 8081),
            station_lat=getattr(self.settings, "station_lat", None),
            station_lon=getattr(self.settings, "station_lon", None),
            publisher=self._publisher,
            use_mock=getattr(self.settings, "kraken_mock", True),
        )
        await self._kraken_adapter.connect()
        logger.info("kraken_sdr_initialized")

        # --- L1: TAK Client ---
        from hydra_c2.infrastructure.tak.client import TakClientFactory

        self._tak_client = TakClientFactory.create(
            self.settings.tak,
            publisher=self._publisher,
        )
        await self._tak_client.connect()
        logger.info("tak_client_initialized", protocol=self.settings.tak.protocol)

        # --- L2: Meshtastic ---
        from hydra_c2.infrastructure.mesh.meshtastic import MeshtasticAdapter

        self._meshtastic_adapter = MeshtasticAdapter(
            connection_type=getattr(self.settings, "meshtastic_connection", "mock"),
            publisher=self._publisher,
        )
        await self._meshtastic_adapter.connect()
        logger.info("meshtastic_initialized")

        # --- L5: ML Analytics ---
        from hydra_c2.infrastructure.analytics.ml import MlAnalyticsEngine

        self._ml_engine = MlAnalyticsEngine(
            publisher=self._publisher,
            enable_llm=getattr(self.settings, "enable_llm_analytics", True),
            do_gpu_host=self.settings.do_gpu_host,
        )
        await self._ml_engine.start()
        logger.info("ml_analytics_initialized")

        # --- L3: Intelligence Retrieval (ColBERT MaxSim + OSINT) ---
        from hydra_c2.infrastructure.intelligence import create_intelligence_layer

        (
            self._intel_retriever,
            self._intel_collector,
            self._intel_fusion,
        ) = create_intelligence_layer()
        logger.info("intelligence_layer_initialized")

        # --- L4: OODA Decision Engine (Boyd Loop + Co-player Inference) ---
        from hydra_c2.infrastructure.ooda import create_ooda_layer

        self._co_player_engine, self._ooda_engine = create_ooda_layer(
            collector=self._intel_collector,
            fusion=self._intel_fusion,
        )
        logger.info("ooda_engine_initialized")

        # --- L6: Harness Orchestration (Utah/Inngest think → act → observe) ---
        from hydra_c2.infrastructure.harness import create_harness_layer

        self._harness = create_harness_layer(
            ooda_engine=self._ooda_engine,
            max_iterations=getattr(self.settings, "harness_max_iterations", 50),
        )
        logger.info("harness_initialized")

        logger.info("container_started")

    async def shutdown(self) -> None:
        """Gracefully shutdown all infrastructure connections."""
        logger.info("container_shutting_down")

        if self._ml_engine:
            await self._ml_engine.stop()
        if self._meshtastic_adapter:
            await self._meshtastic_adapter.disconnect()
        if self._tak_client:
            await self._tak_client.disconnect()
        if self._kraken_adapter:
            await self._kraken_adapter.disconnect()
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

    # --- New adapter accessors ---

    @property
    def kraken_adapter(self) -> Any:
        assert self._kraken_adapter is not None, "Container not started"
        return self._kraken_adapter

    @property
    def tak_client(self) -> Any:
        assert self._tak_client is not None, "Container not started"
        return self._tak_client

    @property
    def meshtastic_adapter(self) -> Any:
        assert self._meshtastic_adapter is not None, "Container not started"
        return self._meshtastic_adapter

    @property
    def ml_engine(self) -> Any:
        assert self._ml_engine is not None, "Container not started"
        return self._ml_engine

    @property
    def intel_collector(self) -> Any:
        """L3: OSINT intelligence collector (ColBERT MaxSim index)."""
        assert self._intel_collector is not None, "Container not started"
        return self._intel_collector

    @property
    def intel_fusion(self) -> Any:
        """L3: Kill Web intelligence fusion (multi-source confidence aggregation)."""
        assert self._intel_fusion is not None, "Container not started"
        return self._intel_fusion

    @property
    def ooda_engine(self) -> Any:
        """L4: OODA decision engine (Boyd Loop + in-context co-player inference)."""
        assert self._ooda_engine is not None, "Container not started"
        return self._ooda_engine

    @property
    def co_player_engine(self) -> Any:
        """L4: In-context co-player inference engine (arXiv:2602.16301)."""
        assert self._co_player_engine is not None, "Container not started"
        return self._co_player_engine

    @property
    def harness(self) -> Any:
        """L6: Utah/Inngest harness orchestration (think → act → observe)."""
        assert self._harness is not None, "Container not started"
        return self._harness

    # --- Use case factories ---

    def ingest_cot_use_case(self) -> "IngestCotUseCase":
        """Create CoT ingestion use case with wired dependencies."""
        from hydra_c2.application.use_cases.ingest_cot import IngestCotUseCase

        return IngestCotUseCase(
            actor_repo=self.actor_repo,
            event_repo=self.event_repo,
            publisher=self.publisher,
        )
