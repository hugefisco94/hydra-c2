"""Infrastructure: MQTT Client implementation (Mosquitto).

Layer 3: Data Ingestion — Central message hub for HYDRA-C2.
Implements the domain MessagePublisher and MessageSubscriber interfaces.
"""

from __future__ import annotations

import json
import asyncio
from typing import Any

import paho.mqtt.client as mqtt
import structlog

from hydra_c2.domain.interfaces.messaging import MessagePublisher, MessageSubscriber, MessageHandler

logger = structlog.get_logger()


class MqttPublisher(MessagePublisher):
    """MQTT message publisher using Mosquitto broker."""

    def __init__(self, host: str = "localhost", port: int = 1883, client_id: str = "hydra-pub") -> None:
        self._host = host
        self._port = port
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._connected = False

    async def connect(self) -> None:
        """Connect to MQTT broker."""
        loop = asyncio.get_event_loop()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        await loop.run_in_executor(None, self._client.connect, self._host, self._port)
        self._client.loop_start()
        logger.info("mqtt_publisher_connected", host=self._host, port=self._port)

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
        logger.info("mqtt_publisher_disconnected")

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish JSON payload to MQTT topic."""
        if not self._connected:
            logger.warning("mqtt_publish_not_connected", topic=topic)
            return

        message = json.dumps(payload, default=str)
        result = self._client.publish(topic, message, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("mqtt_publish_failed", topic=topic, rc=result.rc)
        else:
            logger.debug("mqtt_published", topic=topic, size=len(message))

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        self._connected = True
        logger.info("mqtt_connected", rc=rc)

    def _on_disconnect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        self._connected = False
        logger.warning("mqtt_disconnected", rc=rc)


class MqttSubscriber(MessageSubscriber):
    """MQTT message subscriber using Mosquitto broker."""

    def __init__(self, host: str = "localhost", port: int = 1883, client_id: str = "hydra-sub") -> None:
        self._host = host
        self._port = port
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._handlers: dict[str, MessageHandler] = {}
        self._connected = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> None:
        """Connect to MQTT broker."""
        self._loop = asyncio.get_event_loop()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        await self._loop.run_in_executor(None, self._client.connect, self._host, self._port)
        self._client.loop_start()
        logger.info("mqtt_subscriber_connected", host=self._host, port=self._port)

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
        logger.info("mqtt_subscriber_disconnected")

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to topic with async handler."""
        self._handlers[topic] = handler
        self._client.subscribe(topic, qos=1)
        logger.info("mqtt_subscribed", topic=topic)

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from topic."""
        self._client.unsubscribe(topic)
        self._handlers.pop(topic, None)
        logger.info("mqtt_unsubscribed", topic=topic)

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        self._connected = True
        for topic in self._handlers:
            client.subscribe(topic, qos=1)
        logger.info("mqtt_subscriber_reconnected", topics=list(self._handlers.keys()))

    def _on_message(self, client: Any, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Route incoming messages to registered handlers."""
        if self._loop is None:
            return

        try:
            payload = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("mqtt_invalid_payload", topic=msg.topic)
            return

        for pattern, handler in self._handlers.items():
            if mqtt.topic_matches_sub(pattern, msg.topic):
                asyncio.run_coroutine_threadsafe(handler(msg.topic, payload), self._loop)

    def _on_disconnect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        self._connected = False
        logger.warning("mqtt_subscriber_disconnected", rc=rc)
