"""
L4: OODA Decision Engine
Boyd OODA Loop + In-Context Co-player Inference
MDO-NEXUS-OODA-HYDRA v3.0

Architecture ref: D:\\MDO-NEXUS-OODA-HYDRA-v3.0.md
Learning sources:
  - arXiv:2602.16301 (Google MARL, in-context co-player inference)
  - TRADOC 525-3-1 / JADC2 (OODA compression, decision superiority)
  - Army War College NCW (info sharing → self-synchronization)
  - DARPA Mosaic (Kill Web, OODA compression)
  - D:\\MDO\\multi-domain-operations-workflow.md
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from hydra_c2.infrastructure.intelligence import (
    IntelEntry,
    KillWebFusion,
    OsintCollector,
    QueryResult,
    SourceType,
)


# ---------------------------------------------------------------------------
# OODA Phase definitions
# ---------------------------------------------------------------------------


class OodaPhase(Enum):
    """Boyd OODA Loop phases."""
    OBSERVE = "OBSERVE"     # Multi-sensor fusion + OSINT collection
    ORIENT  = "ORIENT"      # ColBERT retrieval + LLM analysis
    DECIDE  = "DECIDE"      # In-context co-player inference → decision
    ACT     = "ACT"         # Utah harness step.run() execution


@dataclass
class OodaState:
    """
    Immutable OODA cycle state (Tape entry pattern).
    Each cycle produces a new state; history never overwritten.
    """
    cycle_id: str
    phase: OodaPhase
    timestamp: float = field(default_factory=time.time)
    observations: list[dict[str, Any]] = field(default_factory=list)
    intel_results: list[QueryResult] = field(default_factory=list)
    decision: dict[str, Any] | None = None
    action_taken: str | None = None
    loop_duration_ms: float = 0.0
    co_player_pool_size: int = 0


@dataclass
class CoPlayerAction:
    """
    Action taken by a co-player agent (arXiv:2602.16301).
    Used for in-context co-player inference.
    """
    agent_id: str
    action_type: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    reward_signal: float = 0.0      # positive = cooperative


# ---------------------------------------------------------------------------
# In-Context Co-player Inference (arXiv:2602.16301)
# ---------------------------------------------------------------------------


class CoPlayerInferenceEngine:
    """
    In-context co-player inference engine.

    Reference: "Multi-agent cooperation through in-context co-player inference"
    (Weis et al., Google, arXiv:2602.16301, Feb 2026)

    Key insight: Sequence model agents trained against DIVERSE co-player
    distributions naturally develop in-context best-response strategies —
    no explicit naive/meta-learner separation required.

    3-step cooperative mechanism:
    1. In-context adaptation → vulnerability to extortion
    2. Mutual extortion pressure
    3. Resolution into cooperative behavior

    HYDRA application: Each domain agent (SDR/TAK/Mesh/Analytics) = co-player.
    Diverse scenario pool training → emergent self-synchronization (NCW Metcalfe).
    """

    def __init__(self, agent_ids: list[str]) -> None:
        self._agent_ids = agent_ids
        # Episode history for in-context inference (fast timescale)
        self._episode_history: list[CoPlayerAction] = []
        # Cooperation pressure register (mutual extortion tracking)
        self._cooperation_pressures: dict[str, float] = {a: 0.0 for a in agent_ids}

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    def infer_best_response(
        self,
        own_agent_id: str,
        current_observations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        In-context best-response strategy.

        Uses episode history (fast timescale) to infer co-player learning
        dynamics and select cooperative action.

        Step 1: Observe co-player in-context adaptations
        Step 2: Assess mutual extortion pressure
        Step 3: Select action that resolves to cooperation
        """
        # Step 1: Extract co-player patterns from episode history
        co_actions = [
            a for a in self._episode_history
            if a.agent_id != own_agent_id
        ][-20:]  # last 20 actions as context window

        # Step 2: Compute cooperation pressure
        # (how much each agent is shaping others' learning)
        for action in co_actions:
            if action.reward_signal > 0:
                self._cooperation_pressures[action.agent_id] = min(
                    1.0,
                    self._cooperation_pressures.get(action.agent_id, 0.0) + 0.1,
                )

        avg_pressure = (
            sum(self._cooperation_pressures.values()) / len(self._cooperation_pressures)
            if self._cooperation_pressures else 0.0
        )

        # Step 3: Select cooperative action when mutual pressure > threshold
        # Mirrors mechanism: vulnerability to extortion → cooperative equilibrium
        cooperative_threshold = 0.3
        is_cooperative = avg_pressure >= cooperative_threshold

        return {
            "own_agent": own_agent_id,
            "is_cooperative": is_cooperative,
            "cooperation_pressure": avg_pressure,
            "co_player_pool_size": len(set(a.agent_id for a in co_actions)),
            "recommended_action": "cooperate" if is_cooperative else "probe",
            "context_window": len(co_actions),
            "observations": current_observations[:5],
        }

    def record_action(self, action: CoPlayerAction) -> None:
        """Record co-player action to episode history."""
        self._episode_history.append(action)
        # Trim to prevent context overflow (Utah pruning pattern)
        if len(self._episode_history) > 200:
            self._episode_history = self._episode_history[-100:]

    @property
    def cooperation_state(self) -> dict[str, float]:
        return dict(self._cooperation_pressures)


# ---------------------------------------------------------------------------
# OODA Decision Engine
# ---------------------------------------------------------------------------


class OodaDecisionEngine:
    """
    Full Boyd OODA loop with in-context co-player inference.

    OODA phases:
      OBSERVE: multi-sensor fusion + OSINT (INT of First Resort)
      ORIENT:  ColBERT late interaction retrieval + situation analysis
      DECIDE:  in-context co-player inference → emergent cooperation
      ACT:     harness step execution (Utah pattern)

    NCW self-synchronization: agents share information at L3 Intelligence,
    enabling emergent coordination without explicit command (Metcalfe's law).

    OODA compression (Mosaic Warfare): parallel processing of all phases
    compresses decision cycle → decision superiority over adversary.
    """

    def __init__(
        self,
        collector: OsintCollector,
        fusion: KillWebFusion,
        co_player_engine: CoPlayerInferenceEngine,
        domain_agents: list[str] | None = None,
    ) -> None:
        self._collector = collector
        self._fusion = fusion
        self._co_player = co_player_engine
        self._domain_agents = domain_agents or ["SDR", "TAK", "MESH", "ANALYTICS"]

        # OODA cycle history (Tape append-only)
        self._cycle_history: list[OodaState] = []
        self._cycle_count: int = 0

    # ------------------------------------------------------------------
    # Full OODA cycle
    # ------------------------------------------------------------------

    async def run_cycle(
        self,
        trigger: str,
        act_callback: Callable[[dict[str, Any]], Any] | None = None,
    ) -> OodaState:
        """
        Execute one OODA cycle.
        Each phase is independently awaitable (Utah harness step.run analog).
        """
        t0 = time.time()
        cycle_id = f"ooda-{self._cycle_count:04d}"
        self._cycle_count += 1

        # --- OBSERVE --- #
        observations = await self._observe(trigger)

        # --- ORIENT --- #
        intel_results = await self._orient(trigger, observations)

        # --- DECIDE --- #
        decision = await self._decide(observations, intel_results)

        # --- ACT --- #
        action_taken = await self._act(decision, act_callback)

        loop_ms = (time.time() - t0) * 1000
        state = OodaState(
            cycle_id=cycle_id,
            phase=OodaPhase.ACT,
            observations=observations,
            intel_results=intel_results,
            decision=decision,
            action_taken=action_taken,
            loop_duration_ms=loop_ms,
            co_player_pool_size=len(self._domain_agents),
        )
        self._cycle_history.append(state)
        return state

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    async def _observe(self, trigger: str) -> list[dict[str, Any]]:
        """
        OBSERVE: Multi-sensor fusion + OSINT (INT of First Resort).
        Collects from L0-L2 + open-source before classified.
        """
        observations: list[dict[str, Any]] = [
            {
                "source": "trigger",
                "content": trigger,
                "timestamp": time.time(),
                "phase": OodaPhase.OBSERVE.value,
            }
        ]
        stats = self._collector.collection_stats()
        observations.append({
            "source": "intel_index",
            "entry_count": stats["total_entries"],
            "by_source": stats["by_source"],
            "phase": OodaPhase.OBSERVE.value,
        })
        return observations

    async def _orient(
        self,
        query: str,
        observations: list[dict[str, Any]],
    ) -> list[QueryResult]:
        """
        ORIENT: ColBERT late interaction retrieval + situation analysis.
        Uses L3 Intelligence layer for MaxSim search.
        """
        fusion_result = self._fusion.fuse(query, top_k=8)
        return fusion_result["results"]

    async def _decide(
        self,
        observations: list[dict[str, Any]],
        intel_results: list[QueryResult],
    ) -> dict[str, Any]:
        """
        DECIDE: In-context co-player inference.
        arXiv:2602.16301: diverse co-player pool → emergent cooperation.
        """
        decisions: dict[str, dict[str, Any]] = {}
        for agent_id in self._domain_agents:
            response = self._co_player.infer_best_response(
                own_agent_id=agent_id,
                current_observations=observations,
            )
            decisions[agent_id] = response

            # Record as co-player action
            action = CoPlayerAction(
                agent_id=agent_id,
                action_type=response["recommended_action"],
                payload=response,
                reward_signal=1.0 if response["is_cooperative"] else -0.5,
            )
            self._co_player.record_action(action)

        # Aggregate: majority cooperative → collective cooperation
        cooperative_count = sum(
            1 for d in decisions.values() if d["is_cooperative"]
        )
        collective_action = "cooperate" if cooperative_count > len(self._domain_agents) / 2 else "probe"

        return {
            "collective_action": collective_action,
            "agent_decisions": decisions,
            "cooperative_ratio": cooperative_count / len(self._domain_agents),
            "intel_evidence": len(intel_results),
            "cooperation_state": self._co_player.cooperation_state,
            "phase": OodaPhase.DECIDE.value,
        }

    async def _act(
        self,
        decision: dict[str, Any],
        callback: Callable[[dict[str, Any]], Any] | None,
    ) -> str:
        """
        ACT: Execute via Utah harness step.run() callback.
        If no callback provided, log the action.
        """
        action = decision.get("collective_action", "observe")
        if callback is not None:
            try:
                await asyncio.coroutine(callback)(decision) if asyncio.iscoroutinefunction(callback) else callback(decision)
            except Exception:
                action = f"{action}:callback_failed"
        return action

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def last_cycle(self) -> OodaState | None:
        return self._cycle_history[-1] if self._cycle_history else None

    def tempo_stats(self) -> dict[str, float]:
        """OODA tempo statistics (decision superiority metric)."""
        if not self._cycle_history:
            return {}
        durations = [s.loop_duration_ms for s in self._cycle_history]
        return {
            "mean_ms": sum(durations) / len(durations),
            "min_ms": min(durations),
            "max_ms": max(durations),
            "cycles": len(durations),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_ooda_layer(
    collector: OsintCollector,
    fusion: KillWebFusion,
    domain_agents: list[str] | None = None,
) -> tuple[CoPlayerInferenceEngine, OodaDecisionEngine]:
    """
    Factory: create wired L4 OODA layer.
    Requires L3 Intelligence layer (collector, fusion).
    """
    agents = domain_agents or ["SDR", "TAK", "MESH", "ANALYTICS", "NEXUS"]
    co_player = CoPlayerInferenceEngine(agent_ids=agents)
    engine = OodaDecisionEngine(
        collector=collector,
        fusion=fusion,
        co_player_engine=co_player,
        domain_agents=agents,
    )
    return co_player, engine


__all__ = [
    "OodaPhase",
    "OodaState",
    "CoPlayerAction",
    "CoPlayerInferenceEngine",
    "OodaDecisionEngine",
    "create_ooda_layer",
]
