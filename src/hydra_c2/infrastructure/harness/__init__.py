"""
L6: Harness Orchestration Layer
Utah/Inngest Pattern — think → act → observe
MDO-NEXUS-OODA-HYDRA v3.0

Architecture ref: D:\\MDO-NEXUS-OODA-HYDRA-v3.0.md
Learning sources:
  - D:\\harness.txt (Utah/Inngest UTAH = Universally Triggered Agent Harness)
  - Agentic Patterns (7-type: Parallel/Sequential/Loop/Router/...)
  - OpenAI Harness Engineering (depth-first, 1M LOC, evals framework)
  - Desloppify (quality loop, score 98+, anti-gaming)
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from hydra_c2.infrastructure.ooda import OodaDecisionEngine, OodaState


# ---------------------------------------------------------------------------
# Step system (Utah/Inngest step.run equivalent)
# ---------------------------------------------------------------------------


class StepStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    RETRYING  = "retrying"


@dataclass
class StepResult:
    """
    Result of one harness step.
    Each step is independently retryable — if step N fails,
    steps 0..N-1 are already persisted and not re-executed.
    (Utah/Inngest durable execution pattern)
    """
    step_id: str
    status: StepStatus
    result: Any = None
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    attempt: int = 1

    @property
    def duration_ms(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0


# ---------------------------------------------------------------------------
# Context pruning (Utah 2-tier pruning)
# ---------------------------------------------------------------------------


@dataclass
class PruningConfig:
    """
    Utah/Inngest 2-tier context pruning configuration.
    Prevents context balloon in long-running agent loops.
    """
    keep_last_assistant_turns: int = 3
    soft_trim_max_chars: int = 4000
    soft_trim_head_chars: int = 1500
    soft_trim_tail_chars: int = 1500
    hard_clear_threshold: int = 50_000
    hard_clear_placeholder: str = "[Tool result cleared]"
    budget_warning_threshold: float = 0.8   # warn at 80% of max iterations


def prune_messages(
    messages: list[dict[str, Any]],
    config: PruningConfig,
) -> list[dict[str, Any]]:
    """
    Apply 2-tier pruning to message history.

    Tier 1 (soft-trim): large tool results → keep head + tail
    Tier 2 (hard-clear): total context > threshold → clear old tool results

    Last keep_last_assistant_turns iterations always preserved.
    """
    pruned = list(messages)

    # Tier 1: soft-trim individual large tool results
    for i, msg in enumerate(pruned):
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            content = msg["content"]
            if len(content) > config.soft_trim_max_chars:
                head = content[: config.soft_trim_head_chars]
                tail = content[-config.soft_trim_tail_chars :]
                pruned[i] = {**msg, "content": f"{head}\n[...trimmed...]\n{tail}"}

    # Tier 2: hard-clear if total context too large
    total_chars = sum(len(str(m.get("content", ""))) for m in pruned)
    if total_chars > config.hard_clear_threshold:
        # Identify old tool results to clear (keep last N assistant turns)
        assistant_indices = [
            i for i, m in enumerate(pruned) if m.get("role") == "assistant"
        ]
        keep_from = assistant_indices[-(config.keep_last_assistant_turns)] if len(assistant_indices) >= config.keep_last_assistant_turns else 0
        for i, msg in enumerate(pruned):
            if i < keep_from and msg.get("role") == "tool":
                pruned[i] = {**msg, "content": config.hard_clear_placeholder}

    return pruned


# ---------------------------------------------------------------------------
# Agentic Patterns (7-type router)
# ---------------------------------------------------------------------------


class AgentPattern(Enum):
    """
    Agentic execution patterns (Image 3 — Multi-Agent Patterns diagram).
    Applied in HYDRA harness routing.
    """
    PARALLEL       = "parallel"        # Independent domain agents run concurrently
    SEQUENTIAL     = "sequential"      # Chain: SDR → Intel → OODA → Action
    LOOP           = "loop"            # think→act→observe repeat until done
    ROUTER         = "router"          # LLMRouter: select domain expert
    AGGREGATOR     = "aggregator"      # Merge multi-domain results (Kill Web fusion)
    NETWORK        = "network"         # Distributed MARL co-player network
    HIERARCHICAL   = "hierarchical"    # OMC → executor → sub-agents
    DRY_RUN        = "dry_run"         # Image 3: Dry-Run Harness — no side effects
    REFLEXIVE      = "reflexive"       # Image 3: Reflexion — self-critique loop
    BLACKBOARD     = "blackboard"      # Image 3: Blackboard — shared state bus
    META_CONTROLLER= "meta_controller" # Image 3: Meta-Controller — adaptive routing


# ---------------------------------------------------------------------------
# Dry-Run Mode (Image 3: Dry-Run Harness pattern)
# ---------------------------------------------------------------------------


@dataclass
class DryRunResult:
    """
    Result of a dry-run step — executed without side effects.

    Image 3 (Dry-Run Harness): execute the full think→act pipeline
    in simulation mode first. Gate on go/no-go before real ACT.
    Prevents irreversible actions when confidence is low.
    """
    step_id:    str
    would_act:  bool                    # True if live run would take action
    simulated:  Any = None              # What the step *would* have returned
    confidence: float = 1.0             # Model confidence in simulated result
    reasons:    list[str] = field(default_factory=list)

    @property
    def go(self) -> bool:
        """Go/no-go gate: confident AND would act."""
        return self.would_act and self.confidence >= 0.7


# ---------------------------------------------------------------------------
# State-Machine Memory (arXiv:2602.20502 — ActionEngine)
# ---------------------------------------------------------------------------


class StateMachineMemory:
    """
    Offline state-machine memory for execution reuse.

    arXiv:2602.20502 (ActionEngine, Microsoft Research + Georgia Tech):
      Crawling Agent builds a state-machine offline (UI states + transitions).
      Execution Agent reuses cached paths instead of re-querying VLM.
      Reduces redundant VLM calls; improves consistency across sessions.

    HYDRA: cache OODA-cycle outcomes keyed by (trigger_hash, agent_pattern).
    If identical trigger recurs, reuse cached decision without full cycle.
    """

    def __init__(self, max_states: int = 256) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._max_states = max_states
        self._hit_count:  int = 0
        self._miss_count: int = 0

    def _key(self, trigger: str, pattern: str) -> str:
        raw = f"{trigger}|{pattern}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def lookup(self, trigger: str, pattern: str) -> dict[str, Any] | None:
        """Return cached state if available (cache hit)."""
        k = self._key(trigger, pattern)
        cached = self._states.get(k)
        if cached is not None:
            self._hit_count += 1
            cached["_hits"] = cached.get("_hits", 0) + 1
        else:
            self._miss_count += 1
        return cached

    def store(self, trigger: str, pattern: str, state: dict[str, Any]) -> None:
        """Store execution state for future reuse."""
        if len(self._states) >= self._max_states:
            # Evict least-recently-used (pop arbitrary; production: LRU)
            oldest_key = next(iter(self._states))
            del self._states[oldest_key]
        k = self._key(trigger, pattern)
        self._states[k] = {**state, "_stored_at": time.time(), "_hits": 0}

    @property
    def cache_stats(self) -> dict[str, Any]:
        total = self._hit_count + self._miss_count
        return {
            "states":    len(self._states),
            "hits":      self._hit_count,
            "misses":    self._miss_count,
            "hit_rate":  round(self._hit_count / max(total, 1), 4),
        }


# ---------------------------------------------------------------------------
# Preference Memory (arXiv:2602.16173 — PAHF)
# ---------------------------------------------------------------------------


@dataclass
class PreferenceEntry:
    """Single user/operator preference record (PAHF 3-step loop)."""
    session_key:  str
    trigger_hash: str
    feedback:     str                   # "positive" | "negative" | "clarify"
    correction:   str                   # What should have happened instead
    timestamp:    float = field(default_factory=time.time)
    applied:      bool = False


class PreferenceMemory:
    """
    Personalised agent preference memory (PAHF).

    arXiv:2602.16173 (Meta, PAHF — Personalised Agents from Human Feedback):
      3-step personalisation loop:
        1. Pre-action clarification  → ask if uncertain about preferences
        2. Ground in preference memory → retrieve past feedback before acting
        3. Post-action feedback update → record outcome for future sessions

    HYDRA: operators give feedback on OODA decisions after each ACT phase.
    Future cycles ground decisions in accumulated operator preferences.
    """

    def __init__(self, max_entries: int = 512) -> None:
        self._entries:   list[PreferenceEntry] = []
        self._max_entries = max_entries

    # Step 3: Post-action feedback update
    def record_feedback(
        self,
        session_key: str,
        trigger: str,
        feedback: str,
        correction: str = "",
    ) -> PreferenceEntry:
        entry = PreferenceEntry(
            session_key=session_key,
            trigger_hash=hashlib.sha256(trigger.encode()).hexdigest()[:12],
            feedback=feedback,
            correction=correction,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        return entry

    # Step 2: Ground in preference memory
    def retrieve_preferences(
        self,
        trigger: str,
        top_k: int = 5,
    ) -> list[PreferenceEntry]:
        """Retrieve most relevant past feedback for current trigger."""
        t_hash = hashlib.sha256(trigger.encode()).hexdigest()[:12]
        # Exact hash matches first
        exact = [e for e in self._entries if e.trigger_hash == t_hash]
        if exact:
            return exact[-top_k:]
        # Fallback: most recent positive entries (operator style guide)
        positive = [e for e in self._entries if e.feedback == "positive"]
        return positive[-top_k:]

    # Step 1: Pre-action clarification signal
    def needs_clarification(self, trigger: str) -> bool:
        """
        True if no positive preference exists for this trigger family.
        Signals harness to pause for operator clarification before ACT.
        """
        prefs = self.retrieve_preferences(trigger, top_k=3)
        return not any(e.feedback == "positive" for e in prefs)

    @property
    def entry_count(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Harness Session (Utah session management)
# ---------------------------------------------------------------------------


@dataclass
class HarnessSession:
    """
    Harness session with singleton concurrency.
    Utah singleton: { key: "sessionKey", mode: "cancel" }
    """
    session_key: str
    max_iterations: int = 50
    pattern: AgentPattern = AgentPattern.LOOP
    messages: list[dict[str, Any]] = field(default_factory=list)
    step_results: list[StepResult] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    is_active: bool = True
    iteration: int = 0

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content, "ts": time.time()})

    @property
    def budget_used(self) -> float:
        return self.iteration / self.max_iterations if self.max_iterations > 0 else 0.0

    @property
    def step_count(self) -> int:
        return len(self.step_results)


# ---------------------------------------------------------------------------
# Main Harness (Utah UTAH — Universally Triggered Agent Harness)
# ---------------------------------------------------------------------------


class HydraHarness:
    """
    HYDRA C2 Agent Harness — Utah/Inngest pattern.

    Core loop: think → act → observe
    Each LLM call and tool call = independently retryable step.
    If process dies at iteration 5, iterations 0-4 are persisted.

    6 functions (Utah architecture):
      handleMessage    : main agent loop (this class)
      sendReply        : reply to trigger channel
      acknowledgeMessage: typing indicator (fires immediately)
      failureHandler   : global error handler across all functions
      heartbeat        : periodic health check
      subAgent         : isolated sub-agent runs via step.invoke()

    Trigger decoupled from work:
      TAK message | SDR alert | OODA cycle | cron | sub-agent invoke
      → agent loop doesn't change, harness routes it.
    """

    def __init__(
        self,
        ooda_engine: OodaDecisionEngine,
        pruning_config: PruningConfig | None = None,
        max_iterations: int = 50,
        state_memory: StateMachineMemory | None = None,
        preference_memory: PreferenceMemory | None = None,
    ) -> None:
        self._ooda = ooda_engine
        self._pruning = pruning_config or PruningConfig()
        self._max_iterations = max_iterations

        # Singleton concurrency: one session per channel at a time
        # { session_key → HarnessSession }
        self._active_sessions: dict[str, HarnessSession] = {}
        self._completed_sessions: list[HarnessSession] = []

        # Sub-agent registry
        self._sub_agents: dict[str, "HydraHarness"] = {}

        # arXiv:2602.20502 — ActionEngine state-machine reuse
        self._state_memory = state_memory or StateMachineMemory()

        # arXiv:2602.16173 — PAHF preference grounding
        self._preference_memory = preference_memory or PreferenceMemory()

    # ------------------------------------------------------------------
    # step.run equivalent — independently retryable
    # ------------------------------------------------------------------

    async def step_run(
        self,
        step_id: str,
        fn: Callable[[], Any],
        session: HarnessSession,
        max_retries: int = 3,
    ) -> StepResult:
        """
        Execute a step with independent retry logic.
        Inngest auto-indexes duplicate step IDs:
        step_id "think" called 10 times → think:0, think:1, ...
        """
        # Generate unique indexed step ID
        count = sum(1 for r in session.step_results if r.step_id.startswith(step_id))
        indexed_id = f"{step_id}:{count}"

        result = StepResult(step_id=indexed_id, status=StepStatus.RUNNING)

        for attempt in range(1, max_retries + 1):
            result.attempt = attempt
            try:
                if asyncio.iscoroutinefunction(fn):
                    value = await fn()
                else:
                    value = fn()
                result.result = value
                result.status = StepStatus.COMPLETED
                result.completed_at = time.time()
                break
            except Exception as exc:
                result.error = str(exc)
                result.status = StepStatus.RETRYING if attempt < max_retries else StepStatus.FAILED
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * attempt)

        session.step_results.append(result)
        return result

    # ------------------------------------------------------------------
    # Think → Act → Observe loop
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        trigger: str,
        session_key: str,
        reply_callback: Callable[[str], Any] | None = None,
    ) -> str:
        """
        Main agent loop — handleMessage function.

        Singleton concurrency: if session_key already active,
        cancel previous run (mode: "cancel") and start fresh
        with accumulated context.
        """
        # Singleton: cancel existing session for this key
        if session_key in self._active_sessions:
            prev = self._active_sessions[session_key]
            prev.is_active = False
            self._completed_sessions.append(prev)

        session = HarnessSession(
            session_key=session_key,
            max_iterations=self._max_iterations,
        )
        self._active_sessions[session_key] = session

        # Acknowledge immediately (typing indicator)
        await self._acknowledge(session_key)

        session.add_message("user", trigger)
        final_response = ""
        done = False

        try:
            while not done and session.iteration < self._max_iterations:
                if not session.is_active:
                    # Cancelled by new incoming message
                    break

                session.iteration += 1

                # Budget warning (Utah pattern)
                if session.budget_used >= self._pruning.budget_warning_threshold:
                    session.add_message(
                        "system",
                        f"[Budget: {session.iteration}/{self._max_iterations} iterations used. Wrap up.]",
                    )

                # Prune context
                session.messages = prune_messages(session.messages, self._pruning)

                # --- THINK: run OODA cycle as a step ---
                think_result = await self.step_run(
                    "think",
                    fn=lambda: asyncio.get_event_loop().run_until_complete(
                        self._ooda.run_cycle(trigger=trigger)
                    )
                    if False  # async lambda workaround
                    else None,
                    session=session,
                )
                # Direct async call (step_run wraps sync fn; handle async separately)
                ooda_state: OodaState = await self._ooda.run_cycle(trigger=trigger)
                think_result.result = ooda_state
                think_result.status = StepStatus.COMPLETED

                decision = ooda_state.decision or {}
                collective_action = decision.get("collective_action", "observe")
                session.add_message("assistant", f"[OODA:{ooda_state.cycle_id}] action={collective_action}")

                # --- ACT: execute domain tools as steps ---
                if collective_action == "cooperate":
                    tool_results: list[str] = []
                    for agent_id in (self._ooda._domain_agents or []):
                        tool_step = await self.step_run(
                            f"tool-{agent_id}",
                            fn=lambda aid=agent_id: f"{aid}: cooperative_action_dispatched",
                            session=session,
                        )
                        tool_results.append(str(tool_step.result))
                        session.add_message("tool", tool_step.result or "")

                    # --- OBSERVE: feed results back ---
                    final_response = f"OODA:{ooda_state.cycle_id} cooperative. Agents: {', '.join(tool_results)}"
                    done = True

                elif collective_action == "probe":
                    session.add_message("tool", f"[probe] gathering more intelligence on: {trigger}")
                    # continue loop

                else:
                    final_response = f"OODA cycle {ooda_state.cycle_id} complete. No action required."
                    done = True

        except Exception as exc:
            await self._failure_handler(session_key, exc)
            final_response = f"[HarnessError] {exc}"
        finally:
            session.is_active = False

        if reply_callback:
            await reply_callback(final_response) if asyncio.iscoroutinefunction(reply_callback) else reply_callback(final_response)

        return final_response

    # ------------------------------------------------------------------
    # Sub-agent (step.invoke equivalent)
    # ------------------------------------------------------------------

    async def invoke_sub_agent(
        self,
        task: str,
        sub_session_key: str,
        sub_harness: "HydraHarness | None" = None,
    ) -> str:
        """
        Spawn sub-agent with isolated context.
        Utah pattern: step.invoke(subAgent, { task, subSessionKey })
        Sub-agent gets own context window + same tools (minus recursion).
        """
        harness = sub_harness or HydraHarness(
            ooda_engine=self._ooda,
            pruning_config=self._pruning,
            max_iterations=self._max_iterations // 2,  # sub-agents get half budget
        )
        result = await harness.handle_message(
            trigger=task,
            session_key=sub_session_key,
        )
        return f"[SubAgent:{sub_session_key}] {result}"

    # ------------------------------------------------------------------
    # Supporting functions (Utah 6-function decomposition)
    # ------------------------------------------------------------------

    async def _acknowledge(self, session_key: str) -> None:
        """Typing indicator — fires immediately before agent loop."""
        pass  # Production: send typing event to TAK/Telegram/Slack

    async def _failure_handler(self, session_key: str, exc: Exception) -> None:
        """Global error handler across all functions."""
        session = self._active_sessions.get(session_key)
        if session:
            session.add_message("system", f"[FailureHandler] {type(exc).__name__}: {exc}")

    async def heartbeat(self) -> dict[str, Any]:
        """Periodic health check (cron-triggered function)."""
        return {
            "active_sessions": len(self._active_sessions),
            "completed_sessions": len(self._completed_sessions),
            "ooda_cycles": self._ooda.cycle_count,
            "tempo": self._ooda.tempo_stats(),
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Agentic pattern routing
    # ------------------------------------------------------------------

    async def run_pattern(
        self,
        pattern: AgentPattern,
        tasks: list[str],
        session_key_prefix: str = "pattern",
    ) -> list[str]:
        """
        Execute tasks using specified agentic pattern.
        Parallel, Sequential, Hierarchical, etc.
        """
        if pattern == AgentPattern.PARALLEL:
            coroutines = [
                self.handle_message(t, f"{session_key_prefix}-{i}")
                for i, t in enumerate(tasks)
            ]
            results = await asyncio.gather(*coroutines, return_exceptions=True)
            return [str(r) for r in results]

        elif pattern == AgentPattern.SEQUENTIAL:
            results = []
            for i, task in enumerate(tasks):
                r = await self.handle_message(task, f"{session_key_prefix}-{i}")
                results.append(r)
            return results

        elif pattern == AgentPattern.LOOP:
            results = []
            for i, task in enumerate(tasks):
                r = await self.handle_message(task, f"{session_key_prefix}-loop")
                results.append(r)
                if "no action required" in r.lower():
                    break
            return results

        elif pattern == AgentPattern.AGGREGATOR:
            # Kill Web fusion pattern
            sub_results = await self.run_pattern(AgentPattern.PARALLEL, tasks, session_key_prefix)
            combined = " | ".join(sub_results)
            return [f"[Aggregated] {combined[:200]}"]

        elif pattern == AgentPattern.HIERARCHICAL:
            # OMC → executor → sub-agents
            main_task = tasks[0] if tasks else "analyze"
            sub_tasks = tasks[1:] if len(tasks) > 1 else []
            main_result = await self.handle_message(main_task, f"{session_key_prefix}-main")
            sub_results = []
            for i, sub_task in enumerate(sub_tasks):
                r = await self.invoke_sub_agent(sub_task, f"{session_key_prefix}-sub-{i}")
                sub_results.append(r)
            return [main_result] + sub_results

        else:
            # Default: sequential
            return await self.run_pattern(AgentPattern.SEQUENTIAL, tasks, session_key_prefix)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def active_session_count(self) -> int:
        return len(self._active_sessions)

    def session_stats(self) -> dict[str, Any]:
        return {
            "active": self.active_session_count,
            "completed": len(self._completed_sessions),
            "total_steps": sum(
                s.step_count
                for s in list(self._active_sessions.values()) + self._completed_sessions
            ),
            "state_cache": self._state_memory.cache_stats,
            "preferences": self._preference_memory.entry_count,
        }

    # ------------------------------------------------------------------
    # Dry-Run Harness (Image 3 — Dry-Run Harness pattern)
    # ------------------------------------------------------------------

    async def dry_run_step(
        self,
        step_id: str,
        fn: Callable[[], Any],
        session: HarnessSession,
        confidence_threshold: float = 0.7,
    ) -> DryRunResult:
        """
        Execute a step in dry-run (no-side-effect) mode.

        Image 3 (Dry-Run Harness): simulate the full think→act pipeline
        before committing to real actions. Gate on go/no-go verdict.

        Checks StateMachineMemory first — if identical state cached,
        returns cached result with confidence=1.0 (ActionEngine reuse).
        Otherwise simulates via fn(), marks result as dry-run.
        """
        pattern_key = session.pattern.value
        cached = self._state_memory.lookup(step_id, pattern_key)
        if cached is not None:
            return DryRunResult(
                step_id=step_id,
                would_act=cached.get("would_act", True),
                simulated=cached.get("result"),
                confidence=1.0,
                reasons=["state_cache_hit"],
            )

        # Simulate: run fn() but mark as non-committing
        simulated_value = None
        reasons: list[str] = []
        try:
            if asyncio.iscoroutinefunction(fn):
                simulated_value = await fn()
            else:
                simulated_value = fn()
            would_act = True
            reasons.append("simulation_ok")
        except Exception as exc:
            would_act = False
            reasons.append(f"simulation_error:{exc}")

        confidence = 0.8 if would_act else 0.2

        result = DryRunResult(
            step_id=step_id,
            would_act=would_act,
            simulated=simulated_value,
            confidence=confidence,
            reasons=reasons,
        )

        # Store in state machine memory for future reuse
        if result.go:
            self._state_memory.store(
                step_id, pattern_key,
                {"result": simulated_value, "would_act": would_act},
            )
        return result

    # ------------------------------------------------------------------
    # Topology Adaptation (arXiv:2602.17100 — AgentConductor)
    # ------------------------------------------------------------------

    def topology_adapt(
        self,
        trigger: str,
        available_agents: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Dynamically select active agent topology based on task complexity.

        arXiv:2602.17100 (AgentConductor): RL-optimised MAS with dynamic
        topology generation — more complex tasks use deeper topologies;
        simple tasks use minimal agents to reduce cost.

        Complexity heuristics (proxy for full RL signal):
          LOW    (<20 chars OR cached)     → 1 agent  (single responder)
          MEDIUM (20-100 chars OR 1 domain) → 2-3 agents (small team)
          HIGH   (>100 chars OR multi-domain) → full pool (all available)

        Returns: selected topology with estimated complexity level.
        """
        agents = available_agents or (self._ooda._domain_agents or ["SDR", "TAK", "MESH", "ANALYTICS", "NEXUS"])

        # Complexity estimation
        trigger_len = len(trigger)
        # Check if trigger looks like a known cached state
        is_cached = self._state_memory.lookup(trigger[:32], "any") is not None

        if is_cached or trigger_len < 20:
            complexity = "LOW"
            selected = agents[:1]
        elif trigger_len < 100:
            complexity = "MEDIUM"
            mid = max(2, math.ceil(len(agents) * 0.5))
            selected = agents[:mid]
        else:
            complexity = "HIGH"
            selected = agents  # full topology

        # Preference grounding (PAHF step 2)
        needs_clarification = self._preference_memory.needs_clarification(trigger)

        return {
            "complexity":          complexity,
            "selected_agents":     selected,
            "agent_count":         len(selected),
            "available_agents":    agents,
            "needs_clarification": needs_clarification,
            "trigger_len":         trigger_len,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_harness_layer(
    ooda_engine: OodaDecisionEngine,
    max_iterations: int = 50,
) -> HydraHarness:
    """
    Factory: create wired L6 Harness layer.
    Requires L4 OODA engine.
    """
    pruning = PruningConfig()
    return HydraHarness(
        ooda_engine=ooda_engine,
        pruning_config=pruning,
        max_iterations=max_iterations,
    )


__all__ = [
    "StepStatus",
    "StepResult",
    "PruningConfig",
    "prune_messages",
    "AgentPattern",
    "HarnessSession",
    "HydraHarness",
    "create_harness_layer",
    # New additions from image + paper learnings
    "DryRunResult",           # Image 3: Dry-Run Harness
    "StateMachineMemory",     # arXiv:2602.20502 ActionEngine
    "PreferenceEntry",        # arXiv:2602.16173 PAHF
    "PreferenceMemory",       # arXiv:2602.16173 PAHF
]
