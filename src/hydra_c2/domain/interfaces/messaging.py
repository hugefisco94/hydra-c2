"""Domain Interface: Messaging contracts for event-driven architecture.

Defines the pub/sub contracts for Layer 3 (Data Ingestion).
Infrastructure implementations: MQTT (Mosquitto), Kafka (optional).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine


class MessagePublisher(ABC):
    """Contract for publishing messages to the event bus."""

    @abstractmethod
    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a message to a topic.

        Topic convention:
            hydra/cot/{type}     — CoT events (PLI, markers, alerts)
            hydra/sdr/rdf        — KrakenSDR bearing data
            hydra/sdr/adsb       — ADS-B aircraft tracks
            hydra/sdr/ais        — AIS vessel positions
            hydra/sdr/spectrum   — Spectrum waterfall data
            hydra/mesh/{node_id} — Meshtastic node status
            hydra/event/{type}   — System events
        """
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the message broker."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the message broker."""
        ...


MessageHandler = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class MessageSubscriber(ABC):
    """Contract for subscribing to messages from the event bus."""

    @abstractmethod
    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to a topic with a message handler.

        Supports MQTT wildcards:
            hydra/sdr/#    — All SDR topics
            hydra/cot/+    — All CoT event types
        """
        ...

    @abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the message broker."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the message broker."""
        ...
