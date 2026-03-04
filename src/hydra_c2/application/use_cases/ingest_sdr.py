"""Application Use Case: Ingest SDR transmission observations.

This use case handles Layer 0 SDR ingestion, including KrakenSDR RDF (bearing)
signals, persistence, MQTT publication, and RF anomaly triggering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog

from hydra_c2.domain.entities.actor import GeoPosition
from hydra_c2.domain.entities.event import Confidence, Event, EventType, Transmission
from hydra_c2.domain.interfaces.messaging import MessagePublisher
from hydra_c2.domain.interfaces.repositories import EventRepository, TransmissionRepository

logger = structlog.get_logger(__name__)


@dataclass
class IngestSdrResult:
    """Result of SDR transmission ingestion."""

    transmission_id: UUID | None = None
    anomaly_event_id: UUID | None = None
    anomaly_detected: bool = False
    success: bool = True
    error: str | None = None


class IngestSdrUseCase:
    """Ingest one SDR signal sample and route it through application workflows.

    Workflow:
    1. Create a ``Transmission`` domain entity from raw SDR observation data.
    2. Persist through ``TransmissionRepository``.
    3. Publish payload to MQTT for downstream consumers.
    4. Trigger RF anomaly event when power exceeds configured threshold.
    """

    def __init__(
        self,
        transmission_repo: TransmissionRepository,
        event_repo: EventRepository,
        publisher: MessagePublisher,
        anomaly_threshold_dbm: float = -45.0,
    ) -> None:
        self._transmission_repo: TransmissionRepository = transmission_repo
        self._event_repo: EventRepository = event_repo
        self._publisher: MessagePublisher = publisher
        self._anomaly_threshold_dbm: float = anomaly_threshold_dbm

    async def execute(
        self,
        frequency_mhz: float,
        power_dbm: float | None,
        modulation: str,
        bearing_deg: float | None,
        source_sdr: str,
        location: GeoPosition | None,
    ) -> IngestSdrResult:
        """Ingest an SDR observation and emit integration events."""
        try:
            transmission = Transmission(
                frequency_mhz=frequency_mhz,
                power_dbm=power_dbm,
                modulation=modulation,
                bearing_deg=bearing_deg,
                source_sdr=source_sdr,
                location=location,
                timestamp=datetime.now(UTC),
            )

            await self._transmission_repo.save(transmission)

            await self._publisher.publish(
                "hydra/sdr/rdf",
                {
                    "transmission_id": str(transmission.id),
                    "frequency_mhz": transmission.frequency_mhz,
                    "power_dbm": transmission.power_dbm,
                    "modulation": transmission.modulation,
                    "bearing_deg": transmission.bearing_deg,
                    "source_sdr": transmission.source_sdr,
                    "is_rdf": transmission.is_direction_finding,
                    "location": self._serialize_position(transmission.location),
                    "timestamp": transmission.timestamp.isoformat(),
                },
            )

            anomaly_event_id: UUID | None = None
            anomaly_detected = self._is_anomaly(power_dbm)
            if anomaly_detected:
                anomaly_event = Event(
                    event_type=EventType.RF_ANOMALY,
                    timestamp=datetime.now(UTC),
                    location=location,
                    description="RF anomaly detected from SDR ingestion threshold rule",
                    confidence=Confidence.MEDIUM,
                    source=source_sdr,
                    metadata={
                        "frequency_mhz": frequency_mhz,
                        "power_dbm": power_dbm,
                        "modulation": modulation,
                        "bearing_deg": bearing_deg,
                        "threshold_dbm": self._anomaly_threshold_dbm,
                    },
                )
                await self._event_repo.save(anomaly_event)
                anomaly_event_id = anomaly_event.id

                await self._publisher.publish(
                    "hydra/event/rf_anomaly",
                    {
                        "event_id": str(anomaly_event.id),
                        "event_type": anomaly_event.event_type.value,
                        "frequency_mhz": frequency_mhz,
                        "power_dbm": power_dbm,
                        "threshold_dbm": self._anomaly_threshold_dbm,
                        "source_sdr": source_sdr,
                        "timestamp": anomaly_event.timestamp.isoformat(),
                    },
                )

            logger.info(
                "sdr_ingested",
                transmission_id=str(transmission.id),
                source_sdr=source_sdr,
                frequency_mhz=frequency_mhz,
                anomaly_detected=anomaly_detected,
            )

            return IngestSdrResult(
                transmission_id=transmission.id,
                anomaly_event_id=anomaly_event_id,
                anomaly_detected=anomaly_detected,
            )
        except Exception as exc:
            logger.exception("sdr_ingest_failed", error=str(exc))
            return IngestSdrResult(success=False, error=str(exc))

    def _is_anomaly(self, power_dbm: float | None) -> bool:
        """Return whether a power reading exceeds the anomaly threshold."""
        return power_dbm is not None and power_dbm >= self._anomaly_threshold_dbm

    @staticmethod
    def _serialize_position(position: GeoPosition | None) -> dict[str, float] | None:
        """Serialize position value object for message payloads."""
        if position is None:
            return None
        payload: dict[str, float] = {
            "latitude": position.latitude,
            "longitude": position.longitude,
        }
        if position.altitude_m is not None:
            payload["altitude_m"] = position.altitude_m
        return payload
