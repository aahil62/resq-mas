# RESQ-MAS Architecture

## The core idea

Two rescue agents operate in the same disaster area. Several victims are
attractive targets for **both** agents (similar priority, similar
distance). **Without coordination**, both agents can independently pick
the same victim, wasting effort. **With coordination**, the agents
exchange their intended targets before committing, detect the duplicate,
resolve it, and divide the work -- rescuing different victims in parallel.
That is the entire subject of this project.

## System overview

```
Python simulation engine (simulation/)
        |
FastAPI backend (backend/)
        |
React frontend (frontend/)
```

All simulation logic lives in `simulation/`. The backend
(`backend/app/sim_session.py`) only serializes engine state to JSON; the
frontend only polls and renders.

## Directory map

```
simulation/
  environment.py        grid, victims, resources, blockage schedule
  agents/
    base.py              Agent ABC: observe -> update_state -> communicate -> decide -> act
    medical.py            MedicalTriageAgent (priority)
    logistics.py           LogisticsAgent (resource pool owner)
    rescue.py              RescueAgent (used for both Rescue A and Rescue B)
  coordination/
    messages.py            Event / EventType
    shared_state.py         the blackboard every agent reads/writes
    task_allocation.py      utility scoring + deterministic conflict resolution
  search/bfs.py             BFS route search
  metrics/metrics.py        shared RunResult schema + statistics
  simulation.py             the orchestration loop (one `Simulation` class, both modes)

experiments/                scenario configs, the 5 controlled scenarios, CSV/chart output
backend/                    FastAPI app wrapping the engine
frontend/                   React (Vite) dashboard
tests/                      pytest suite
results/                    generated CSV/JSON/PNG (not hand-edited)
```

## Only 4 agents

Exactly: **Medical Agent**, **Logistics Agent**, **Rescue Agent A**,
**Rescue Agent B**. Rescue A and B are both instances of the same
`RescueAgent` class, run independently. There is no fifth agent and no
sensor/perception agent -- every victim is known to both simulation modes
from t=0 (`MedicalTriageAgent` registers all of them at setup). This
project is about task-allocation coordination between two agents, not
about information latency.

## Two modes, one class

`simulation/simulation.py` has exactly one orchestrator, `Simulation`,
parametrized by `coordinate: bool`:

- **`coordinate=False` (No Coordination)**: each rescue agent evaluates
  candidates and commits to its best one immediately, without knowing what
  the other agent is about to choose. If both agents' best candidate is
  the same victim, both commit to it.
- **`coordinate=True` (MAS)**: each rescue agent only *proposes* a
  candidate (`TASK_PROPOSED`). The orchestrator collects both proposals
  for the tick and resolves conflicts (`coordination/task_allocation.
  resolve_conflicts`, a pure deterministic function -- not a hidden
  "super agent") **before** either agent commits. The losing agent stays
  idle that tick and proposes its next-best candidate on the next one.

Everything else -- the environment, BFS routing, resource requests,
movement, pickup, delivery, replanning on a blocked route -- is identical
code for both modes (see `RescueAgent.receive_assignment` /
`RescueAgent.act`), which is what makes the comparison fair: the *only*
behavioural difference is whether proposals are exchanged and resolved
before committing.

## Agent responsibilities

| Agent | Domain | Publishes |
|---|---|---|
| Medical | reads the environment's victim list (its own legitimate domain) once at setup, then republishes as waiting time accrues | `VICTIM_DETECTED` (registration), `PRIORITY_UPDATED` |
| Logistics | owns `ResourcePool` (its own resource) | `RESOURCE_ALLOCATED` / `RESOURCE_DENIED` |
| Rescue A/B | reads only `SharedState` + a static, pre-disaster `WorldMap` (the city layout) | `TARGET_SELECTED` (No Coordination) or `TASK_PROPOSED`/`TASK_ASSIGNED` (MAS), `RESOURCE_REQUEST`, `ROUTE_INVALIDATED`/`ROUTE_REPLANNED`, `VICTIM_RESCUED` |

## Coordination mechanism

```
utility = priority - distance_weight * travel_distance
```

(`coordination/task_allocation.compute_utility`, `distance_weight=0.1` by
default -- small, so severity actually influences target choice instead
of being swamped by distance). In MAS mode, when two proposals target the
same victim, `resolve_conflicts()` picks the higher-utility one (ties
broken by shorter distance, then agent id) -- deterministic and fully
reproducible, and something either agent could compute locally from the
public proposals; it is not a centralized decision-maker with private
state.

The duplicate-target situation is also detected generically, in both
modes, by `Simulation._check_duplicate_targets()`: once per tick it checks
whether two rescue agents are simultaneously, genuinely committed
(`status != "idle"`) to the same victim, and logs `DUPLICATE_DETECTED` the
first time that happens for a given victim. This is the source of the
`duplicate_conflicts` metric -- under MAS it should be at or near zero,
because `resolve_conflicts()` already prevented the situation before
either agent committed.

## Resource protocol

Rescue agents never touch the resource pool directly -- they publish
`RESOURCE_REQUEST`; only `LogisticsAgent` calls `ResourcePool.request()`.
The pool refuses a second request for a victim that already has a kit
reserved (one victim only ever needs one kit, regardless of how many
agents are independently heading there) and can never go negative. If a
request stays denied past `RESOURCE_WAIT_TIMEOUT` ticks, or a rescue agent
arrives to find its target already rescued by the other agent, it
abandons the target and becomes available for other work rather than
freezing -- the same rule applies in both modes.

## BFS vs. coordination

- **BFS** (`simulation/search/bfs.py`) answers *"how does a rescue agent
  reach a destination?"* -- shortest-path search on a 4-connected grid
  with uniform step cost. Re-run whenever a route is invalidated by a
  newly-known blockage (`ROUTE_INVALIDATED` -> `ROUTE_REPLANNED`).
- **Coordination** (`simulation/coordination/task_allocation.py`) answers
  *"which rescue agent should go, given what the other agent is doing?"*

BFS is the only search algorithm in the project by design -- the
intellectual content is the coordination mechanism, not the pathfinding.

## Simulation loop

Each tick of `Simulation.tick()`: apply scheduled blockage events (known
to both modes immediately) -> Medical registers/retriages -> Logistics
resolves last tick's resource requests -> rescue agents evaluate
candidates and propose/select -> (MAS only) conflicts resolved -> targets
committed and BFS routes planned -> routes re-validated/replanned if
blocked -> actions executed (movement, resource requests, pickup,
delivery) -> duplicate-target check -> victim waiting times updated ->
repeat until every victim is rescued, resources are exhausted with every
unit idle (a detectable dead end), or `max_time` is reached.
