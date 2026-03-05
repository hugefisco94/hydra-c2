"""Infrastructure: ML Analytics Engine.

Provides movement pattern analysis, threat scoring, and anomaly
detection for actors observed in the HYDRA-C2 operational picture.

Optionally offloads narrative threat assessments to the DO GPU
vLLM endpoint (qwen2.5-vl-72b) for rich natural-language analysis.

Topics published:
    hydra/analytics/threat_scores  — per-actor threat score update
    hydra/analytics/anomalies      — detected movement anomalies
"""

from __future__ import annotations

import asyncio
import json
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# MQTT topics
TOPIC_THREAT_SCORES = "hydra/analytics/threat_scores"
TOPIC_ANOMALIES = "hydra/analytics/anomalies"

# DO GPU vLLM endpoint
DO_GPU_HOST = "134.199.207.172"
DO_GPU_PORT = 8000
DO_GPU_API_KEY = "sk-do-vllm-2026"
DO_GPU_MODEL = "qwen2.5-vl-72b"
DO_GPU_TIMEOUT = 30.0

# Analysis windows
MOVEMENT_WINDOW_SECS = 300    # 5-minute movement history
ANOMALY_Z_THRESHOLD = 2.5     # z-score cutoff for anomaly flag
MIN_OBSERVATIONS = 5          # minimum points before scoring


# ---------------------------------------------------------------------------
# Enums + result types
# ---------------------------------------------------------------------------

class ThreatLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass
class MovementFeatures:
    """Extracted kinematic features for a single actor."""

    actor_id: UUID
    speed_mean_mps: float = 0.0
    speed_std_mps: float = 0.0
    speed_max_mps: float = 0.0
    course_variance_deg: float = 0.0
    displacement_km: float = 0.0
    observation_count: int = 0
    is_stationary: bool = True


@dataclass
class ThreatScore:
    """Composite threat assessment for a single actor."""

    actor_id: UUID
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    score: float = 0.0                     # 0.0–1.0
    threat_level: ThreatLevel = ThreatLevel.UNKNOWN
    components: dict[str, float] = field(default_factory=dict)
    llm_assessment: Optional[str] = None
    is_anomaly: bool = False

    def to_mqtt_payload(self) -> dict[str, Any]:
        return {
            "actor_id": str(self.actor_id),
            "timestamp": self.timestamp.isoformat(),
            "score": round(self.score, 4),
            "threat_level": self.threat_level.value,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "llm_assessment": self.llm_assessment,
            "is_anomaly": self.is_anomaly,
        }


@dataclass
class AnomalyEvent:
    """Detected movement anomaly."""

    actor_id: UUID
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    anomaly_type: str = "UNKNOWN"
    z_score: float = 0.0
    description: str = ""

    def to_mqtt_payload(self) -> dict[str, Any]:
        return {
            "actor_id": str(self.actor_id),
            "timestamp": self.timestamp.isoformat(),
            "anomaly_type": self.anomaly_type,
            "z_score": round(self.z_score, 3),
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Observation history store
# ---------------------------------------------------------------------------

@dataclass
class PositionObservation:
    timestamp: datetime
    lat: float
    lon: float
    speed_mps: Optional[float] = None
    course_deg: Optional[float] = None
    affiliation: str = "UNKNOWN"
    source: str = "MANUAL"


class ActorHistory:
    """Sliding-window observation history for a single actor."""

    def __init__(self, window_secs: int = MOVEMENT_WINDOW_SECS) -> None:
        self._window_secs = window_secs
        self._obs: deque[PositionObservation] = deque()

    def add(self, obs: PositionObservation) -> None:
        self._obs.append(obs)
        cutoff = datetime.now(UTC) - timedelta(seconds=self._window_secs)
        while self._obs and self._obs[0].timestamp < cutoff:
            self._obs.popleft()

    @property
    def observations(self) -> list[PositionObservation]:
        return list(self._obs)

    def __len__(self) -> int:
        return len(self._obs)


# ---------------------------------------------------------------------------
# Movement analyzer
# ---------------------------------------------------------------------------

class MovementAnalyzer:
    """Extracts kinematic features from actor observation history."""

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def extract(self, actor_id: UUID, history: ActorHistory) -> MovementFeatures:
        obs = history.observations
        if len(obs) < 2:
            return MovementFeatures(
                actor_id=actor_id,
                observation_count=len(obs),
                is_stationary=True,
            )

        speeds: list[float] = []
        courses: list[float] = []
        total_dist_km = 0.0

        for i in range(1, len(obs)):
            prev, curr = obs[i - 1], obs[i]
            dt = (curr.timestamp - prev.timestamp).total_seconds()
            if dt <= 0:
                continue
            dist_km = self.haversine_km(prev.lat, prev.lon, curr.lat, curr.lon)
            total_dist_km += dist_km
            speed = (dist_km * 1000) / dt  # m/s
            speeds.append(speed)
            if curr.course_deg is not None:
                courses.append(curr.course_deg)

        if not speeds:
            return MovementFeatures(actor_id=actor_id, observation_count=len(obs))

        speed_mean = statistics.mean(speeds)
        speed_std = statistics.stdev(speeds) if len(speeds) > 1 else 0.0
        speed_max = max(speeds)

        # Circular variance for course (handles 0/360 wrap-around)
        course_var = 0.0
        if len(courses) > 1:
            sin_sum = sum(math.sin(math.radians(c)) for c in courses)
            cos_sum = sum(math.cos(math.radians(c)) for c in courses)
            R_stat = math.sqrt(sin_sum ** 2 + cos_sum ** 2) / len(courses)
            course_var = math.degrees(math.sqrt(-2 * math.log(max(R_stat, 1e-9))))

        # Point-to-point displacement (first to last)
        displacement = self.haversine_km(
            obs[0].lat, obs[0].lon, obs[-1].lat, obs[-1].lon
        )

        is_stationary = speed_mean < 0.5 and total_dist_km < 0.05

        return MovementFeatures(
            actor_id=actor_id,
            speed_mean_mps=speed_mean,
            speed_std_mps=speed_std,
            speed_max_mps=speed_max,
            course_variance_deg=course_var,
            displacement_km=displacement,
            observation_count=len(obs),
            is_stationary=is_stationary,
        )


# ---------------------------------------------------------------------------
# Anomaly detector
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """Z-score based anomaly detection across actor population.

    Computes z-scores for speed and displacement against the
    current population distribution. Actors exceeding
    ANOMALY_Z_THRESHOLD standard deviations are flagged.
    """

    def __init__(self, threshold: float = ANOMALY_Z_THRESHOLD) -> None:
        self.threshold = threshold
        self._speed_history: list[float] = []
        self._disp_history: list[float] = []

    def update_population(self, features_list: list[MovementFeatures]) -> None:
        self._speed_history = [f.speed_mean_mps for f in features_list if f.observation_count >= MIN_OBSERVATIONS]
        self._disp_history = [f.displacement_km for f in features_list if f.observation_count >= MIN_OBSERVATIONS]

    def detect(self, features: MovementFeatures) -> list[AnomalyEvent]:
        if features.observation_count < MIN_OBSERVATIONS:
            return []

        events: list[AnomalyEvent] = []

        if len(self._speed_history) >= 3:
            mu = statistics.mean(self._speed_history)
            sigma = statistics.stdev(self._speed_history)
            if sigma > 0:
                z = (features.speed_mean_mps - mu) / sigma
                if abs(z) > self.threshold:
                    events.append(AnomalyEvent(
                        actor_id=features.actor_id,
                        anomaly_type="HIGH_SPEED",
                        z_score=z,
                        description=f"Speed {features.speed_mean_mps:.1f} m/s is {z:.1f}σ from mean {mu:.1f} m/s",
                    ))

        if len(self._disp_history) >= 3:
            mu = statistics.mean(self._disp_history)
            sigma = statistics.stdev(self._disp_history)
            if sigma > 0:
                z = (features.displacement_km - mu) / sigma
                if abs(z) > self.threshold:
                    events.append(AnomalyEvent(
                        actor_id=features.actor_id,
                        anomaly_type="HIGH_DISPLACEMENT",
                        z_score=z,
                        description=f"Displacement {features.displacement_km:.2f} km is {z:.1f}σ from mean {mu:.2f} km",
                    ))

        return events


# ---------------------------------------------------------------------------
# Threat scorer
# ---------------------------------------------------------------------------

class ThreatScorer:
    """Multi-factor Bayesian-inspired threat scoring.

    Factors:
      - affiliation: HOSTILE=1.0, UNKNOWN=0.5, NEUTRAL=0.2, FRIENDLY=0.0
      - speed: normalized against configurable max (default 30 m/s)
      - course_variance: erratic movement → higher threat
      - source_reliability: SDR < MESH < ATAK < MANUAL
      - is_anomaly: flat bonus if flagged
    """

    SOURCE_RELIABILITY = {
        "ATAK": 1.0,
        "MANUAL": 0.9,
        "MESH": 0.75,
        "SDR": 0.6,
    }
    AFFILIATION_WEIGHTS = {
        "HOSTILE": 1.0,
        "UNKNOWN": 0.5,
        "NEUTRAL": 0.15,
        "FRIENDLY": 0.0,
    }

    def __init__(self, max_speed_mps: float = 30.0) -> None:
        self.max_speed_mps = max_speed_mps

    def score(
        self,
        features: MovementFeatures,
        affiliation: str = "UNKNOWN",
        source: str = "MANUAL",
        is_anomaly: bool = False,
    ) -> ThreatScore:
        if features.observation_count < MIN_OBSERVATIONS:
            return ThreatScore(
                actor_id=features.actor_id,
                score=0.0,
                threat_level=ThreatLevel.UNKNOWN,
            )

        aff_score = self.AFFILIATION_WEIGHTS.get(affiliation.upper(), 0.5)
        reliability = self.SOURCE_RELIABILITY.get(source.upper(), 0.7)
        speed_score = min(1.0, features.speed_mean_mps / self.max_speed_mps)
        course_score = min(1.0, features.course_variance_deg / 90.0)
        anomaly_bonus = 0.2 if is_anomaly else 0.0

        # Weighted composite
        raw = (
            aff_score * 0.40
            + speed_score * 0.20
            + course_score * 0.15
            + (1.0 - reliability) * 0.10   # lower reliability → higher uncertainty
            + anomaly_bonus * 0.15
        )
        score = min(1.0, raw)

        if score >= 0.75:
            level = ThreatLevel.CRITICAL
        elif score >= 0.55:
            level = ThreatLevel.HIGH
        elif score >= 0.30:
            level = ThreatLevel.MEDIUM
        else:
            level = ThreatLevel.LOW

        return ThreatScore(
            actor_id=features.actor_id,
            score=score,
            threat_level=level,
            is_anomaly=is_anomaly,
            components={
                "affiliation": aff_score,
                "speed": speed_score,
                "course_variance": course_score,
                "source_unreliability": 1.0 - reliability,
                "anomaly_bonus": anomaly_bonus,
            },
        )


# ---------------------------------------------------------------------------
# DO GPU vLLM integration
# ---------------------------------------------------------------------------

class LlmThreatAnalyst:
    """Offloads narrative threat assessment to DO GPU vLLM endpoint.

    Uses qwen2.5-vl-72b via OpenAI-compatible API. Generates a
    concise tactical assessment paragraph for HIGH/CRITICAL actors.
    Non-blocking — returns None gracefully if the endpoint is down.
    """

    def __init__(
        self,
        host: str = DO_GPU_HOST,
        port: int = DO_GPU_PORT,
        api_key: str = DO_GPU_API_KEY,
        model: str = DO_GPU_MODEL,
        timeout: float = DO_GPU_TIMEOUT,
    ) -> None:
        self.base_url = f"http://{host}:{port}/v1"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client: Any = None
        self._available = True

    async def connect(self) -> None:
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            logger.info("llm_analyst_connected", host=DO_GPU_HOST, model=self.model)
        except ImportError:
            logger.warning("httpx_not_available", impact="llm_assessment_disabled")
            self._available = False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()

    async def assess(
        self,
        actor_id: UUID,
        features: MovementFeatures,
        threat_score: ThreatScore,
        affiliation: str,
        callsign: str = "",
    ) -> Optional[str]:
        """Generate a tactical assessment for a high-threat actor.

        Returns the LLM narrative or None if unavailable/timeout.
        Only called for HIGH or CRITICAL actors to conserve API budget.
        """
        if not self._available or self._client is None:
            return None
        if threat_score.threat_level not in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            return None

        prompt = (
            f"Tactical actor assessment:\n"
            f"  Callsign: {callsign or str(actor_id)[:8]}\n"
            f"  Affiliation: {affiliation}\n"
            f"  Threat score: {threat_score.score:.2f} ({threat_score.threat_level.value})\n"
            f"  Mean speed: {features.speed_mean_mps:.1f} m/s\n"
            f"  Max speed: {features.speed_max_mps:.1f} m/s\n"
            f"  Course variance: {features.course_variance_deg:.1f}°\n"
            f"  Displacement: {features.displacement_km:.2f} km\n"
            f"  Anomaly detected: {threat_score.is_anomaly}\n\n"
            f"Provide a 2-sentence tactical assessment of this actor's "
            f"behaviour and recommended action. Be concise and use military brevity."
        )

        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("llm_assess_failed", actor_id=str(actor_id), error=str(exc))
            self._available = False  # back off — avoid hammering a down endpoint
            return None


# ---------------------------------------------------------------------------
# ML Analytics Engine
# ---------------------------------------------------------------------------

class MlAnalyticsEngine:
    """Orchestrates movement analysis, anomaly detection, and threat scoring.

    Maintains per-actor observation histories and runs the full
    analysis pipeline on each ingest cycle. Publishes results to
    MQTT for downstream consumers (React dashboard, Neo4j writer).

    Lifecycle:
        engine = MlAnalyticsEngine(settings, publisher)
        await engine.start()
        engine.ingest(actor_id, obs)   # called on each actor update
        await engine.stop()
    """

    def __init__(
        self,
        publisher: Any = None,
        enable_llm: bool = True,
        do_gpu_host: str = DO_GPU_HOST,
        analysis_interval_secs: float = 10.0,
    ) -> None:
        self.publisher = publisher
        self.enable_llm = enable_llm
        self.analysis_interval_secs = analysis_interval_secs

        self._histories: dict[UUID, ActorHistory] = defaultdict(ActorHistory)
        self._actor_meta: dict[UUID, dict[str, str]] = {}  # affiliation, source, callsign
        self._latest_scores: dict[UUID, ThreatScore] = {}

        self._movement = MovementAnalyzer()
        self._anomaly = AnomalyDetector()
        self._scorer = ThreatScorer()
        self._llm: Optional[LlmThreatAnalyst] = None
        self._analysis_task: Optional[asyncio.Task] = None

        if enable_llm:
            self._llm = LlmThreatAnalyst(host=do_gpu_host)

    async def start(self) -> None:
        if self._llm:
            await self._llm.connect()
        self._analysis_task = asyncio.create_task(self._analysis_loop())
        logger.info("ml_analytics_started", llm_enabled=self.enable_llm)

    async def stop(self) -> None:
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass
        if self._llm:
            await self._llm.disconnect()
        logger.info("ml_analytics_stopped")

    def ingest(
        self,
        actor_id: UUID,
        obs: PositionObservation,
        affiliation: str = "UNKNOWN",
        source: str = "MANUAL",
        callsign: str = "",
    ) -> None:
        """Record a new observation for an actor."""
        self._histories[actor_id].add(obs)
        self._actor_meta[actor_id] = {
            "affiliation": affiliation,
            "source": source,
            "callsign": callsign,
        }

    async def _analysis_loop(self) -> None:
        """Periodic full-population analysis cycle."""
        while True:
            try:
                await asyncio.sleep(self.analysis_interval_secs)
                await self._run_analysis()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("analysis_loop_error", error=str(exc))

    async def _run_analysis(self) -> None:
        if not self._histories:
            return

        # Extract features for all actors
        all_features: list[MovementFeatures] = []
        for actor_id, history in self._histories.items():
            if len(history) < 2:
                continue
            features = self._movement.extract(actor_id, history)
            all_features.append(features)

        if not all_features:
            return

        # Update anomaly detector population baseline
        self._anomaly.update_population(all_features)

        # Score each actor
        for features in all_features:
            actor_id = features.actor_id
            meta = self._actor_meta.get(actor_id, {})
            affiliation = meta.get("affiliation", "UNKNOWN")
            source = meta.get("source", "MANUAL")
            callsign = meta.get("callsign", "")

            anomaly_events = self._anomaly.detect(features)
            is_anomaly = len(anomaly_events) > 0

            threat = self._scorer.score(features, affiliation, source, is_anomaly)

            # Optionally enrich with LLM assessment
            if self._llm and threat.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
                threat.llm_assessment = await self._llm.assess(
                    actor_id, features, threat, affiliation, callsign
                )

            self._latest_scores[actor_id] = threat

            # Publish
            if self.publisher:
                await self.publisher.publish(
                    TOPIC_THREAT_SCORES,
                    json.dumps(threat.to_mqtt_payload()),
                )
                for event in anomaly_events:
                    await self.publisher.publish(
                        TOPIC_ANOMALIES,
                        json.dumps(event.to_mqtt_payload()),
                    )

            if is_anomaly or threat.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
                logger.warning(
                    "threat_detected",
                    actor_id=str(actor_id),
                    callsign=callsign,
                    level=threat.threat_level.value,
                    score=round(threat.score, 3),
                    anomaly=is_anomaly,
                )

        logger.info("analysis_cycle_complete", actors_scored=len(all_features))

    def get_threat_score(self, actor_id: UUID) -> Optional[ThreatScore]:
        return self._latest_scores.get(actor_id)

    def get_all_scores(self) -> dict[UUID, ThreatScore]:
        return dict(self._latest_scores)

    def top_threats(self, n: int = 10) -> list[ThreatScore]:
        """Return top-N actors sorted by threat score descending."""
        return sorted(
            self._latest_scores.values(),
            key=lambda t: t.score,
            reverse=True,
        )[:n]
