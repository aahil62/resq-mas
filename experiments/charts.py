"""Generates the 3 required chart PNGs strictly from results/comparison.csv
(written by runner.py). No values are computed or hardcoded here."""

from __future__ import annotations

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

NC_COLOR = "#4C72B0"
MAS_COLOR = "#DD8452"

# Modeling assumption: 1 simulation timestep = 1 simulated minute (see
# README.md / docs/methodology.md). Values are simulated minutes produced
# by the model, not real-world measured rescue times.
CHARTS = [
    ("completion_time", "Completion Time (Minutes)", "minutes", "min", "chart_1_completion_time.png"),
    ("avg_waiting_time", "Average Waiting Time (Minutes)", "minutes", "min", "chart_2_avg_waiting_time.png"),
    ("duplicate_conflicts", "Duplicate / Conflicting Target Assignments", "count per run", "", "chart_3_conflicts.png"),
]


def _read_csv(name: str) -> list[dict]:
    path = os.path.join(RESULTS_DIR, name)
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _chart(rows: list[dict], metric: str, title: str, ylabel: str, unit_suffix: str, filename: str) -> None:
    row = next((r for r in rows if r["metric"] == metric), None)
    if row is None:
        return
    nc_v = float(row["no_coordination_mean"])
    mas_v = float(row["mas_mean"])
    improvement = float(row["improvement_pct"])

    fig, ax = plt.subplots(figsize=(6, 4.5))
    bars = ax.bar(["No Coordination", "MAS"], [nc_v, mas_v], color=[NC_COLOR, MAS_COLOR])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    for bar, val in zip(bars, [nc_v, mas_v]):
        label = f"{val:.2f} {unit_suffix}".strip()
        ax.annotate(label, (bar.get_x() + bar.get_width() / 2, val), ha="center", va="bottom")
    sign = "+" if improvement >= 0 else ""
    ax.set_xlabel(f"MAS change vs No Coordination: {sign}{improvement:.1f}%\n(positive = MAS better)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, filename), dpi=150)
    plt.close(fig)


def generate_all_charts() -> list[str]:
    comparison = _read_csv("comparison.csv")
    for metric, title, ylabel, unit_suffix, filename in CHARTS:
        _chart(comparison, metric, title, ylabel, unit_suffix, filename)
    return sorted(f for f in os.listdir(RESULTS_DIR) if f.endswith(".png"))


if __name__ == "__main__":
    generated = generate_all_charts()
    print(f"Generated {len(generated)} charts in {RESULTS_DIR}:")
    for g in generated:
        print(" -", g)
