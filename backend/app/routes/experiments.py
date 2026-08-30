import csv
import json
import os

from fastapi import APIRouter, HTTPException

from backend.app.schemas.experiments import ExperimentRunRequest
from experiments.configs import DEFAULT_SEVERITY_SEQUENCE, resources_for
from experiments.runner import RESULTS_DIR, build_comparison_table
from simulation.environment import ScenarioConfig
from simulation.metrics.metrics import summarize_rows
from simulation.simulation import run_mas, run_no_coordination

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

METRICS = ["completion_time", "avg_waiting_time", "duplicate_conflicts", "victims_rescued"]


@router.post("/run")
def run_experiment(req: ExperimentRunRequest) -> dict:
    """Runs a fresh, user-configured No-Coordination-vs-MAS comparison on
    demand. Every row comes from an executed simulation run -- nothing here
    is precomputed or hardcoded."""
    seeds = [req.base_seed + i for i in range(req.n_runs)]
    severity_sequence = DEFAULT_SEVERITY_SEQUENCE if req.victim_count == 6 else None
    rows = []
    for seed in seeds:
        cfg = ScenarioConfig(
            seed=seed, width=15, height=15, victim_count=req.victim_count, severity_sequence=severity_sequence,
            blockage_level=req.blockage_level, initial_resources=resources_for(req.victim_count),
            max_time=req.max_time,
        )
        nc = run_no_coordination(cfg, rescue_agent_count=req.rescue_agent_count, scenario_name="custom")
        mas = run_mas(cfg, rescue_agent_count=req.rescue_agent_count, scenario_name="custom")
        rows.append(nc.to_row())
        rows.append(mas.to_row())

    summary = summarize_rows(rows, group_keys=["policy"], value_keys=METRICS)
    comparison = build_comparison_table(rows)
    return {"config": req.model_dump(), "seeds": seeds, "raw_rows": rows, "summary": summary,
            "comparison": comparison}


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
