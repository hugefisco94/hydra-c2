"""Infrastructure: KrakenSDR Radio Direction Finding.

KrakenSDR is a 5-channel phase-coherent SDR for Direction of Arrival
(DOA) estimation. This adapter polls the KrakenSDR HTTP API, converts
DOA angles to bearing lines, and publishes MQTT events for fusion.

Topics published:
    hydra/sdr/rdf     — per-scan DOA result (bearing, freq, confidence)
    hydra/sdr/status  — adapter health / connection status
"""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)

KRAKEN_DEFAULT_HOST = "127.0.0.1"
KRAKEN_DEFAULT_PORT = 8081
KRAKEN_POLL_INTERVAL = 0.5
KRAKEN_TIMEOUT = 5.0

TOPIC_RDF = "hydra/sdr/rdf"
TOPIC_STATUS = "hydra/sdr/status"

CONFIDENCE_LOW = 0.30


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DoaResult:
    """Single Direction-of-Arrival measurement."""

    scan_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    bearing_deg: float = 0.0
    doa_confidence: float = 0.0
    doa_power_db: float = -120.0
    center_freq_hz: float = 433.92e6
    bandwidth_hz: float = 200_000.0
    station_lat: Optional[float] = None
    station_lon: Optional[float] = None
    station_alt_m: Optional[float] = None

    def to_mqtt_payload(self) -> dict[str, Any]:
        return {
            "scan_id": str(self.scan_id),
            "timestamp": self.timestamp.isoformat(),
            "bearing_deg": round(self.bearing_deg, 2),
            "doa_confidence": round(self.doa_confidence, 4),
            "doa_power_db": round(self.doa_power_db, 2),
            "center_freq_hz": self.center_freq_hz,
            "bandwidth_hz": self.bandwidth_hz,
            "station": {
                "lat": self.station_lat,
                "lon": self.station_lon,
                "alt_m": self.station_alt_m,
            },
        }

    def bearing_endpoint(self, range_km: float = 10.0) -> tuple[float, float]:
        """Project bearing line endpoint (lat, lon) for map rendering."""
        if self.station_lat is None or self.station_lon is None:
            return (0.0, 0.0)
        R = 6371.0
        lat1 = math.radians(self.station_lat)
        lon1 = math.radians(self.station_lon)
        brg = math.radians(self.bearing_deg)
        d_R = range_km / R
        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_R)
            + math.cos(lat1) * math.sin(d_R) * math.cos(brg)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brg) * math.sin(d_R) * math.cos(lat1),
            math.cos(d_R) - math.sin(lat1) * math.sin(lat2),
        )
        return (math.degrees(lat2), math.degrees(lon2))


@dataclass
class KrakenStatus:
    connected: bool = False
    last_poll: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    firmware_version: Optional[str] = None
    num_channels: int = 5

    def to_mqtt_payload(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "firmware_version": self.firmware_version,
            "num_channels": self.num_channels,
        }


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

class KrakenResponseParser:
    """Parse KrakenSDR /pr_doa_res API responses (v1.6+ schema)."""

    @staticmethod
    def parse_doa(
        data: dict[str, Any],
        station_lat: Optional[float] = None,
        station_lon: Optional[float] = None,
        station_alt_m: Optional[float] = None,
    ) -> Optional[DoaResult]:
        try:
            bearing = float(
                data.get("DOA_res_deg")
                or data.get("doa_deg")
                or data.get("bearing")
                or 0.0
            )
            conf_raw = float(
                data.get("DOA_confidence")
                or data.get("confidence")
                or data.get("SNR")
                or 0.0
            )
            confidence = min(1.0, conf_raw / 30.0) if conf_raw > 1.0 else conf_raw
            power_db = float(
                data.get("max_amplitude") or data.get("peak_power_db") or -120.0
            )
            return DoaResult(
                bearing_deg=bearing % 360,
                doa_confidence=confidence,
                doa_power_db=power_db,
                center_freq_hz=float(data.get("freq_Hz") or 433.92e6),
                bandwidth_hz=float(data.get("bw_Hz") or 200_000.0),
                station_lat=station_lat,
                station_lon=station_lon,
                station_alt_m=station_alt_m,
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("kraken_parse_failed", error=str(exc))
            return None

    @staticmethod
    def parse_status(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "firmware_version": data.get("fw_version") or data.get("version"),
            "num_channels": int(data.get("num_ch") or data.get("channels") or 5),
        }


# ---------------------------------------------------------------------------
# Mock interface
# ---------------------------------------------------------------------------

class MockKrakenInterface:
    """Simulates KrakenSDR output for development/testing."""

    def __init__(self) -> None:
        self._tick = 0
        self._emitters = [
            (47.0, 433.92e6, -45.0),
            (162.0, 915.00e6, -62.0),
            (285.0, 868.00e6, -58.0),
        ]

    async def get_doa(self) -> dict[str, Any]:
        import random
        bearing, freq, power = self._emitters[self._tick % len(self._emitters)]
        self._tick += 1
        return {
            "DOA_res_deg": (bearing + random.gauss(0, 3.0)) % 360,
            "DOA_confidence": min(1.0, random.uniform(12, 28) / 30.0),
            "max_amplitude": power,
            "freq_Hz": freq,
            "bw_Hz": 200_000.0,
        }

    async def get_status(self) -> dict[str, Any]:
        return {"fw_version": "mock-1.0", "num_ch": 5}


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

class KrakenHttpClient:
    def __init__(self, host: str, port: int, timeout: float = KRAKEN_TIMEOUT) -> None:
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self._client: Any = None

    async def connect(self) -> None:
        try:
            import httpx
            self._client = httpx.AsyncClient(timeout=self.timeout)
        except ImportError:
            self._client = None

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()

    async def get_doa(self) -> Optional[dict[str, Any]]:
        if not self._client:
            return None
        try:
            resp = await self._client.get(f"{self.base_url}/pr_doa_res")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("kraken_http_doa_failed", error=str(exc))
            return None

    async def get_status(self) -> Optional[dict[str, Any]]:
        if not self._client:
            return None
        try:
            resp = await self._client.get(f"{self.base_url}/status")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("kraken_http_status_failed", error=str(exc))
            return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class KrakenSdrAdapter:
    """HYDRA-C2 L0 adapter for KrakenSDR DOA output.

    Polls the KrakenSDR HTTP API and publishes bearing measurements
    to MQTT for downstream fusion and triangulation.
    Falls back to mock mode when hardware is unreachable.
    """

    def __init__(
        self,
        host: str = KRAKEN_DEFAULT_HOST,
        port: int = KRAKEN_DEFAULT_PORT,
        station_lat: Optional[float] = None,
        station_lon: Optional[float] = None,
        station_alt_m: Optional[float] = None,
        poll_interval: float = KRAKEN_POLL_INTERVAL,
        publisher: Any = None,
        use_mock: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.station_lat = station_lat
        self.station_lon = station_lon
        self.station_alt_m = station_alt_m
        self.poll_interval = poll_interval
        self.publisher = publisher
        self.use_mock = use_mock

        self._status = KrakenStatus()
        self._latest: Optional[DoaResult] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._parser = KrakenResponseParser()
        self._http: Optional[KrakenHttpClient] = None
        self._mock: Optional[MockKrakenInterface] = None

    async def connect(self) -> None:
        if self.use_mock:
            self._mock = MockKrakenInterface()
            logger.info("kraken_mock_active")
        else:
            self._http = KrakenHttpClient(self.host, self.port)
            await self._http.connect()
            status_data = await self._http.get_status()
            if status_data is None:
                logger.warning("kraken_hardware_unreachable", fallback="mock")
                self._mock = MockKrakenInterface()
            else:
                parsed = self._parser.parse_status(status_data)
                self._status.firmware_version = parsed["firmware_version"]
                self._status.num_channels = parsed["num_channels"]
                logger.info(
                    "kraken_connected",
                    host=self.host,
                    firmware=self._status.firmware_version,
                    channels=self._status.num_channels,
                )

        self._status.connected = True
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def disconnect(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._http:
            await self._http.disconnect()
        self._status.connected = False
        logger.info("kraken_disconnected")

    async def _poll_loop(self) -> None:
        logger.info("kraken_poll_loop_started", interval=self.poll_interval)
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._status.error_count += 1
                self._status.last_error = str(exc)
                logger.warning("kraken_poll_error", error=str(exc))
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        if self._mock:
            raw = await self._mock.get_doa()
        else:
            raw = await self._http.get_doa()  # type: ignore[union-attr]

        self._status.last_poll = datetime.now(UTC)
        if raw is None:
            return

        result = self._parser.parse_doa(
            raw,
            station_lat=self.station_lat,
            station_lon=self.station_lon,
            station_alt_m=self.station_alt_m,
        )
        if result is None or result.doa_confidence < CONFIDENCE_LOW:
            return

        self._latest = result
        logger.info(
            "kraken_doa",
            bearing=round(result.bearing_deg, 1),
            confidence=round(result.doa_confidence, 3),
            freq_mhz=round(result.center_freq_hz / 1e6, 3),
        )

        if self.publisher:
            await self.publisher.publish(TOPIC_RDF, json.dumps(result.to_mqtt_payload()))
            await self.publisher.publish(TOPIC_STATUS, json.dumps(self._status.to_mqtt_payload()))

    @property
    def latest_result(self) -> Optional[DoaResult]:
        return self._latest

    @property
    def status(self) -> KrakenStatus:
        return self._status


# ---------------------------------------------------------------------------
# Multi-station triangulator
# ---------------------------------------------------------------------------

@dataclass
class TdoaStation:
    station_id: str
    lat: float
    lon: float
    latest_bearing: Optional[float] = None
    latest_confidence: Optional[float] = None


class TdoaTriangulator:
    """Weighted bearing-intersection triangulation from N KrakenSDR stations."""

    def __init__(self) -> None:
        self._stations: dict[str, TdoaStation] = {}

    def register(self, station: TdoaStation) -> None:
        self._stations[station.station_id] = station

    def update(self, station_id: str, bearing: float, confidence: float) -> None:
        if station_id in self._stations:
            s = self._stations[station_id]
            s.latest_bearing = bearing
            s.latest_confidence = confidence

    def triangulate(self) -> Optional[tuple[float, float]]:
        """Return (lat, lon) estimate or None if < 2 stations available."""
        stations = [
            s for s in self._stations.values()
            if s.latest_bearing is not None
        ]
        if len(stations) < 2:
            return None
        try:
            return self._ls_intersect(stations)
        except Exception as exc:
            logger.warning("tdoa_failed", error=str(exc))
            return None

    def _ls_intersect(self, stations: list[TdoaStation]) -> Optional[tuple[float, float]]:
        A_rows, b_rows, weights = [], [], []
        for s in stations:
            theta = math.radians(s.latest_bearing)  # type: ignore[arg-type]
            sin_t, cos_t = math.sin(theta), math.cos(theta)
            A_rows.append([sin_t, -cos_t])
            b_rows.append(sin_t * s.lat - cos_t * s.lon)
            weights.append(s.latest_confidence or 0.5)

        AtWA = [[0.0, 0.0], [0.0, 0.0]]
        AtWb = [0.0, 0.0]
        for row, b, w in zip(A_rows, b_rows, weights):
            for j in range(2):
                for k in range(2):
                    AtWA[j][k] += w * row[j] * row[k]
                AtWb[j] += w * row[j] * b

        det = AtWA[0][0] * AtWA[1][1] - AtWA[0][1] * AtWA[1][0]
        if abs(det) < 1e-12:
            return None
        lat = (AtWb[0] * AtWA[1][1] - AtWb[1] * AtWA[0][1]) / det
        lon = (AtWA[0][0] * AtWb[1] - AtWA[1][0] * AtWb[0]) / det
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return (lat, lon)
