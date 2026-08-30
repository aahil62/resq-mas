"""Runs the 5 controlled scenarios (experiments/configs.SCENARIOS) under
both No Coordination and MAS and writes /results/*.csv and /results/*.json.
Nothing here is precomputed or hardcoded -- every row comes from an
executed run of simulation.run_no_coordination() or simulation.run_mas().
"""

from __future__ import annotations

import csv
import json
import os
import time

from experiments.configs import SCENARIOS
from experiments.scenarios import named_scenario_configs
from simulation.metrics.metrics import percent_improvement, summarize_rows
from simulation.simulation import run_mas, run_no_coordination

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

METRICS = ["completion_time", "avg_waiting_time", "duplicate_conflicts", "victims_rescued"]


def run_all_scenarios() -> list[dict]:
    rows = []
    for name in SCENARIOS:
        for cfg in named_scenario_configs(name):
            nc = run_no_coordination(cfg, scenario_name=name)
            mas = run_mas(cfg, scenario_name=name)
            rows.append(nc.to_row())
            rows.append(mas.to_row())
    return rows


def _write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_comparison_table(rows: list[dict]) -> list[dict]:
    """The simple summary table from the assessment brief: No Coordination
    vs MAS, mean of each of the 3 core metrics, across every scenario/seed."""
    summary = summarize_rows(rows, group_keys=["policy"], value_keys=METRICS)
    by_policy = {s["policy"]: s for s in summary}
    if "no_coordination" not in by_policy or "mas" not in by_policy:
        return []
    table = []
    for metric in METRICS:
        nc = by_policy["no_coordination"][f"{metric}_mean"]
        mas = by_policy["mas"][f"{metric}_mean"]
        table.append({
            "metric": metric,
            "no_coordination_mean": nc,
            "mas_mean": mas,
            "improvement_pct": percent_improvement(nc, mas, metric),
        })
    return table


def run_all(results_dir: str = RESULTS_DIR) -> dict:
    os.makedirs(results_dir, exist_ok=True)
    t0 = time.time()

    rows = run_all_scenarios()
    _write_csv(os.path.join(results_dir, "raw_runs.csv"), rows)

    per_scenario = summarize_rows(rows, group_keys=["scenario", "policy"], value_keys=METRICS)
    _write_csv(os.path.join(results_dir, "summary.csv"), per_scenario)
    with open(os.path.join(results_dir, "summary.json"), "w") as f:
        json.dump(per_scenario, f, indent=2)

    comparison = build_comparison_table(rows)
    _write_csv(os.path.join(results_dir, "comparison.csv"), comparison)

    elapsed = time.time() - t0
    meta = {
        "scenarios": {name: spec["seeds"] for name, spec in SCENARIOS.items()},
        "total_runs": len(rows),
        "elapsed_seconds": elapsed,
    }
    with open(os.path.join(results_dir, "run_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    return {"rows": rows, "per_scenario": per_scenario, "comparison": comparison, "meta": meta}


if __name__ == "__main__":
    result = run_all()
    print(f"Completed {result['meta']['total_runs']} runs in {result['meta']['elapsed_seconds']:.2f}s")
    print(f"Results written to {RESULTS_DIR}")

    from experiments.charts import generate_all_charts
    charts = generate_all_charts()
    print(f"Generated {len(charts)} charts in {RESULTS_DIR}")
