"""Large-scale study behind the RESQ-MAS paper (paper/main.tex).

Four experiments, each on freshly generated random worlds (seeds 1000+,
disjoint from the curated demo seeds in experiments/configs.py), each world
run once per task-allocation protocol so every comparison is paired:

  E1 generalization -- 2 agents / 6 victims (the original setting),
                        1,000 random worlds, with and without road blockages
  E2 scaling        -- team size N x victim count M on a 20x20 grid
  E3 comm_loss      -- broadcast-loss probability p for the message-based
                        protocols (N=4, M=20)
  E4 blockage       -- fraction of road cells that block mid-run (N=4, M=20)
  E5 arrivals       -- victims appear over a window instead of at t=0 (N=4, M=20)
  E6 bursty         -- Gilbert-Elliott (bursty) loss: mean loss x burst length

Writes one CSV of raw runs per experiment to results/study/ plus
results/study/stats.json (paired tests, CIs). Run:

    python -m experiments.study            # full study (~10 min on 4 cores)
    python -m experiments.study --quick    # 20 seeds per cell, for a smoke test
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import time
from multiprocessing import Pool

from simulation.environment import ScenarioConfig
from simulation.simulation import POLICIES, run_policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "results", "study")
SEED_BASE = 1000
MAX_TIME = 3000  # safety cap only: every run in a valid world ends when all victims are rescued
BLOCKAGE_HORIZON = 300  # blockages start within the first 120 min and last 10-75 min (repo default)


def _config(seed: int, victims: int, width: int, blockage: float, arrival: int = 0) -> ScenarioConfig:
    return ScenarioConfig(seed=seed, width=width, height=width, victim_count=victims,
                          severity_sequence=None, blockage_level=blockage,
                          initial_resources=victims, max_time=MAX_TIME, blockage_horizon=BLOCKAGE_HORIZON,
                          arrival_window=arrival)


def valid_world(seed: int, victims: int, width: int) -> bool:
    """Random building placement can wall a victim (or the hospital) off
    from both depots. No protocol can rescue such a victim, so these worlds
    measure the simulator's generator rather than coordination; they are
    excluded (and counted) instead of letting runs idle to the time cap."""
    from simulation.environment import Environment, CellType
    from simulation.search.bfs import GridSpec, bfs_distances

    env = Environment(_config(seed, victims, width, 0.0))
    blocked = {(r, c) for r in range(width) for c in range(width) if env.grid[r][c] == CellType.BUILDING}
    grid = GridSpec(width=width, height=width, blocked=blocked)
    goals = [v.position for v in env.victims.values()] + [env.hospital]
    return all(all(g in dist for g in goals) for dist in (bfs_distances(grid, d) for d in env.depots))


def seeds_for(count: int, victims: int, width: int) -> list[int]:
    """The first `count` valid worlds from SEED_BASE upward (deterministic)."""
    out, s = [], SEED_BASE
    while len(out) < count:
        if valid_world(s, victims, width):
            out.append(s)
        s += 1
    return out


def _job(args: tuple) -> dict:
    exp, seed, policy, n, m, width, blockage, loss = args[:8]
    arrival, burst = (args[8], args[9]) if len(args) > 8 else (0, None)
    res = run_policy(_config(seed, m, width, blockage, arrival), policy, rescue_agent_count=n,
                     comm_loss=loss, burst_length=burst)
    row = res.to_extended_row()
    row.update({"experiment": exp, "victims": m, "grid": width, "blockage": blockage, "comm_loss": loss,
                "arrival_window": arrival, "burst_length": burst if burst is not None else 0})
    return row


def build_jobs(seeds: int, e1_seeds: int = 1000) -> list[tuple]:
    jobs = []
    for bl in (0.0, 0.1):
        for s in seeds_for(e1_seeds, 6, 15):
            for p in POLICIES:
                jobs.append(("E1", s, p, 2, 6, 15, bl, 0.0))
    for n in (1, 2, 3, 4, 6, 8):
        for m in (10, 20, 30):
            for s in seeds_for(seeds, m, 20):
                for p in POLICIES:
                    if n == 1 and p != "independent":
                        continue  # a single agent has nobody to coordinate with
                    jobs.append(("E2", s, p, n, m, 20, 0.0, 0.0))
    for loss in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0):
        for s in seeds_for(seeds, 20, 20):
            for p in ("claim", "mas", "mas_iterative", "cbba"):
                jobs.append(("E3", s, p, 4, 20, 20, 0.0, loss))
    for bl in (0.0, 0.1, 0.2, 0.3):
        for s in seeds_for(seeds, 20, 20):
            for p in POLICIES:
                jobs.append(("E4", s, p, 4, 20, 20, bl, 0.0))
    for window in (0, 100, 200, 400):
        for s in seeds_for(seeds, 20, 20):
            for p in POLICIES:
                jobs.append(("E5", s, p, 4, 20, 20, 0.0, 0.0, window, None))
    for loss in (0.1, 0.3, 0.5):
        for burst in (1, 5, 20):
            for s in seeds_for(seeds, 20, 20):
                for p in ("claim", "mas", "mas_iterative", "cbba"):
                    jobs.append(("E6", s, p, 4, 20, 20, 0.0, loss, 0, burst))
    return jobs


# -- statistics ---------------------------------------------------------------
def bootstrap_ci(diffs: list[float], reps: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(statistics.fmean(rng.choices(diffs, k=n)) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def paired_test(a: list[float], b: list[float]) -> dict:
    """a = baseline, b = treatment, paired by seed. Positive `mean_diff`
    means b is lower (better, for time metrics)."""
    from scipy.stats import wilcoxon

    diffs = [x - y for x, y in zip(a, b)]
    nz = [d for d in diffs if d != 0]
    if nz:
        stat = wilcoxon(a, b, zero_method="wilcox")
        p = float(stat.pvalue)
        pos = sum(1 for d in nz if d > 0)
        # matched-pairs rank-biserial correlation
        ranks = _abs_ranks(nz)
        r_plus = sum(r for r, d in zip(ranks, nz) if d > 0)
        r_minus = sum(r for r, d in zip(ranks, nz) if d < 0)
        rbc = (r_plus - r_minus) / (r_plus + r_minus)
    else:
        p, pos, rbc = 1.0, 0, 0.0
    lo, hi = bootstrap_ci(diffs)
    base = statistics.fmean(a)
    return {
        "n": len(diffs), "baseline_mean": base, "treatment_mean": statistics.fmean(b),
        "mean_diff": statistics.fmean(diffs), "ci95": [lo, hi],
        "pct_improvement": 100 * statistics.fmean(diffs) / base if base else 0.0,
        "wins": pos, "ties": len(diffs) - len(nz), "losses": len(nz) - pos,
        "p_value": p, "rank_biserial": rbc,
    }


def _abs_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: abs(values[i]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(values[order[j + 1]]) == abs(values[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def _col(rows: list[dict], key: str, **where) -> dict[int, float]:
    return {r["seed"]: float(r[key]) for r in rows if all(r[k] == v for k, v in where.items())}


def _paired(rows, key, base_where, treat_where):
    a, b = _col(rows, key, **base_where), _col(rows, key, **treat_where)
    seeds = sorted(set(a) & set(b))
    return paired_test([a[s] for s in seeds], [b[s] for s in seeds])


def compute_stats(rows: list[dict]) -> dict:
    out: dict = {"E1": {}, "E2": {}, "E4": {}, "E5": {}, "E6": {}}
    e1 = [r for r in rows if r["experiment"] == "E1"]
    comparisons = [("no_coordination", "claim"), ("claim", "mas"), ("no_coordination", "mas"),
                   ("mas", "mas_iterative"), ("mas", "hungarian"), ("mas_iterative", "hungarian")]
    pvals = {}
    for bl in (0.0, 0.1):
        for metric in ("completion_time", "avg_waiting_time", "weighted_wait"):
            for base, treat in comparisons:
                key = f"bl={bl}|{metric}|{base}->{treat}"
                res = _paired(e1, metric, {"policy": base, "blockage": bl}, {"policy": treat, "blockage": bl})
                out["E1"][key] = res
                pvals[key] = res["p_value"]
    for k, p in holm(pvals).items():
        out["E1"][k]["p_holm"] = p

    e2 = [r for r in rows if r["experiment"] == "E2"]
    pvals = {}
    for n in (2, 3, 4, 6, 8):
        for m in (10, 20, 30):
            for base, treat in (("no_coordination", "mas"), ("mas", "hungarian"), ("mas_iterative", "hungarian"),
                                ("cbba", "hungarian")):
                key = f"N={n}|M={m}|completion_time|{base}->{treat}"
                res = _paired(e2, "completion_time", {"policy": base, "rescue_agents": n, "victims": m},
                              {"policy": treat, "rescue_agents": n, "victims": m})
                out["E2"][key] = res
                pvals[key] = res["p_value"]
    for k, p in holm(pvals).items():
        out["E2"][k]["p_holm"] = p

    e5 = [r for r in rows if r["experiment"] == "E5"]
    pvals = {}
    for w in (0, 100, 200, 400):
        for metric in ("avg_waiting_time", "weighted_wait"):
            for base, treat in (("no_coordination", "claim"), ("claim", "mas"), ("no_coordination", "mas"),
                                ("mas", "mas_iterative"), ("mas_iterative", "cbba"), ("mas_iterative", "hungarian")):
                key = f"W={w}|{metric}|{base}->{treat}"
                res = _paired(e5, metric, {"policy": base, "arrival_window": w}, {"policy": treat, "arrival_window": w})
                out["E5"][key] = res
                pvals[key] = res["p_value"]
    for k, p in holm(pvals).items():
        out["E5"][k]["p_holm"] = p

    e6 = [r for r in rows if r["experiment"] == "E6"]
    pvals = {}
    for loss in (0.1, 0.3, 0.5):
        for burst in (1, 5, 20):
            for base, treat in (("mas", "mas_iterative"), ("mas_iterative", "cbba"), ("claim", "mas")):
                key = f"p={loss}|L={burst}|completion_time|{base}->{treat}"
                res = _paired(e6, "completion_time", {"policy": base, "comm_loss": loss, "burst_length": burst},
                              {"policy": treat, "comm_loss": loss, "burst_length": burst})
                out["E6"][key] = res
                pvals[key] = res["p_value"]
    for k, p in holm(pvals).items():
        out["E6"][k]["p_holm"] = p
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=150, help="random worlds per E2-E4 cell (E1 uses 1,000)")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    seeds = 20 if args.quick else args.seeds

    os.makedirs(OUT_DIR, exist_ok=True)
    jobs = build_jobs(seeds, e1_seeds=seeds if args.quick else 1000)
    t0 = time.time()
    with Pool(args.workers) as pool:
        rows = pool.map(_job, jobs, chunksize=16)
    elapsed = time.time() - t0

    for exp in ("E1", "E2", "E3", "E4", "E5", "E6"):
        sub = [r for r in rows if r["experiment"] == exp]
        with open(os.path.join(OUT_DIR, f"{exp}_runs.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sub[0].keys()))
            w.writeheader()
            w.writerows(sub)

    stats = compute_stats(rows)
    excluded = {f"M={m},grid={w}": (max(seeds_for(n, m, w)) - SEED_BASE + 1) - n
                for m, w, n in ((6, 15, seeds if args.quick else 1000), (10, 20, seeds), (20, 20, seeds),
                                (30, 20, seeds))}
    stats["meta"] = {"excluded_unreachable_worlds": excluded, "runs": len(rows), "elapsed_seconds": elapsed, "seeds_per_cell": seeds,
                     "seed_base": SEED_BASE, "max_time": MAX_TIME,
                     "blockage_horizon": BLOCKAGE_HORIZON}
    with open(os.path.join(OUT_DIR, "stats.json"), "w") as f:
        json.dump(stats, f, indent=1, default=lambda x: None if isinstance(x, float) and math.isnan(x) else x)
    print(f"{len(rows)} runs in {elapsed:.1f}s -> {OUT_DIR}")


if __name__ == "__main__":
    main()
