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

- **Home** — the thesis ("three rescue teams that talk beat eight that
  don't"), a live side-by-side replay of the same disaster under "No talking"
  and "Negotiate" (115 vs 60 simulated minutes), the key findings, the three
  agent roles, the six strategies, and one-click scenarios.
- **Simulator** — pick a situation and one of the six strategies (plain names
  with the paper's codes: IND, CLM, PR-1, PR-k, HUN, CBBA), then play, step or
  skip to the end. "More settings" adds casualties arriving over time, lost
  radio messages or outages, blocked roads, up to 8 teams and bigger cities.
  A plain-language radio log explains every decision, and "Compare all six"
  runs every strategy on the same disaster.
- **Results** — the paper's 43,350-run study (`results/study/`): headline
  numbers, the two-team table, interactive charts (hover for values and 95%
  CIs), and "Run your own experiment" for fresh paired runs on the server.
- **How it works** — the agent diagram, one simulated minute step by step,
  the six strategies with their names in the paper, and the model's rules.

Light and dark themes follow the system setting (toggle in the header).
Fonts are bundled, so the site works offline. The paper PDF is served at
`http://127.0.0.1:8000/paper/main.pdf`.

## Notes on reproducibility

- Every scenario is generated deterministically from `(seed, grid size,
  victim count, severities, blockage level, resources)` -- see
  `simulation/environment.generate_scenario`. Same seed -> same world.
- No Coordination and MAS are always run against a world built from the
  *same* `ScenarioConfig`, so the comparison is fair.
- The default demo seed (11) and the 5 controlled-scenario seeds are fixed
  in `experiments/configs.py`.

## Research paper and large-scale study

`paper/main.tex` (compiled: `paper/main.pdf`) is an IEEE conference paper
built on this codebase: *How Much Talk Does a Rescue Team Need? Decomposing
the Value of Communication in Decentralized Multi-Agent Disaster Response.*

The engine now supports five allocation protocols (`Simulation(policy=...)`):
`independent` (the original No Coordination), `claim` (broadcast claims only),
`mas` (the original one-round propose/resolve), `mas_iterative` (losers
re-propose within the tick), `hungarian` (centralized optimal matching,
reference only), and `cbba` (consensus-based bundle algorithm), plus any
number of rescue agents, victims arriving over time
(`ScenarioConfig(arrival_window=...)`), and independent or bursty
Gilbert-Elliott message loss (`comm_loss=p`, `burst_length=L`). The original
`results/` are unchanged by these extensions.

```bash
pip install -r requirements.txt       # adds scipy
python -m experiments.study           # 43,350 paired runs -> results/study/ (~8 min, 4 cores)
python -m experiments.paper_figures   # figures + LaTeX tables -> paper/figures, paper/tables
cd paper && pdflatex main.tex && pdflatex main.tex
```
