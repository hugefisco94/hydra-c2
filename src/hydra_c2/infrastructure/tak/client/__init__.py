"""Infrastructure: TAK Client — connects to remote TAK Server (FreeTAKServer / WinTAK / ATAK).

Layer 3 (Data Ingestion): Receives Cursor-on-Target (CoT) XML streams over TCP/SSL/UDP,
parses them into domain entities, and publishes to the MQTT event bus.

Protocol references:
  - MIL-STD-2525B: Symbol identification codes
  - CoT schema: https://www.mitre.org/publications/technical-papers/cursor-on-target-message-router-users-guide
  - TAK Protocol v1: TCP stream delimited by newline or </event> token
"""

from __future__ import annotations

import asyncio
import json
import socket
import ssl
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import uuid4

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
# Constants
# ---------------------------------------------------------------------------

_COT_TOPIC_PREFIX = "hydra/cot"
_TCP_RECONNECT_DELAY_S = 5
_TCP_MAX_RECONNECT = 10
_TCP_READ_CHUNK = 4096
_COT_STALE_DEFAULT_S = 300

# Multicast default for ATAK SA broadcasts (standard SA port)
_MCAST_GROUP_DEFAULT = "239.2.3.1"
_MCAST_PORT_DEFAULT = 6969

# CoT type prefix → Affiliation mapping (MIL-STD-2525B)
_AFFILIATION_MAP: dict[str, Affiliation] = {
    "a-f": Affiliation.FRIENDLY,
    "a-h": Affiliation.HOSTILE,
    "a-n": Affiliation.NEUTRAL,
    "a-u": Affiliation.UNKNOWN,
}

# CoT dimension character → ActorType mapping
# Position 4 in type string (e.g. "a-f-G-U-C" → index [4] = 'G')
_DIMENSION_MAP: dict[str, ActorType] = {
    "G": ActorType.UNIT,       # Ground
    "A": ActorType.AIRCRAFT,   # Air
    "S": ActorType.VESSEL,     # Sea/Surface
    "U": ActorType.UNKNOWN,    # Sub-surface / Unknown
    "F": ActorType.UNKNOWN,    # SOF
    "P": ActorType.PERSON,     # Person (some schemas)
}

# Sub-type hints for more precise ActorType resolution
_SUBTYPE_HINTS: dict[str, ActorType] = {
    "U-A": ActorType.UAV,      # Unmanned Aircraft
    "A-C": ActorType.AIRCRAFT,
    "G-E": ActorType.VEHICLE,  # Ground Equipment
    "G-I": ActorType.UNIT,     # Ground Installation
    "G-U": ActorType.UNIT,     # Ground Unit
}


# ---------------------------------------------------------------------------
# CotMessage dataclass
# ---------------------------------------------------------------------------

@dataclass
class CotMessage:
    """Parsed Cursor-on-Target message — intermediate representation.

    Bridges raw CoT XML and the Actor domain entity.  All fields are
    populated by CotParser.parse(); consumers should use CotParser.to_actor()
    to obtain a fully-typed domain entity.
    """

    uid: str
    cot_type: str
    affiliation: Affiliation
    actor_type: ActorType
    position: GeoPosition
    callsign: str
    course_deg: Optional[float]
    speed_mps: Optional[float]
    timestamp: datetime
    stale_time: datetime
    raw_xml: str

    def to_mqtt_payload(self) -> dict[str, Any]:
        """Serialise to MQTT JSON payload."""
        return {
            "uid": self.uid,
            "cot_type": self.cot_type,
            "affiliation": self.affiliation.value,
            "actor_type": self.actor_type.value,
            "callsign": self.callsign,
            "lat": self.position.latitude,
            "lon": self.position.longitude,
            "hae": self.position.altitude_m,
            "course_deg": self.course_deg,
            "speed_mps": self.speed_mps,
            "timestamp": self.timestamp.isoformat(),
            "stale": self.stale_time.isoformat(),
        }


# ---------------------------------------------------------------------------
# CotParser — pure static utility, no state
# ---------------------------------------------------------------------------

class CotParser:
    """Parse CoT XML strings to/from domain entities.

    All methods are static; instantiation is not required.  The parser is
    intentionally lenient: malformed optional fields degrade gracefully to
    None rather than raising exceptions, because real-world TAK feeds often
    contain incomplete or non-standard CoT.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def parse(xml_str: str) -> Optional[CotMessage]:
        """Parse raw CoT XML string into a CotMessage.

        Returns None on any parse failure (malformed XML, missing required
        attributes) rather than propagating exceptions to the caller.
        """
        try:
            root = ET.fromstring(xml_str.strip())
        except ET.ParseError as exc:
            logger.warning("cot_parse_xml_error", error=str(exc), snippet=xml_str[:120])
            return None

        if root.tag != "event":
            logger.debug("cot_parse_not_event", tag=root.tag)
            return None

        uid = root.get("uid", "")
        cot_type = root.get("type", "")

        if not uid or not cot_type:
            logger.warning("cot_parse_missing_required", uid=uid, cot_type=cot_type)
            return None

        # Timestamps
        timestamp = CotParser._parse_time(root.get("time", ""))
        stale_time = CotParser._parse_time(root.get("stale", ""))
        if timestamp is None:
            timestamp = datetime.now(UTC)
        if stale_time is None:
            stale_time = timestamp

        # Position from <point> child
        point_el = root.find("point")
        if point_el is None:
            logger.warning("cot_parse_no_point", uid=uid)
            return None

        position = CotParser._parse_point(point_el)
        if position is None:
            logger.warning("cot_parse_invalid_point", uid=uid)
            return None

        # Affiliation and actor type from CoT type string
        affiliation = CotParser._parse_affiliation(cot_type)
        actor_type = CotParser._parse_actor_type(cot_type)

        # Detail block — optional sub-elements
        detail_el = root.find("detail")
        callsign = CotParser._parse_callsign(detail_el, uid)
        course_deg, speed_mps = CotParser._parse_track(detail_el)

        return CotMessage(
            uid=uid,
            cot_type=cot_type,
            affiliation=affiliation,
            actor_type=actor_type,
            position=position,
            callsign=callsign,
            course_deg=course_deg,
            speed_mps=speed_mps,
            timestamp=timestamp,
            stale_time=stale_time,
            raw_xml=xml_str,
        )

    @staticmethod
    def to_actor(msg: CotMessage) -> Actor:
        """Convert a parsed CotMessage to an Actor domain entity.

        The actor ID is derived from the CoT UID via uuid4 (not a real UUID
        derivation — we use a name-based approach so the same TAK UID always
        maps to the same Actor UUID within a session).
        """
        import hashlib
        # Deterministic UUID from CoT UID string
        digest = hashlib.sha1(msg.uid.encode()).digest()[:16]
        # Stamp version bits for UUID4 compatibility
        digest_list = bytearray(digest)
        digest_list[6] = (digest_list[6] & 0x0F) | 0x40
        digest_list[8] = (digest_list[8] & 0x3F) | 0x80
        from uuid import UUID
        actor_id = UUID(bytes=bytes(digest_list))

        return Actor(
            id=actor_id,
            callsign=msg.callsign,
            actor_type=msg.actor_type,
            affiliation=msg.affiliation,
            position=msg.position,
            speed_mps=msg.speed_mps,
            course_deg=msg.course_deg,
            source="ATAK",
            first_seen=msg.timestamp,
            last_seen=msg.timestamp,
            confidence=0.8,
            metadata={
                "cot_type": msg.cot_type,
                "uid": msg.uid,
                "stale": msg.stale_time.isoformat(),
            },
        )

    @staticmethod
    def create_cot_xml(actor: Actor, stale_seconds: int = _COT_STALE_DEFAULT_S) -> str:
        """Generate a CoT XML string from an Actor domain entity.

        Used for outbound CoT transmission (e.g. injecting HYDRA tracks back
        into the TAK common operating picture).
        """
        if actor.position is None:
            raise ValueError(f"Actor {actor.id} has no position — cannot create CoT")

        now = datetime.now(UTC)
        stale = datetime.fromtimestamp(now.timestamp() + stale_seconds, tz=UTC)

        cot_type = CotParser._actor_to_cot_type(actor)
        uid = actor.metadata.get("uid") or f"HYDRA-{actor.id}"

        time_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        stale_str = stale.strftime("%Y-%m-%dT%H:%M:%SZ")

        hae = actor.position.altitude_m if actor.position.altitude_m is not None else 9999999.0

        root = ET.Element("event")
        root.set("version", "2.0")
        root.set("uid", uid)
        root.set("type", cot_type)
        root.set("how", "m-g")
        root.set("time", time_str)
        root.set("start", time_str)
        root.set("stale", stale_str)

        point = ET.SubElement(root, "point")
        point.set("lat", str(actor.position.latitude))
        point.set("lon", str(actor.position.longitude))
        point.set("hae", str(hae))
        point.set("ce", "9999999")
        point.set("le", "9999999")

        detail = ET.SubElement(root, "detail")

        contact = ET.SubElement(detail, "contact")
        contact.set("callsign", actor.callsign or uid)

        if actor.course_deg is not None or actor.speed_mps is not None:
            track = ET.SubElement(detail, "track")
            track.set("course", str(actor.course_deg or 0.0))
            track.set("speed", str(actor.speed_mps or 0.0))

        # HYDRA metadata tag
        hydra_tag = ET.SubElement(detail, "hydra")
        hydra_tag.set("source", actor.source)
        hydra_tag.set("confidence", str(actor.confidence))

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_time(time_str: str) -> Optional[datetime]:
        """Parse CoT ISO-8601 timestamp — returns None on failure."""
        if not time_str:
            return None
        # CoT uses both 'Z' suffix and '+00:00'; normalise to UTC
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                    "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue
        logger.debug("cot_parse_time_failed", raw=time_str)
        return None

    @staticmethod
    def _parse_point(el: ET.Element) -> Optional[GeoPosition]:
        """Parse <point> element into GeoPosition."""
        try:
            lat = float(el.get("lat", "0"))
            lon = float(el.get("lon", "0"))
            hae_raw = el.get("hae", "9999999")
            hae: Optional[float] = None
            if hae_raw and float(hae_raw) < 9999998:
                hae = float(hae_raw)
            return GeoPosition(latitude=lat, longitude=lon, altitude_m=hae)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_affiliation(cot_type: str) -> Affiliation:
        """Extract MIL-STD-2525B affiliation from CoT type string."""
        prefix = cot_type[:3]  # e.g. "a-f"
        return _AFFILIATION_MAP.get(prefix, Affiliation.UNKNOWN)

    @staticmethod
    def _parse_actor_type(cot_type: str) -> ActorType:
        """Resolve ActorType from CoT type dimension and sub-type characters."""
        parts = cot_type.split("-")
        # parts[0]='a', parts[1]='f'/'h'/'n'/'u', parts[2]='G'/'A'/'S'/...
        if len(parts) < 3:
            return ActorType.UNKNOWN

        dimension = parts[2].upper()

        # Check sub-type hints first (more specific)
        if len(parts) >= 4:
            sub_key = f"{dimension}-{parts[3].upper()}"
            if sub_key in _SUBTYPE_HINTS:
                return _SUBTYPE_HINTS[sub_key]

        # UAV special case: "a-*-A-M-F-Q-r" or contains 'U-A'
        if len(parts) >= 4 and dimension == "A" and parts[3].upper() == "M":
            return ActorType.UAV

        return _DIMENSION_MAP.get(dimension, ActorType.UNKNOWN)

    @staticmethod
    def _parse_callsign(detail_el: Optional[ET.Element], fallback: str) -> str:
        """Extract callsign from <detail><contact callsign="..."/>."""
        if detail_el is None:
            return fallback
        contact = detail_el.find("contact")
        if contact is not None:
            cs = contact.get("callsign", "").strip()
            if cs:
                return cs
        # Some implementations put callsign directly in <detail>
        cs = detail_el.get("callsign", "").strip()
        return cs if cs else fallback

    @staticmethod
    def _parse_track(detail_el: Optional[ET.Element]) -> tuple[Optional[float], Optional[float]]:
        """Extract course (deg) and speed (m/s) from <detail><track .../>."""
        if detail_el is None:
            return None, None
        track = detail_el.find("track")
        if track is None:
            return None, None
        course: Optional[float] = None
        speed: Optional[float] = None
        try:
            course_raw = track.get("course")
            if course_raw is not None:
                course = float(course_raw)
        except (ValueError, TypeError):
            pass
        try:
            speed_raw = track.get("speed")
            if speed_raw is not None:
                speed = float(speed_raw)
        except (ValueError, TypeError):
            pass
        return course, speed

    @staticmethod
    def _actor_to_cot_type(actor: Actor) -> str:
        """Build CoT type string from Actor affiliation and type."""
        aff_map = {
            Affiliation.FRIENDLY: "f",
            Affiliation.HOSTILE: "h",
            Affiliation.NEUTRAL: "n",
            Affiliation.UNKNOWN: "u",
        }
        dim_map = {
            ActorType.UNIT: "G-U-C",
            ActorType.VEHICLE: "G-E-V",
            ActorType.AIRCRAFT: "A-C-F",
            ActorType.VESSEL: "S-X-M",
            ActorType.UAV: "A-M-F-Q-r",
            ActorType.PERSON: "G-U-C-I",
            ActorType.EQUIPMENT: "G-E",
            ActorType.UNKNOWN: "Z",
            ActorType.TRANSMISSION_SOURCE: "G-E-S",
        }
        aff = aff_map.get(actor.affiliation, "u")
        dim = dim_map.get(actor.actor_type, "Z")
        return f"a-{aff}-{dim}"


# ---------------------------------------------------------------------------
# CoT stream framing helper
# ---------------------------------------------------------------------------

class _CotStreamBuffer:
    """Stateful buffer that extracts complete CoT XML messages from a TCP byte stream.

    TAK Protocol v1 frames messages with either:
      - A newline character (0x0A) after </event>
      - The literal token '</event>' as an end-of-message marker

    Some implementations also prepend a 4-byte big-endian length prefix
    (TAK Protocol v2 / protobuf — out of scope here, but the framer
    handles it gracefully by discarding non-XML leading bytes).
    """

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, data: bytes) -> list[str]:
        """Feed raw bytes and return list of complete CoT XML strings."""
        self._buf += data
        messages: list[str] = []

        while True:
            # Find </event> end token
            end_idx = self._buf.find(b"</event>")
            if end_idx == -1:
                break

            end_pos = end_idx + len(b"</event>")
            chunk = self._buf[:end_pos]
            self._buf = self._buf[end_pos:]

            # Strip any leading garbage before <?xml or <event
            for start_token in (b"<?xml", b"<event"):
                start_idx = chunk.find(start_token)
                if start_idx != -1:
                    chunk = chunk[start_idx:]
                    break
            else:
                # No recognisable XML start — discard
                logger.debug("cot_framer_discard_chunk", size=len(chunk))
                continue

            try:
                xml_str = chunk.decode("utf-8", errors="replace").strip()
                if xml_str:
                    messages.append(xml_str)
            except Exception as exc:
                logger.warning("cot_framer_decode_error", error=str(exc))

        # Guard against unbounded buffer growth (>1 MB)
        if len(self._buf) > 1_048_576:
            logger.error("cot_framer_buffer_overflow", size=len(self._buf))
            self._buf = b""

        return messages


# ---------------------------------------------------------------------------
# TakTcpClient
# ---------------------------------------------------------------------------

class TakTcpClient:
    """TAK Server TCP (or SSL/TLS) client.

    Connects to a TAK Server endpoint, receives a continuous CoT XML stream,
    parses each message, converts it to an Actor domain entity, and publishes
    the result to the MQTT event bus on the topic `hydra/cot/{cot_type}`.

    Reconnection:
        On any connection error the client waits _TCP_RECONNECT_DELAY_S
        seconds before retrying.  After _TCP_MAX_RECONNECT consecutive
        failures the listen loop exits and the task completes.

    Usage::

        publisher = MqttPublisher(host="localhost", port=1883)
        await publisher.connect()

        client = TakTcpClient(host="tak.example.com", port=8089, publisher=publisher)
        await client.connect()
        task = asyncio.create_task(client.listen())
        ...
        await client.disconnect()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8089,
        publisher: Optional[MessagePublisher] = None,
        ssl: bool = False,
        cert_path: str = "",
        key_path: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._publisher = publisher
        self._use_ssl = ssl
        self._cert_path = cert_path
        self._key_path = key_path

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._running = False
        self._framer = _CotStreamBuffer()

        self._log = logger.bind(
            component="TakTcpClient",
            host=host,
            port=port,
            ssl=ssl,
        )

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open TCP (or SSL) connection to TAK Server."""
        ssl_ctx = self._build_ssl_context() if self._use_ssl else None

        try:
            self._reader, self._writer = await asyncio.open_connection(
                host=self._host,
                port=self._port,
                ssl=ssl_ctx,
            )
            self._connected = True
            self._log.info("tak_tcp_connected")
        except OSError as exc:
            self._log.error("tak_tcp_connect_failed", error=str(exc))
            raise

    async def disconnect(self) -> None:
        """Gracefully close the TCP connection and stop the listen loop."""
        self._running = False
        self._connected = False
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        self._log.info("tak_tcp_disconnected")

    async def listen(self) -> None:
        """Main receive loop — intended to run as an asyncio Task.

        Continuously reads from the TAK TCP stream, frames complete CoT
        messages, and dispatches them for processing.  Reconnects
        automatically on connection loss up to _TCP_MAX_RECONNECT times.
        """
        self._running = True
        reconnect_count = 0

        while self._running:
            if not self._connected:
                if reconnect_count >= _TCP_MAX_RECONNECT:
                    self._log.error(
                        "tak_tcp_max_reconnect_exceeded",
                        max=_TCP_MAX_RECONNECT,
                    )
                    break
                self._log.info(
                    "tak_tcp_reconnecting",
                    attempt=reconnect_count + 1,
                    delay_s=_TCP_RECONNECT_DELAY_S,
                )
                await asyncio.sleep(_TCP_RECONNECT_DELAY_S)
                try:
                    await self.connect()
                    reconnect_count = 0  # reset on successful reconnect
                except OSError as exc:
                    reconnect_count += 1
                    self._log.warning(
                        "tak_tcp_reconnect_failed",
                        attempt=reconnect_count,
                        error=str(exc),
                    )
                    continue

            try:
                data = await self._reader.read(_TCP_READ_CHUNK)  # type: ignore[union-attr]
            except (asyncio.IncompleteReadError, ConnectionResetError, OSError) as exc:
                self._log.warning("tak_tcp_read_error", error=str(exc))
                self._connected = False
                self._reader = None
                self._writer = None
                continue

            if not data:
                # Remote closed the connection
                self._log.info("tak_tcp_remote_closed")
                self._connected = False
                self._reader = None
                self._writer = None
                continue

            xml_messages = self._framer.feed(data)
            for xml_str in xml_messages:
                msg = await self._process_message(xml_str.encode())
                if msg is not None:
                    await self._publish_cot(msg)

        self._log.info("tak_tcp_listen_stopped")

    async def send_cot(self, cot_xml: str) -> None:
        """Transmit a CoT XML message to the TAK Server.

        Appends a newline delimiter as required by TAK Protocol v1.
        Raises RuntimeError if not connected.
        """
        if not self._connected or self._writer is None:
            raise RuntimeError("TakTcpClient is not connected")
        payload = cot_xml.strip() + "\n"
        self._writer.write(payload.encode("utf-8"))
        await self._writer.drain()
        self._log.debug("tak_tcp_sent", size=len(payload))

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    async def _process_message(self, data: bytes) -> Optional[CotMessage]:
        """Parse raw bytes into a CotMessage; returns None on failure."""
        xml_str = data.decode("utf-8", errors="replace")
        msg = CotParser.parse(xml_str)
        if msg is None:
            self._log.debug("tak_tcp_parse_failed", snippet=xml_str[:80])
            return None
        self._log.debug(
            "tak_tcp_cot_received",
            uid=msg.uid,
            cot_type=msg.cot_type,
            callsign=msg.callsign,
        )
        return msg

    async def _publish_cot(self, msg: CotMessage) -> None:
        """Publish a parsed CotMessage to the MQTT event bus."""
        if self._publisher is None:
            return

        # Topic: hydra/cot/{cot_type}  e.g. hydra/cot/a-f-G-U-C
        # Replace dots with underscores to avoid MQTT topic hierarchy issues
        safe_type = msg.cot_type.replace(".", "_")
        topic = f"{_COT_TOPIC_PREFIX}/{safe_type}"
        payload = msg.to_mqtt_payload()

        try:
            await self._publisher.publish(topic, payload)
            self._log.debug("tak_cot_published", topic=topic, uid=msg.uid)
        except Exception as exc:
            self._log.error("tak_cot_publish_failed", topic=topic, error=str(exc))

    # ------------------------------------------------------------------
    # SSL context
    # ------------------------------------------------------------------

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build an SSL context for mutual TLS authentication.

        If cert_path and key_path are provided the client certificate is
        loaded for mutual TLS (required by some TAK Server configurations).
        """
        import ssl as _ssl  # local import to avoid shadowing the parameter name

        ctx = _ssl.create_default_context()

        if self._cert_path and self._key_path:
            ctx.load_cert_chain(certfile=self._cert_path, keyfile=self._key_path)
            self._log.info("tak_ssl_client_cert_loaded", cert=self._cert_path)
        else:
            # No client cert — server auth only (or disable verification
            # for self-signed certs common in tactical environments)
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            self._log.warning(
                "tak_ssl_no_client_cert",
                note="Server certificate verification disabled",
            )

        return ctx


# ---------------------------------------------------------------------------
# TakUdpClient — UDP multicast SA broadcast receiver
# ---------------------------------------------------------------------------

class TakUdpClient:
    """TAK Server UDP multicast client for Situational Awareness (SA) broadcasts.

    ATAK and WinTAK periodically broadcast CoT SA messages on the multicast
    group 239.2.3.1:6969 (default).  This client joins the group and
    processes incoming CoT XML datagrams.

    Unlike TakTcpClient no reconnection logic is needed — UDP is
    connectionless.  The listen loop simply runs until disconnect() is called.

    Usage::

        client = TakUdpClient(
            multicast_group="239.2.3.1",
            port=6969,
            publisher=publisher,
        )
        task = asyncio.create_task(client.listen())
        ...
        await client.disconnect()
    """

    def __init__(
        self,
        multicast_group: str = _MCAST_GROUP_DEFAULT,
        port: int = _MCAST_PORT_DEFAULT,
        publisher: Optional[MessagePublisher] = None,
    ) -> None:
        self._group = multicast_group
        self._port = port
        self._publisher = publisher
        self._running = False
        self._sock: Optional[socket.socket] = None

        self._log = logger.bind(
            component="TakUdpClient",
            multicast_group=multicast_group,
            port=port,
        )

    async def listen(self) -> None:
        """Join multicast group and process incoming SA broadcasts.

        Runs until disconnect() is called or an unrecoverable socket error
        occurs.  Each datagram is expected to contain exactly one CoT XML
        document (UDP datagrams are message-bounded, unlike TCP streams).
        """
        self._running = True
        loop = asyncio.get_running_loop()

        try:
            self._sock = self._create_multicast_socket()
        except OSError as exc:
            self._log.error("tak_udp_socket_failed", error=str(exc))
            return

        self._log.info("tak_udp_listening")

        while self._running:
            try:
                # asyncio does not have a native UDP recv — use run_in_executor
                # with a short timeout so we can check _running periodically.
                data = await loop.run_in_executor(None, self._recv_datagram)
            except OSError as exc:
                if self._running:
                    self._log.warning("tak_udp_recv_error", error=str(exc))
                break

            if data is None:
                # Timeout — check _running and loop again
                continue

            xml_str = data.decode("utf-8", errors="replace").strip()
            if not xml_str:
                continue

            msg = CotParser.parse(xml_str)
            if msg is None:
                self._log.debug("tak_udp_parse_failed", snippet=xml_str[:80])
                continue

            self._log.debug(
                "tak_udp_cot_received",
                uid=msg.uid,
                cot_type=msg.cot_type,
                callsign=msg.callsign,
            )

            if self._publisher is not None:
                safe_type = msg.cot_type.replace(".", "_")
                topic = f"{_COT_TOPIC_PREFIX}/{safe_type}"
                try:
                    await self._publisher.publish(topic, msg.to_mqtt_payload())
                    self._log.debug("tak_udp_cot_published", topic=topic, uid=msg.uid)
                except Exception as exc:
                    self._log.error("tak_udp_publish_failed", error=str(exc))

        self._log.info("tak_udp_listen_stopped")
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    async def disconnect(self) -> None:
        """Signal the listen loop to stop."""
        self._running = False
        self._log.info("tak_udp_disconnect_requested")

    # ------------------------------------------------------------------
    # Socket helpers
    # ------------------------------------------------------------------

    def _create_multicast_socket(self) -> socket.socket:
        """Create and configure a UDP multicast receive socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT allows multiple listeners on the same port (Linux only)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", self._port))

        # Join the multicast group
        mreq = struct.pack(
            "4sL",
            socket.inet_aton(self._group),
            socket.INADDR_ANY,
        )
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Non-blocking with 1-second timeout for cooperative shutdown
        sock.settimeout(1.0)
        return sock

    def _recv_datagram(self) -> Optional[bytes]:
        """Blocking recv call with timeout — returns None on timeout."""
        if self._sock is None:
            return None
        try:
            data, _ = self._sock.recvfrom(65535)
            return data
        except socket.timeout:
            return None


# ---------------------------------------------------------------------------
# TakClientFactory — convenience factory driven by TakSettings
# ---------------------------------------------------------------------------

class TakClientFactory:
    """Construct the appropriate TAK client from TakSettings configuration.

    Usage::

        from hydra_c2.config import TakSettings
        from hydra_c2.infrastructure.tak.client import TakClientFactory

        settings = TakSettings()
        client = TakClientFactory.build(settings, publisher=publisher)
        await client.connect()
        asyncio.create_task(client.listen())
    """

    @staticmethod
    def build(
        settings: Any,
        publisher: Optional[MessagePublisher] = None,
    ) -> "TakTcpClient | TakUdpClient":
        """Return a TCP or UDP client based on settings.protocol."""
        protocol = getattr(settings, "protocol", "tcp").lower()

        if protocol == "udp":
            return TakUdpClient(
                multicast_group=_MCAST_GROUP_DEFAULT,
                port=getattr(settings, "port", _MCAST_PORT_DEFAULT),
                publisher=publisher,
            )

        # tcp or ssl
        use_ssl = protocol == "ssl"
        return TakTcpClient(
            host=getattr(settings, "host", "localhost"),
            port=getattr(settings, "port", 8089),
            publisher=publisher,
            ssl=use_ssl,
            cert_path=getattr(settings, "cert_path", ""),
            key_path=getattr(settings, "key_path", ""),
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "CotMessage",
    "CotParser",
    "TakTcpClient",
    "TakUdpClient",
    "TakClientFactory",
]
