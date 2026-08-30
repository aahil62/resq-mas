"""Shared result schema and statistics comparing No-Coordination vs MAS.

Deliberately minimal: exactly the 3 metrics the assessment cares about --
completion time, average victim waiting time, and duplicate/conflicting
target assignments. `duplicate_conflicts` is the metric that most directly
demonstrates the point of this project: it counts how many times two
rescue agents ended up genuinely, simultaneously committed to the same
victim. Under MAS this should be at (or very near) zero, because
conflicting proposals are resolved before either agent commits.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class RunResult:
    policy: str  # "no_coordination" | "mas"
    seed: int
    scenario: str
    completion_time: int
    victims_total: int
    victims_rescued: int
    waiting_times: list[float]
    duplicate_conflicts: int
    event_log: list[dict] = field(default_factory=list)

    def to_row(self) -> dict:
        return {
            "policy": self.policy,
            "seed": self.seed,
            "scenario": self.scenario,
            "completion_time": self.completion_time,
            "victims_total": self.victims_total,
            "victims_rescued": self.victims_rescued,
            "avg_waiting_time": _mean(self.waiting_times),
            "duplicate_conflicts": self.duplicate_conflicts,
        }


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


@dataclass
class Stat:
    mean: float
    median: float
    stdev: float
    min: float
    max: float
    n: int

    def to_dict(self) -> dict:
        return {"mean": self.mean, "median": self.median, "stdev": self.stdev,
                "min": self.min, "max": self.max, "n": self.n}


def compute_stat(values: list[float]) -> Stat:
    if not values:
        return Stat(mean=0.0, median=0.0, stdev=0.0, min=0.0, max=0.0, n=0)
    return Stat(
        mean=statistics.fmean(values),
        median=statistics.median(values),
        stdev=statistics.pstdev(values) if len(values) > 1 else 0.0,
        min=min(values),
        max=max(values),
        n=len(values),
    )


# Metric direction: True if a lower value is better (used to decide the sign
# of the improvement calculation and to avoid mislabeling a metric).
LOWER_IS_BETTER = {
    "completion_time": True,
    "avg_waiting_time": True,
    "duplicate_conflicts": True,
    "victims_rescued": False,
}


def percent_improvement(baseline_value: float, mas_value: float, metric: str) -> float:
    """improvement = ((no_coordination - mas) / no_coordination) * 100,
    sign-adjusted so a positive number always means "MAS is better on this
    metric"."""
    if baseline_value == 0:
        return 0.0
    lower_is_better = LOWER_IS_BETTER.get(metric, True)
    raw = (baseline_value - mas_value) / abs(baseline_value) * 100
    return raw if lower_is_better else -raw


def summarize_rows(rows: list[dict], group_keys: list[str], value_keys: list[str]) -> list[dict]:
    """Group `rows` (dicts, e.g. from RunResult.to_row()) by group_keys and
    compute mean/median/stdev/min/max for each value_key within each group."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        groups.setdefault(key, []).append(row)

    summary = []
    for key, group_rows in groups.items():
        entry = dict(zip(group_keys, key))
        entry["n_runs"] = len(group_rows)
        for vk in value_keys:
            stat = compute_stat([r[vk] for r in group_rows])
            for stat_name, stat_value in stat.to_dict().items():
                if stat_name == "n":
                    continue
                entry[f"{vk}_{stat_name}"] = stat_value
        summary.append(entry)
    return summary
