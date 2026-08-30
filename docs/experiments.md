# Experiments

Run with `python -m experiments.runner` from the project root (inside the
venv). This executes all 5 controlled scenarios below under both modes
and writes `results/*.csv`, `results/*.json`, and (via `experiments.charts`,
called at the end of the same command) `results/*.png`.

`completion_time` and `avg_waiting_time` are reported in simulated minutes
(one simulation timestep = one simulated minute -- see
[`docs/methodology.md`](methodology.md#simulation-time-unit)), not
real-world measured rescue times.

## The 5 controlled scenarios (`experiments/configs.SCENARIOS`)

Each scenario is a set of seeds; every seed is run once under No
Coordination and once under MAS, with identical initial conditions.

1. **high_overlap** (seeds 11, 17) -- both agents' best candidate is
   naturally the same critical victim.
2. **moderate_overlap** (seeds 2, 5) -- agents start on different victims
   but their candidate sets overlap as priorities shift over time.
3. **more_victims_than_agents** (seeds 1, 2) -- 10 victims, 2 rescue
   agents, randomly distributed severities.
4. **low_conflict** (seeds 25, 30) -- a layout where the two agents'
   preferences rarely collide, so coordination has little to fix.
5. **blocked_route** (seeds 1, 9) -- the overlap-prone layout, plus roads
   that block and reopen mid-run, to exercise BFS replanning.

10 (scenario, seed) combinations x 2 modes = **20 total runs** per full
`experiments.runner` invocation (under a second on a laptop).

## Default demo scenario

`experiments/configs.DEFAULT_SEED = 11`, 6 victims (2 critical, 2 high, 2
moderate via `DEFAULT_SEVERITY_SEQUENCE`), 15x15 grid, no blockage. This
seed was picked (from a search across many candidate seeds) because both
rescue agents' best candidate is naturally the same critical victim at
t=0 -- not hardcoded, but chosen because it makes the coordination story
immediately visible. This is the scenario the Live Simulation view loads
by default.

## Files produced

```
results/
  raw_runs.csv     every individual run: scenario, seed, policy, completion_time,
                    victims_total, victims_rescued, avg_waiting_time, duplicate_conflicts
  summary.csv/.json grouped mean/median/stdev/min/max, per (scenario, policy)
  comparison.csv    the 3-metric No-Coordination-vs-MAS table, averaged across every
                    scenario/seed, with sign-adjusted % improvement
  run_meta.json     which scenarios/seeds were run, total run count, wall-clock time
  chart_1_completion_time.png
  chart_2_avg_waiting_time.png
  chart_3_conflicts.png
```

Nothing is cherry-picked: `comparison.csv` is the mean across all 20 runs,
not a single favorable run.
