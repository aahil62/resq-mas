# RESQ-MAS — Multi-Agent Task Coordination for Disaster Rescue

An AI-course project demonstrating one idea: **two independent rescue
agents can waste effort by picking the same victim; agents that
communicate their intended targets before committing can detect that,
resolve it, and divide the work instead.**

- **No Coordination**: two rescue agents each independently pick their
  best-scoring victim (priority + distance) and commit immediately. If
  both pick the same one, both go -- one arrives to find it already
  rescued.
- **MAS**: both agents propose a target first. If they proposed the same
  victim, a deterministic conflict-resolution rule picks a winner; the
  loser immediately re-evaluates and picks its next-best target instead.

See [`docs/architecture.md`](docs/architecture.md) for how the system is
built, [`docs/methodology.md`](docs/methodology.md) for the formulas, and
[`docs/experiments.md`](docs/experiments.md) for exactly what was run to
produce `results/`.

**Simulation assumption: one simulation timestep represents one minute of
simulated disaster-response operation.** `t=115` means 115 simulated
minutes. This is a modeling assumption used purely for reporting/labeling
(the CLI, event log, dashboard, result tables, and charts all display
"minutes"); it does not change any simulation logic, agent behavior,
coordination mechanism, BFS, or experimental setup, and these are not
real-world measured rescue times -- they are simulated minutes produced by
the model.

## Project structure

```
simulation/     the engine: environment, 4 agents, coordination, BFS, metrics
experiments/    the 5 controlled scenarios + CSV/chart generation
results/        generated CSV/JSON/PNG (checked in from the last full run)
backend/        FastAPI wrapper around the engine
frontend/       React (Vite) dashboard -- 3 views: Live Simulation, Comparison, Architecture
tests/          pytest suite
docs/           architecture / methodology / experiments write-ups
```

## Requirements

- Python 3.11+ (developed on 3.14)
- Node.js 18+ (developed on 24) with npm

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # simulation + experiments + tests
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

## Run the tests

```bash
source .venv/bin/activate
python -m pytest -q
```

50 tests covering BFS, environment/victims/resources, independent target
selection, duplicate target selection under No Coordination, conflict
detection/resolution/reassignment under MAS, victim rescue, waiting time,
and comparison metrics.

## Run a single simulation from the CLI

```bash
source .venv/bin/activate
python -m simulation.simulation --mode no_coordination --scenario medium --seed 11
python -m simulation.simulation --mode mas --scenario medium --seed 11
```

`--scenario` is `small`/`medium`/`large`; override with `--victim-count`,
`--blockage-level`, `--rescue-agents`, `--max-time`.

## Reproduce all experiments and results

```bash
source .venv/bin/activate
python -m experiments.runner   # runs all 5 controlled scenarios (20 runs) and generates charts
```

Overwrites `results/` from a fresh, real execution — seeds are fixed
(`experiments/configs.py`), so the numbers should match what's checked in.

## Run the web application

Two terminals, from the project root:

```bash
# terminal 1 — backend (port 8000)
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000

# terminal 2 — frontend (port 5173)
cd frontend
npm run dev
```

Open `http://localhost:5173`.

- **Live Simulation** — drives the actual Python engine tick-by-tick.
  Toggle between "NO COORDINATION" and "MULTI-AGENT", hit Run, and watch
  Rescue A and Rescue B either duplicate effort or divide the work. The
  event log shows exactly what the brief asks for: `TARGET_SELECTED` /
  `DUPLICATE_DETECTED` under No Coordination, `TASK_PROPOSED` /
  `TASK_CONFLICT` / `TASK_ASSIGNED` / `TASK_REASSIGNED` under MAS.
- **Comparison** — "Effect of Multi-Agent Coordination": the 3-metric
  table and 3 charts, read from `results/` (produced by
  `experiments.runner`, above).
- **Architecture** — the system diagram and the No-Coordination-vs-MAS /
  BFS-vs-coordination explanation.

## Notes on reproducibility

- Every scenario is generated deterministically from `(seed, grid size,
  victim count, severities, blockage level, resources)` -- see
  `simulation/environment.generate_scenario`. Same seed -> same world.
- No Coordination and MAS are always run against a world built from the
  *same* `ScenarioConfig`, so the comparison is fair.
- The default demo seed (11) and the 5 controlled-scenario seeds are fixed
  in `experiments/configs.py`.
