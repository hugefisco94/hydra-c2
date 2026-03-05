"""Infrastructure: Meshtastic LoRa mesh network adapter.

Layer 3: Data Ingestion — LoRa mesh overlay for HYDRA-C2.
Decodes position, nodeinfo, and telemetry packets from Meshtastic devices.
Converts mesh nodes to Actor domain entities and publishes to MQTT.

Connection modes:
    serial  — direct USB/UART connection (/dev/ttyUSB0, COM3, etc.)
    tcp     — TCP/IP connection to a Meshtastic device or proxy

MQTT topics produced:
    hydra/mesh/position    — node GPS fix with SNR/RSSI quality
    hydra/mesh/telemetry   — battery and channel utilisation metrics
    hydra/mesh/text        — received text messages
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra_c2.domain.entities.actor import (
    Actor,
    ActorType,
    Affiliation,
    GeoPosition,
)
from hydra_c2.domain.interfaces.messaging import MessagePublisher

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Optional SDK import — graceful fallback to mock when hardware unavailable
# ---------------------------------------------------------------------------
try:
    import meshtastic  # type: ignore[import-untyped]
    import meshtastic.serial_interface  # type: ignore[import-untyped]
    import meshtastic.tcp_interface  # type: ignore[import-untyped]
    from pubsub import pub  # type: ignore[import-untyped]  # meshtastic uses pypubsub

    _MESHTASTIC_AVAILABLE = True
except ImportError:
    meshtastic = None  # type: ignore[assignment]
    pub = None  # type: ignore[assignment]
    _MESHTASTIC_AVAILABLE = False
    logger.warning(
        "meshtastic_sdk_unavailable",
        message="meshtastic package not installed; falling back to MockMeshtasticInterface",
        hint="pip install meshtastic",
    )

# ---------------------------------------------------------------------------
# MQTT topic constants
# ---------------------------------------------------------------------------
TOPIC_POSITION = "hydra/mesh/position"
TOPIC_TELEMETRY = "hydra/mesh/telemetry"
TOPIC_TEXT = "hydra/mesh/text"

# Packet port numbers (Meshtastic PortNum enum values as strings)
PORTNUM_POSITION = "POSITION_APP"
PORTNUM_NODEINFO = "NODEINFO_APP"
PORTNUM_TELEMETRY = "TELEMETRY_APP"
PORTNUM_TEXT = "TEXT_MESSAGE_APP"

# SNR/RSSI → confidence thresholds
_RSSI_HIGH = -70
_RSSI_MED = -85
_RSSI_LOW = -100
_CONF_HIGH = 0.9
_CONF_MED = 0.7
_CONF_LOW = 0.5
_CONF_MINIMAL = 0.3


# ---------------------------------------------------------------------------
# Domain dataclass
# ---------------------------------------------------------------------------


@dataclass
class MeshNode:
    """Meshtastic network node — snapshot of a peer's last known state."""

    node_id: int          # 32-bit numeric node ID
    node_id_hex: str      # canonical Meshtastic form: "!12345678"
    long_name: str
    short_name: str
    hw_model: str
    position: GeoPosition | None
    battery_level: int | None
    snr: float | None
    rssi: int | None
    last_heard: datetime
    hop_count: int = 0
    voltage: float | None = None
    channel_utilization: float | None = None
    air_util_tx: float | None = None


# ---------------------------------------------------------------------------
# Mock interface — hardware-free simulation
# ---------------------------------------------------------------------------


class MockMeshtasticInterface:
    """Hardware-free Meshtastic interface for testing and development.

    Periodically emits synthetic position, nodeinfo, and telemetry packets
    via the same _on_receive callback contract as the real SDK.
    """

    # Simulated nodes seeded at construction time
    _NODE_TEMPLATES: list[dict[str, Any]] = [
        {
            "node_id": 0x11223344,
            "long_name": "ALPHA-1",
            "short_name": "A1",
            "hw_model": "TBEAM",
            "lat_base": 37.5500,
            "lon_base": 127.0400,
        },
        {
            "node_id": 0xAABBCCDD,
            "long_name": "BRAVO-2",
            "short_name": "B2",
            "hw_model": "HELTEC_V3",
            "lat_base": 37.5520,
            "lon_base": 127.0420,
        },
        {
            "node_id": 0xDEADBEEF,
            "long_name": "CHARLIE-3",
            "short_name": "C3",
            "hw_model": "RAK4631",
            "lat_base": 37.5490,
            "lon_base": 127.0380,
        },
    ]

    def __init__(self) -> None:
        self._on_receive_cb: Any | None = None
        self._running = False
        self._task: asyncio.Task[None] | None = None
        logger.info("mock_meshtastic_interface_created")

    def set_receive_callback(self, callback: Any) -> None:
        """Register the packet-receive callback."""
        self._on_receive_cb = callback

    async def start(self) -> None:
        """Begin emitting synthetic packets."""
        self._running = True
        self._task = asyncio.create_task(self._emit_loop())
        logger.info("mock_meshtastic_started")

    async def stop(self) -> None:
        """Stop packet emission."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("mock_meshtastic_stopped")

    # ------------------------------------------------------------------
    # Stub send methods matching the real SDK surface
    # ------------------------------------------------------------------

    def sendText(self, text: str, destinationId: int = 0xFFFFFFFF) -> None:  # noqa: N802
        logger.info(
            "mock_send_text",
            text=text[:80],
            destination=f"!{destinationId:08x}",
        )

    def sendPosition(  # noqa: N802
        self,
        latitude: float = 0.0,
        longitude: float = 0.0,
        altitude: int = 0,
    ) -> None:
        logger.info(
            "mock_send_position",
            lat=latitude,
            lon=longitude,
            alt=altitude,
        )

    def close(self) -> None:
        logger.info("mock_meshtastic_closed")

    # ------------------------------------------------------------------
    # Internal simulation loop
    # ------------------------------------------------------------------

    async def _emit_loop(self) -> None:
        """Emit one packet per node every 10–15 seconds, rotating types."""
        cycle = 0
        while self._running:
            for tmpl in self._NODE_TEMPLATES:
                if not self._running:
                    break
                packet = self._build_packet(tmpl, cycle)
                if self._on_receive_cb is not None:
                    try:
                        self._on_receive_cb(packet, self)
                    except Exception:
                        logger.exception(
                            "mock_callback_error",
                            node=tmpl["long_name"],
                        )
                await asyncio.sleep(random.uniform(1.5, 3.0))  # noqa: S311

            cycle += 1
            await asyncio.sleep(random.uniform(8.0, 12.0))  # noqa: S311

    def _build_packet(self, tmpl: dict[str, Any], cycle: int) -> dict[str, Any]:
        """Build a synthetic MeshPacket matching real SDK structure."""
        node_id: int = tmpl["node_id"]
        snr = round(random.uniform(4.0, 12.0), 2)  # noqa: S311
        rssi = random.randint(-95, -60)  # noqa: S311
        packet_type = cycle % 3  # rotate: 0=position, 1=nodeinfo, 2=telemetry

        base: dict[str, Any] = {
            "from": node_id,
            "to": 0xFFFFFFFF,
            "rxSnr": snr,
            "rxRssi": rssi,
            "hopLimit": random.randint(1, 5),  # noqa: S311
        }

        if packet_type == 0:
            # Position packet
            lat_jitter = random.uniform(-0.002, 0.002)  # noqa: S311
            lon_jitter = random.uniform(-0.002, 0.002)  # noqa: S311
            lat = tmpl["lat_base"] + lat_jitter
            lon = tmpl["lon_base"] + lon_jitter
            base["decoded"] = {
                "portnum": PORTNUM_POSITION,
                "position": {
                    "latitude_i": int(lat * 1e7),
                    "longitude_i": int(lon * 1e7),
                    "altitude": random.randint(20, 200),  # noqa: S311
                    "time": int(time.time()),
                },
            }

        elif packet_type == 1:
            # NodeInfo packet
            base["decoded"] = {
                "portnum": PORTNUM_NODEINFO,
                "user": {
                    "id": f"!{node_id:08x}",
                    "longName": tmpl["long_name"],
                    "shortName": tmpl["short_name"],
                    "hwModel": tmpl["hw_model"],
                },
            }

        else:
            # Telemetry packet
            base["decoded"] = {
                "portnum": PORTNUM_TELEMETRY,
                "telemetry": {
                    "deviceMetrics": {
                        "batteryLevel": random.randint(40, 100),  # noqa: S311
                        "voltage": round(random.uniform(3.7, 4.2), 2),  # noqa: S311
                        "channelUtilization": round(random.uniform(0.05, 0.25), 4),  # noqa: S311
                        "airUtilTx": round(random.uniform(0.01, 0.10), 4),  # noqa: S311
                    }
                },
            }

        return base


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------


class MeshtasticAdapter:
    """Meshtastic LoRa mesh network adapter.

    Connects to a Meshtastic device via serial or TCP.
    Decodes position, nodeinfo, and telemetry packets from the mesh.
    Converts mesh nodes to Actor domain entities and publishes to MQTT.

    When the meshtastic SDK is unavailable, falls back automatically to
    MockMeshtasticInterface so the rest of the system continues to function.

    Args:
        connection_type:  "serial" or "tcp"
        device_or_host:   Serial device path (e.g. "/dev/ttyUSB0", "COM3")
                          or TCP hostname/IP (e.g. "192.168.1.100")
        port:             TCP port (ignored for serial connections; default 4403)
        publisher:        MessagePublisher for downstream MQTT delivery
    """

    def __init__(
        self,
        connection_type: str,
        device_or_host: str,
        port: int,
        publisher: MessagePublisher,
    ) -> None:
        if connection_type not in ("serial", "tcp"):
            raise ValueError(
                f"connection_type must be 'serial' or 'tcp', got {connection_type!r}"
            )

        self._connection_type = connection_type
        self._device_or_host = device_or_host
        self._port = port
        self._publisher = publisher

        # Keyed by node_id_hex ("!xxxxxxxx")
        self._node_map: dict[str, MeshNode] = {}

        # The underlying interface (real SDK or mock)
        self._interface: Any = None
        self._mock: MockMeshtasticInterface | None = None

        # asyncio event loop reference (set on connect)
        self._loop: asyncio.AbstractEventLoop | None = None

        # Listening task
        self._listen_task: asyncio.Task[None] | None = None
        self._running = False

        logger.info(
            "meshtastic_adapter_created",
            connection_type=connection_type,
            device_or_host=device_or_host,
            port=port,
            sdk_available=_MESHTASTIC_AVAILABLE,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish connection to the Meshtastic device or mock."""
        self._loop = asyncio.get_event_loop()

        if _MESHTASTIC_AVAILABLE:
            await self._connect_real()
        else:
            await self._connect_mock()

        self._running = True
        logger.info(
            "meshtastic_adapter_connected",
            connection_type=self._connection_type,
            using_mock=not _MESHTASTIC_AVAILABLE,
        )

    async def _connect_real(self) -> None:
        """Connect via the real meshtastic SDK (runs blocking call in executor)."""
        assert self._loop is not None

        try:
            if self._connection_type == "serial":
                self._interface = await self._loop.run_in_executor(
                    None,
                    lambda: meshtastic.serial_interface.SerialInterface(
                        self._device_or_host
                    ),
                )
            else:
                self._interface = await self._loop.run_in_executor(
                    None,
                    lambda: meshtastic.tcp_interface.TCPInterface(
                        self._device_or_host, portNumber=self._port
                    ),
                )

            # Subscribe via pypubsub — meshtastic fires "meshtastic.receive"
            pub.subscribe(self._on_receive, "meshtastic.receive")
            logger.info(
                "meshtastic_sdk_interface_ready",
                connection_type=self._connection_type,
            )

        except Exception as exc:
            logger.error(
                "meshtastic_sdk_connect_failed",
                error=str(exc),
                fallback="switching to mock",
            )
            self._interface = None
            await self._connect_mock()

    async def _connect_mock(self) -> None:
        """Activate MockMeshtasticInterface as a drop-in replacement."""
        self._mock = MockMeshtasticInterface()
        self._mock.set_receive_callback(self._on_receive)
        self._interface = self._mock
        logger.info("meshtastic_mock_interface_active")

    async def disconnect(self) -> None:
        """Gracefully stop listening and close the device connection."""
        self._running = False

        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._mock is not None:
            await self._mock.stop()
            self._mock = None

        if self._interface is not None and _MESHTASTIC_AVAILABLE:
            try:
                pub.unsubscribe(self._on_receive, "meshtastic.receive")
            except Exception:
                pass
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._interface.close
                )
            except Exception:
                pass

        self._interface = None
        logger.info("meshtastic_adapter_disconnected")

    async def start_listening(self) -> None:
        """Start the background packet-receive loop.

        For the real SDK the pypubsub callback fires in the SDK's thread;
        this coroutine keeps the adapter alive and drives the mock emitter.
        For the mock, it starts the internal emission task.
        """
        if self._mock is not None:
            await self._mock.start()

        self._listen_task = asyncio.create_task(self._keep_alive_loop())
        logger.info("meshtastic_listening_started")

    async def _keep_alive_loop(self) -> None:
        """Keep the adapter alive while waiting for SDK callbacks."""
        while self._running:
            await asyncio.sleep(5.0)

    # ------------------------------------------------------------------
    # Packet receive callback (called from SDK thread or mock)
    # ------------------------------------------------------------------

    def _on_receive(self, packet: dict[str, Any], interface: Any) -> None:  # noqa: ARG002
        """Synchronous callback invoked by meshtastic SDK or mock.

        Dispatches to async handlers via run_coroutine_threadsafe so the
        blocking SDK thread does not hold the event loop.
        """
        if self._loop is None:
            return

        decoded = packet.get("decoded", {})
        portnum: str = decoded.get("portnum", "")

        coro: Any = None
        if portnum == PORTNUM_POSITION:
            coro = self._process_position(packet)
        elif portnum == PORTNUM_NODEINFO:
            coro = self._process_nodeinfo(packet)
        elif portnum == PORTNUM_TELEMETRY:
            coro = self._process_telemetry(packet)
        elif portnum == PORTNUM_TEXT:
            coro = self._process_text(packet)
        else:
            logger.debug("meshtastic_unknown_portnum", portnum=portnum)
            return

        asyncio.run_coroutine_threadsafe(coro, self._loop)

    # ------------------------------------------------------------------
    # Packet processors
    # ------------------------------------------------------------------

    async def _process_position(self, packet: dict[str, Any]) -> None:
        """Decode a POSITION_APP packet and update node map."""
        node_id: int = packet.get("from", 0)
        node_id_hex = _to_hex_id(node_id)
        pos_data: dict[str, Any] = packet.get("decoded", {}).get("position", {})

        lat_i: int = pos_data.get("latitude_i", 0)
        lon_i: int = pos_data.get("longitude_i", 0)
        alt: int = pos_data.get("altitude", 0)

        if lat_i == 0 and lon_i == 0:
            logger.debug("meshtastic_position_zero", node=node_id_hex)
            return

        lat = lat_i / 1e7
        lon = lon_i / 1e7

        try:
            geo = GeoPosition(latitude=lat, longitude=lon, altitude_m=float(alt))
        except ValueError as exc:
            logger.warning(
                "meshtastic_invalid_position",
                node=node_id_hex,
                lat=lat,
                lon=lon,
                error=str(exc),
            )
            return

        snr: float | None = packet.get("rxSnr")
        rssi: int | None = packet.get("rxRssi")
        hop: int = packet.get("hopLimit", 0)

        node = self._get_or_create_node(node_id, node_id_hex)
        node.position = geo
        node.snr = snr
        node.rssi = rssi
        node.hop_count = hop
        node.last_heard = datetime.now(UTC)

        logger.info(
            "meshtastic_position_updated",
            node=node_id_hex,
            lat=lat,
            lon=lon,
            alt=alt,
            snr=snr,
            rssi=rssi,
        )

        await self._publish_node(node)

    async def _process_nodeinfo(self, packet: dict[str, Any]) -> None:
        """Decode a NODEINFO_APP packet and update node map."""
        node_id: int = packet.get("from", 0)
        node_id_hex = _to_hex_id(node_id)
        user: dict[str, Any] = packet.get("decoded", {}).get("user", {})

        long_name: str = user.get("longName", node_id_hex)
        short_name: str = user.get("shortName", node_id_hex[:4].upper())
        hw_model: str = user.get("hwModel", "UNKNOWN")

        node = self._get_or_create_node(node_id, node_id_hex)
        node.long_name = long_name
        node.short_name = short_name
        node.hw_model = hw_model
        node.snr = packet.get("rxSnr", node.snr)
        node.rssi = packet.get("rxRssi", node.rssi)
        node.hop_count = packet.get("hopLimit", node.hop_count)
        node.last_heard = datetime.now(UTC)

        logger.info(
            "meshtastic_nodeinfo_updated",
            node=node_id_hex,
            long_name=long_name,
            short_name=short_name,
            hw_model=hw_model,
        )

    async def _process_telemetry(self, packet: dict[str, Any]) -> None:
        """Decode a TELEMETRY_APP packet and publish device metrics."""
        node_id: int = packet.get("from", 0)
        node_id_hex = _to_hex_id(node_id)
        telemetry: dict[str, Any] = (
            packet.get("decoded", {}).get("telemetry", {})
        )
        metrics: dict[str, Any] = telemetry.get("deviceMetrics", {})

        battery: int | None = metrics.get("batteryLevel")
        voltage: float | None = metrics.get("voltage")
        ch_util: float | None = metrics.get("channelUtilization")
        air_util: float | None = metrics.get("airUtilTx")

        node = self._get_or_create_node(node_id, node_id_hex)
        if battery is not None:
            node.battery_level = battery
        if voltage is not None:
            node.voltage = voltage
        if ch_util is not None:
            node.channel_utilization = ch_util
        if air_util is not None:
            node.air_util_tx = air_util
        node.last_heard = datetime.now(UTC)

        payload: dict[str, Any] = {
            "node_id": node_id_hex,
            "battery_level": battery,
            "voltage": voltage,
            "channel_util": ch_util,
            "air_util_tx": air_util,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._publisher.publish(TOPIC_TELEMETRY, payload)
        logger.info(
            "meshtastic_telemetry_published",
            node=node_id_hex,
            battery=battery,
            voltage=voltage,
        )

    async def _process_text(self, packet: dict[str, Any]) -> None:
        """Decode a TEXT_MESSAGE_APP packet and publish to MQTT."""
        from_id: int = packet.get("from", 0)
        to_id: int = packet.get("to", 0xFFFFFFFF)
        text: str = (
            packet.get("decoded", {}).get("text", "")
            or packet.get("decoded", {}).get("payload", b"").decode(
                "utf-8", errors="replace"
            )
        )
        snr: float | None = packet.get("rxSnr")
        rssi: int | None = packet.get("rxRssi")

        payload: dict[str, Any] = {
            "from": _to_hex_id(from_id),
            "to": _to_hex_id(to_id),
            "text": text,
            "snr": snr,
            "rssi": rssi,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._publisher.publish(TOPIC_TEXT, payload)
        logger.info(
            "meshtastic_text_published",
            from_node=_to_hex_id(from_id),
            to_node=_to_hex_id(to_id),
            text_preview=text[:60],
        )

    async def _publish_node(self, node: MeshNode) -> None:
        """Publish node position payload to hydra/mesh/position."""
        if node.position is None:
            return

        payload: dict[str, Any] = {
            "node_id": node.node_id_hex,
            "long_name": node.long_name,
            "lat": node.position.latitude,
            "lon": node.position.longitude,
            "alt": node.position.altitude_m or 0.0,
            "battery": node.battery_level,
            "snr": node.snr,
            "rssi": node.rssi,
            "hop_count": node.hop_count,
            "timestamp": node.last_heard.isoformat(),
        }

        await self._publisher.publish(TOPIC_POSITION, payload)
        logger.debug(
            "meshtastic_position_published",
            node=node.node_id_hex,
            topic=TOPIC_POSITION,
        )

    # ------------------------------------------------------------------
    # Domain conversion
    # ------------------------------------------------------------------

    def to_actor(self, node: MeshNode) -> Actor:
        """Convert a MeshNode to an Actor domain entity.

        Confidence is derived from link quality (RSSI thresholds).
        Falls back to SNR-based estimation when RSSI is absent.
        """
        confidence = _rssi_to_confidence(node.rssi, node.snr)

        return Actor(
            callsign=node.long_name or node.node_id_hex,
            actor_type=ActorType.PERSON,
            affiliation=Affiliation.UNKNOWN,
            position=node.position,
            source="MESH",
            last_seen=node.last_heard,
            confidence=confidence,
            metadata={
                "node_id_hex": node.node_id_hex,
                "short_name": node.short_name,
                "hw_model": node.hw_model,
                "battery_level": node.battery_level,
                "snr": node.snr,
                "rssi": node.rssi,
                "hop_count": node.hop_count,
                "voltage": node.voltage,
                "channel_utilization": node.channel_utilization,
                "air_util_tx": node.air_util_tx,
            },
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_node_map(self) -> dict[str, MeshNode]:
        """Return a shallow copy of the current known-node registry.

        Keys are node_id_hex strings ("!xxxxxxxx").
        """
        return dict(self._node_map)

    # ------------------------------------------------------------------
    # Send operations
    # ------------------------------------------------------------------

    async def send_text(
        self,
        message: str,
        destination: int = 0xFFFFFFFF,
    ) -> None:
        """Send a text message over the mesh network.

        Args:
            message:     UTF-8 text payload (Meshtastic max ~230 bytes).
            destination: Target node ID; 0xFFFFFFFF = broadcast.
        """
        if self._interface is None:
            logger.warning("meshtastic_send_text_no_interface")
            return

        dest_hex = _to_hex_id(destination)
        logger.info(
            "meshtastic_send_text",
            destination=dest_hex,
            message_preview=message[:60],
        )

        loop = asyncio.get_event_loop()
        try:
            if _MESHTASTIC_AVAILABLE and not isinstance(
                self._interface, MockMeshtasticInterface
            ):
                await loop.run_in_executor(
                    None,
                    lambda: self._interface.sendText(
                        message, destinationId=destination
                    ),
                )
            else:
                # Mock path
                self._interface.sendText(message, destinationId=destination)
        except Exception as exc:
            logger.error(
                "meshtastic_send_text_failed",
                destination=dest_hex,
                error=str(exc),
            )

    async def send_position(self, position: GeoPosition) -> None:
        """Broadcast our position over the mesh network.

        Args:
            position: WGS84 position to broadcast.
        """
        if self._interface is None:
            logger.warning("meshtastic_send_position_no_interface")
            return

        alt_m = int(position.altitude_m) if position.altitude_m is not None else 0
        logger.info(
            "meshtastic_send_position",
            lat=position.latitude,
            lon=position.longitude,
            alt=alt_m,
        )

        loop = asyncio.get_event_loop()
        try:
            if _MESHTASTIC_AVAILABLE and not isinstance(
                self._interface, MockMeshtasticInterface
            ):
                await loop.run_in_executor(
                    None,
                    lambda: self._interface.sendPosition(
                        latitude=position.latitude,
                        longitude=position.longitude,
                        altitude=alt_m,
                    ),
                )
            else:
                self._interface.sendPosition(
                    latitude=position.latitude,
                    longitude=position.longitude,
                    altitude=alt_m,
                )
        except Exception as exc:
            logger.error(
                "meshtastic_send_position_failed",
                lat=position.latitude,
                lon=position.longitude,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_node(self, node_id: int, node_id_hex: str) -> MeshNode:
        """Retrieve an existing MeshNode or create a skeleton entry."""
        if node_id_hex not in self._node_map:
            self._node_map[node_id_hex] = MeshNode(
                node_id=node_id,
                node_id_hex=node_id_hex,
                long_name=node_id_hex,
                short_name=node_id_hex[:4].upper(),
                hw_model="UNKNOWN",
                position=None,
                battery_level=None,
                snr=None,
                rssi=None,
                last_heard=datetime.now(UTC),
                hop_count=0,
            )
            logger.debug("meshtastic_node_registered", node=node_id_hex)

        return self._node_map[node_id_hex]


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------


def _to_hex_id(node_id: int) -> str:
    """Convert a 32-bit numeric node ID to Meshtastic hex callsign.

    Example: 0x12345678 -> "!12345678"
    """
    return f"!{node_id & 0xFFFFFFFF:08x}"


def _rssi_to_confidence(rssi: int | None, snr: float | None) -> float:
    """Map RF link quality metrics to an Actor confidence score (0.0–1.0).

    Primary metric is RSSI; SNR is used as a secondary estimate when RSSI
    is absent.  Thresholds reflect typical LoRa link budget experience:

        RSSI > -70 dBm  -> 0.9  (excellent link)
        RSSI > -85 dBm  -> 0.7  (good link)
        RSSI > -100 dBm -> 0.5  (marginal link)
        RSSI <= -100    -> 0.3  (poor/fringe link)

    SNR fallback (when RSSI is None):
        SNR > 10 dB     -> 0.9
        SNR > 5 dB      -> 0.7
        SNR > 0 dB      -> 0.5
        SNR <= 0 dB     -> 0.3
    """
    if rssi is not None:
        if rssi > _RSSI_HIGH:
            return _CONF_HIGH
        if rssi > _RSSI_MED:
            return _CONF_MED
        if rssi > _RSSI_LOW:
            return _CONF_LOW
        return _CONF_MINIMAL

    # SNR-based fallback
    if snr is not None:
        if snr > 10.0:
            return _CONF_HIGH
        if snr > 5.0:
            return _CONF_MED
        if snr > 0.0:
            return _CONF_LOW
        return _CONF_MINIMAL

    # No RF metrics available — neutral default
    return 0.5


__all__ = [
    "MeshNode",
    "MeshtasticAdapter",
    "MockMeshtasticInterface",
]
