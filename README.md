# RESQ-MAS — Multi-Agent Task Coordination for Disaster Rescue

A multi-agent disaster-rescue simulator built around one question: **how
much do rescue agents need to communicate before committing to a target?**

The starting point is simple — **two independent rescue agents can waste
effort by picking the same victim; agents that communicate their intended
targets before committing can detect that, resolve it, and divide the work
instead** — and the codebase grew into a testbed for six coordination
protocols, evaluated across 43,350 simulated disasters, with an interactive
web dashboard (`backend/` + `frontend/`) built on the same engine.

## The six coordination protocols

| Code | Name | What agents share before committing |
|---|---|---|
| `independent` | No Coordination | Nothing — each agent commits to its own best target immediately |
| `claim` | Claim Broadcasting | An agent announces its choice after committing; others avoid claimed victims |
| `mas` | One-round Propose–Resolve | Agents propose first; conflicts resolve by utility before anyone commits |
| `mas_iterative` | Iterative Propose–Resolve | Like `mas`, but losers re-propose immediately within the same tick |
| `hungarian` | Centralized Hungarian | A coordinator computes the optimal assignment from every agent's utility |
| `cbba` | Consensus-Based Bundle Algorithm | Agents bid on bundles of future targets and reconcile via consensus rounds |

All six run on one shared engine (`simulation/simulation.py`,
`Simulation(policy=...)`), share the same environment, agents, BFS routing
and metrics — so any measured difference comes from the coordination
protocol alone. The engine also supports victims arriving over time
(`ScenarioConfig(arrival_window=...)`), independent or bursty
Gilbert–Elliott message loss (`comm_loss=p`, `burst_length=L`), road
blockages, and any number of rescue agents.

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
simulation/     the engine: environment, N agents, 6 coordination protocols, BFS, metrics
experiments/    scenario configs + two run modes:
                  runner.py   the original 5 controlled scenarios (20 runs) -> results/
                  study.py    the full paired study (43,350 runs) -> results/study/
results/        generated CSV/JSON/PNG from experiments.runner (checked in from the last full run)
                results/study/  raw per-experiment CSVs + stats.json from experiments.study
backend/        FastAPI app: live simulation sessions, custom experiment runs, study API, replay
frontend/       React (Vite) dashboard -- Home, Simulator, Results, How it works
docs/           architecture / methodology / experiments write-ups for the original two-mode baseline
tests/          pytest suite (engine, protocols, BFS, API)
```

## Requirements

- Python 3.11+ (developed on 3.14)
- Node.js 18+ (developed on 24) with npm

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # simulation + experiments + tests + scipy
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

## Run the tests

```bash
source .venv/bin/activate
python -m pytest -q
```

96 tests covering BFS, environment/victims/resources, all six coordination
protocols (independent selection and duplication, claim broadcasting,
one-round and iterative propose/resolve, the Hungarian optimum, CBBA),
victims arriving over time, independent and bursty message loss, victim
rescue, waiting time, comparison metrics, and the FastAPI backend.

## Run a single simulation from the CLI

```bash
source .venv/bin/activate
python -m simulation.simulation --mode no_coordination --scenario medium --seed 11
python -m simulation.simulation --mode mas --scenario medium --seed 11
```

`--scenario` is `small`/`medium`/`large`; override with `--victim-count`,
`--blockage-level`, `--rescue-agents`, `--max-time`. The CLI only exposes
the original two modes; use `simulation.simulation.run_policy(...)` (or
`experiments.study`) to run any of the other four protocols, arrivals, or
message loss from Python.

## Reproduce the original 5-scenario baseline

```bash
source .venv/bin/activate
python -m experiments.runner   # runs the 5 controlled scenarios (20 runs) and generates charts
```

Overwrites `results/` from a fresh, real execution — seeds are fixed
(`experiments/configs.py`), so the numbers should match what's checked in.
This is the original course benchmark, comparing only `independent` vs
`mas`; it's kept as the "Original course benchmark" panel on the Results
page and superseded by the full study below for anything else.

## Reproduce the full paired study

```bash
source .venv/bin/activate
python -m experiments.study   # 43,350 paired runs -> results/study/ (~8 min, 4 cores)
```

Six experiments (E1–E6): the two-agent baseline on random worlds, scaling
from 1–8 agents, independent message loss, road blockages, victims
arriving over time, and bursty message loss — each protocol run on the
same randomly generated worlds for a paired comparison, with
Wilcoxon/Holm-corrected significance tests and bootstrap confidence
intervals. The original `results/` (from `experiments.runner`) is
untouched by this — the two run modes write to separate directories.

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

- **Home** — the thesis ("three rescue teams that talk beat eight that
  don't"), a live side-by-side replay of the same disaster under "No talking"
  and "Negotiate" (115 vs 60 simulated minutes), the key findings, the three
  agent roles, the six strategies, and one-click scenarios.
- **Simulator** — pick a situation and one of the six strategies (plain names
  with short codes: IND, CLM, PR-1, PR-k, HUN, CBBA), then play, step or
  skip to the end. "More settings" adds casualties arriving over time, lost
  radio messages or outages, blocked roads, up to 8 teams and bigger cities.
  A plain-language radio log explains every decision, and "Compare all six"
  runs every strategy on the same disaster.
- **Results** — the 43,350-run study (`results/study/`): headline
  numbers, the two-team table, interactive charts (hover for values and 95%
  CIs), and "Run your own experiment" for fresh paired runs on the server.
- **How it works** — the agent diagram, one simulated minute step by step,
  the six strategies with their formal names, and the model's rules.

Light and dark themes follow the system setting (toggle in the header).
Fonts are bundled, so the site works offline.

## Notes on reproducibility

- Every scenario is generated deterministically from `(seed, grid size,
  victim count, severities, blockage level, resources)` -- see
  `simulation/environment.generate_scenario`. Same seed -> same world.
- Every protocol in a given experiment is always run against a world built
  from the *same* `ScenarioConfig`, so comparisons are paired and fair.
- The default demo seed (11) and the 5 controlled-scenario seeds are fixed
  in `experiments/configs.py`; the study's seeds are fixed in
  `experiments/study.py`.

## Further reading

- [`docs/architecture.md`](docs/architecture.md), [`docs/methodology.md`](docs/methodology.md),
  [`docs/experiments.md`](docs/experiments.md) — how the original two-mode
  baseline (`independent` vs `mas`) is built, its formulas, and exactly what
  `experiments.runner` runs. The six-protocol extension, arrivals, and
  message loss are covered by `experiments/study.py` and the web dashboard's
  Results and How it works pages instead.
