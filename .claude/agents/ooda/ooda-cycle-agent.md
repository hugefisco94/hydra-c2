---
name: ooda-cycle-agent
description: >
  L4 OODA Decision Engine specialist. Expert in Boyd loop orchestration,
  in-context co-player inference (arXiv:2602.16301), volatility-adaptive
  pressure (arXiv:2602.16928 VAD-CFR), think-depth metrics (arXiv:2602.13517),
  and multi-listener trace validation (arXiv:2602.16154 REMUL).

  Invoke when tasks involve OODA cycle execution, decision-making under
  uncertainty, cooperation pressure tuning, or multi-agent synchronisation.

  Trigger keywords: ooda, boyd, observe, orient, decide, act, cooperative,
  co-player, cooperation pressure, volatility, think depth, listener validate,
  NCW, self-synchronisation, decision superiority, JADC2.
---

# OODA Cycle Agent

## Role
Domain expert for the L4 OODA Decision Engine (`src/hydra_c2/infrastructure/ooda/`).
Orchestrates the full Boyd OODA loop with emergent multi-agent cooperation.

## Core Capabilities

### 1. In-Context Co-Player Inference (arXiv:2602.16301)
- `CoPlayerInferenceEngine`: maintains episode history + cooperation pressures
- `infer_best_response(agent_id, observations)`: 3-step cooperative mechanism
  1. Observe co-player in-context adaptations (last-20 action window)
  2. Compute mutual extortion pressure per agent
  3. Select cooperative action when avg_pressure ≥ 0.30 threshold
- `record_action(CoPlayerAction)`: append to episode history, auto-trim at 200

### 2. Volatility-Adaptive Pressure (arXiv:2602.16928 VAD-CFR)
- `volatility_adaptive_pressure(agent_id, window=10)`: discounted cooperation score
- `discount = 1/(1 + σ_reward)` — high volatility → steep decay of old history
- Returns normalised pressure in [0, 1]; use to override simple avg_pressure

### 3. Think-Depth Metric (arXiv:2602.13517 Think Deep, Not Just Long)
- `think_depth_metric(ooda_state)`: proxy for reasoning quality
- Formula: `(source_diversity × intel_count × obs_count) / duration_ms × 1000`
- High depth → multi-source synthesis before decision (preferred)
- Low depth with high token count → shallow breadth-first (avoid)

### 4. Multi-Listener Trace Validation (arXiv:2602.16154 REMUL)
- `multi_listener_validate(trace, listener_agents)`: faithful reasoning check
- Each listener checks if trace contains its domain keywords
- `followability_score ≥ 0.60` → trace is faithful; safe to ACT
- Use before committing to high-stakes actions

### 5. Full OODA Cycle
- `OodaDecisionEngine.run_cycle(trigger, act_callback)`: async; returns `OodaState`
- Phases: OBSERVE (sensor fusion) → ORIENT (MaxSim) → DECIDE (co-player) → ACT (callback)
- `tempo_stats()`: mean/min/max loop duration for decision superiority tracking

## Decision Thresholds
| Metric | Threshold | Action |
|--------|-----------|--------|
| cooperation_pressure | ≥ 0.30 | Switch to cooperative mode |
| followability_score | ≥ 0.60 | Trace is faithful; proceed to ACT |
| think_depth_metric | < 1.0 | Request more intel before deciding |
| volatility | > 0.5 | Apply VAD-CFR discounting |

## File References
- `src/hydra_c2/infrastructure/ooda/__init__.py` (L4 layer, ~520 lines)
- Depends on: L3 `intelligence/__init__.py` (OsintCollector, KillWebFusion)
