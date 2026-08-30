# Methodology

## Problem

Multiple autonomous rescue agents may waste effort by independently
selecting the same victim.

## Solution

Agents communicate their target choices and coordinate task allocation
before committing.

## Fairness: identical worlds

No Coordination and MAS are always run against an `Environment` built from
the same `ScenarioConfig` (same seed, grid, victim positions/severities,
starting positions, blockage schedule, resource pool). Every victim is
known to both modes from t=0. The only thing that differs is the
*policy*: whether the two rescue agents exchange proposals and resolve
conflicts before committing to a target, or each commits independently.
Any measured difference is attributable to that, and nothing else.

## Victim priority

```
priority = severity_score + waiting_weight * waiting_time
```

`severity_score`: critical=4, high=3, moderate=2, low=1 (exactly the
scale in the assessment brief). `waiting_weight=0.1` -- small, so severity
dominates but a long-waiting lower-severity victim can still eventually
out-rank a critical one. Deterministic, transparent, one line -- not a
learned model.

## Task-allocation utility

```
utility = priority - distance_weight * travel_distance
```

`distance_weight=0.1` (`coordination/task_allocation.UtilityWeights`).
`travel_distance` is the BFS path length on the currently known grid. This
weight is deliberately small: priority ranges 1-4ish and distances can be
10-20+ cells on a 15x15 grid, so a larger weight would make distance
swamp severity entirely and priority would never actually influence which
victim gets picked.

## Conflict resolution (MAS only)

A pure function of the tick's published proposals
(`coordination/task_allocation.resolve_conflicts`): highest utility wins;
ties broken by shorter travel distance, then by agent id -- fully
deterministic and reproducible.

## Simulation time unit

**Modeling assumption: one simulation timestep represents one minute of
simulated disaster-response operation.** So `t=1` means 1 simulated
minute, `t=60` means 60 simulated minutes, `t=115` means 115 simulated
minutes. This is a modeling assumption, not a measurement -- the numbers
below are simulated minutes produced by the model, not real-world
measured rescue times. The assumption only affects how time is *labeled*
(the CLI, event log, UI, result tables, and charts all say "minutes");
it does not change any simulation logic, agent behavior, coordination
mechanism, BFS, or experimental setup. Internally the engine still steps
through integer ticks (`Environment.time`, `ScheduledEvent.timestep`) --
"minute" is simply what one tick is defined to mean for reporting
purposes.

## Metrics

Exactly 3, computed per run (`simulation/metrics/metrics.RunResult`) and
aggregated across repetitions:

- **completion_time** (minutes) -- simulated minute the run ended.
- **avg_waiting_time** (minutes) -- mean simulated waiting time of rescued
  victims.
- **duplicate_conflicts** -- how many times two rescue agents ended up
  genuinely, simultaneously committed to the same victim. This is the
  metric that most directly demonstrates the point of the project.

(`victims_rescued` is also recorded, mainly as a sanity check that both
modes complete the scenario equally well.)

## Percentage improvement

```
improvement = ((no_coordination - mas) / no_coordination) * 100
```

sign-adjusted per metric (`metrics.LOWER_IS_BETTER`) so a positive number
always means "MAS is better on this metric." No metric is labeled an
"improvement" in the wrong direction.

## Honesty about results

Every number this project reports comes from an executed run recorded in
`results/*.csv`/`*.json`. The default demo scenario/seed was *chosen*
(from a search across many seeds, see `experiments/configs.DEFAULT_SEED`)
because it naturally produces target overlap -- not because the code was
tuned to fake a conflict. `victims_rescued` is reported identically for
both modes in the primary comparison, because both modes do in fact
rescue the same victims eventually; the difference the project measures is
in *how much wasted effort* it takes to get there.
