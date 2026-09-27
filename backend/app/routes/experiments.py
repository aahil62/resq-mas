import csv
import json
import math
import os
import statistics
from collections import defaultdict
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from backend.app.schemas.experiments import ExperimentRunRequest
from backend.app.sim_session import BLOCKAGE_HORIZON, ENGINE_POLICY
from experiments.configs import DEFAULT_SEVERITY_SEQUENCE, resources_for
from experiments.runner import RESULTS_DIR, build_comparison_table
from simulation.environment import ScenarioConfig
from simulation.metrics.metrics import summarize_rows
from simulation.simulation import run_policy

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

METRICS = ["completion_time", "avg_waiting_time", "duplicate_conflicts", "victims_rescued"]
EXTENDED = ["completion_time", "avg_waiting_time", "weighted_wait", "duplicate_conflicts", "wasted_ticks",
            "idle_ticks", "messages", "message_payload", "victims_rescued"]
STUDY_DIR = os.path.join(RESULTS_DIR, "study")
PROTOCOLS = ["no_coordination", "claim", "mas", "mas_iterative", "hungarian", "cbba"]


def _mean_ci(values: list[float]) -> dict:
    values = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    if not values:
        return {"mean": None, "ci": None, "n": 0}
    m = statistics.fmean(values)
    h = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return {"mean": m, "ci": h, "n": len(values)}


@router.post("/run")
def run_experiment(req: ExperimentRunRequest) -> dict:
    """Runs a fresh, user-configured comparison of any set of protocols on
    demand. Each seed builds one world that every selected protocol runs on
    (paired design). Every row comes from an executed simulation run --
    nothing here is precomputed or hardcoded."""
    seeds = [req.base_seed + i for i in range(req.n_runs)]
    severity_sequence = DEFAULT_SEVERITY_SEQUENCE if req.victim_count == 6 else None
    policies = list(dict.fromkeys(req.policies))
    rows = []
    for seed in seeds:
        cfg = ScenarioConfig(
            seed=seed, width=req.width, height=req.width, victim_count=req.victim_count,
            severity_sequence=severity_sequence, blockage_level=req.blockage_level,
            initial_resources=resources_for(req.victim_count), max_time=req.max_time,
            arrival_window=req.arrival_window, blockage_horizon=BLOCKAGE_HORIZON,
        )
        for policy in policies:
            res = run_policy(cfg, ENGINE_POLICY.get(policy, policy), rescue_agent_count=req.rescue_agent_count,
                             scenario_name="custom", comm_loss=req.comm_loss, burst_length=req.burst_length)
            row = res.to_extended_row()
            row["policy"] = policy  # keep the dashboard's name for the independent protocol
            rows.append(row)

    by_policy = defaultdict(list)
    for r in rows:
        by_policy[r["policy"]].append(r)
    per_policy = {p: {m: _mean_ci([float(r[m]) for r in by_policy[p]]) for m in EXTENDED} for p in policies}

    # Paired improvement of every protocol over the first selected one (the baseline).
    base = policies[0]
    base_t = {r["seed"]: r for r in by_policy[base]}
    paired = {}
    for p in policies[1:]:
        diffs = [base_t[r["seed"]]["completion_time"] - r["completion_time"] for r in by_policy[p]]
        wins = sum(d > 0 for d in diffs)
        paired[p] = {"mean_reduction": statistics.fmean(diffs), "wins": wins,
                     "ties": sum(d == 0 for d in diffs), "losses": len(diffs) - wins - sum(d == 0 for d in diffs)}

    summary = summarize_rows(rows, group_keys=["policy"], value_keys=METRICS)
    comparison = build_comparison_table(rows) if {"no_coordination", "mas"} <= set(policies) else []
    return {"config": req.model_dump(), "seeds": seeds, "policies": policies, "baseline": base,
            "per_policy": per_policy, "paired": paired, "raw_rows": rows, "summary": summary,
            "comparison": comparison}


def _load(exp: str) -> list[dict]:
    path = os.path.join(STUDY_DIR, f"{exp}_runs.csv")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No study results found. Run `python -m experiments.study` first.")
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            try:
                r[k] = float(v)
            except (TypeError, ValueError):
                pass
    return rows


def _agg(rows, keys, metrics):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys)].append(r)
    out = []
    for key, rs in sorted(g.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        entry = dict(zip(keys, key))
        for m in metrics:
            entry[m] = _mean_ci([r[m] for r in rs])
        out.append(entry)
    return out


@lru_cache(maxsize=1)
def _study_summary(mtime: float) -> dict:
    e1, e2, e3, e4, e5, e6 = (_load(x) for x in ("E1", "E2", "E3", "E4", "E5", "E6"))
    with open(os.path.join(STUDY_DIR, "stats.json")) as f:
        stats = json.load(f)
    e1_static = [r for r in e1 if r["blockage"] == 0.0]

    # Headline: smallest coordinated team that beats eight independent agents, per workload.
    t = defaultdict(dict)
    for r in e2:
        t[(r["victims"], r["rescue_agents"], r["policy"])][r["seed"]] = r["completion_time"]
    beats = []
    for m in (10.0, 20.0, 30.0):
        ind8 = t[(m, 8.0, "no_coordination")]
        for n in (2.0, 3.0, 4.0):
            mas = t[(m, n, "mas")]
            seeds = sorted(set(ind8) & set(mas))
            beats.append({"victims": m, "coordinated_agents": n,
                          "coordinated_T": statistics.fmean(mas[s] for s in seeds),
                          "independent8_T": statistics.fmean(ind8[s] for s in seeds),
                          "wins": sum(mas[s] < ind8[s] for s in seeds), "n": len(seeds)})

    return {
        "meta": stats.get("meta", {}),
        "protocols": PROTOCOLS,
        "e1": _agg(e1_static, ["policy"], ["completion_time", "avg_waiting_time", "weighted_wait", "critical_wait",
                                           "duplicate_conflicts", "wasted_ticks", "message_payload"]),
        "e1_tests": {k: v for k, v in stats.get("E1", {}).items() if k.startswith("bl=0.0|completion_time")},
        "e2": _agg(e2, ["victims", "rescue_agents", "policy"],
                   ["completion_time", "wasted_ticks", "idle_ticks", "message_payload"]),
        "e3": _agg(e3, ["comm_loss", "policy"], ["completion_time", "duplicate_conflicts"]),
        "e4": _agg(e4, ["blockage", "policy"], ["completion_time"]),
        "e5": _agg(e5, ["arrival_window", "policy"], ["avg_waiting_time", "weighted_wait", "duplicate_conflicts"]),
        "e6": _agg(e6, ["comm_loss", "burst_length", "policy"], ["completion_time", "duplicate_conflicts"]),
        "three_beats_eight": beats,
    }


@router.get("/study")
def study_summary() -> dict:
    """Aggregates the paper's paired study (results/study/*.csv, produced by
    `python -m experiments.study`): means and 95% CIs per experiment cell."""
    path = os.path.join(STUDY_DIR, "stats.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No study results found. Run `python -m experiments.study` first.")
    return _study_summary(os.path.getmtime(path))


@router.get("/precomputed/meta")
def precomputed_meta() -> dict:
    path = os.path.join(RESULTS_DIR, "run_meta.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No precomputed results found. Run `python -m experiments.runner` first.")
    with open(path) as f:
        return json.load(f)


_TABLE_FILES = {
    "comparison": "comparison.csv",
    "summary": "summary.csv",
    "raw_runs": "raw_runs.csv",
}


@router.get("/precomputed/{table}")
def precomputed_table(table: str) -> list[dict]:
    if table not in _TABLE_FILES:
        raise HTTPException(status_code=404, detail=f"Unknown table '{table}'. Valid: {list(_TABLE_FILES)}")
    path = os.path.join(RESULTS_DIR, _TABLE_FILES[table])
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No precomputed results found. Run `python -m experiments.runner` first.")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))
