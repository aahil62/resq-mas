"""Builds a ScenarioConfig for the default demo scenario or a named
controlled scenario from experiments/configs.py."""

from __future__ import annotations

from experiments.configs import DEFAULT_SEED, DEFAULT_SEVERITY_SEQUENCE, DEFAULTS, SCENARIOS, resources_for
from simulation.environment import ScenarioConfig


def default_scenario(seed: int = DEFAULT_SEED) -> ScenarioConfig:
    return ScenarioConfig(
        seed=seed, width=DEFAULTS["width"], height=DEFAULTS["height"], victim_count=DEFAULTS["victim_count"],
        severity_sequence=DEFAULT_SEVERITY_SEQUENCE, blockage_level=DEFAULTS["blockage_level"],
        initial_resources=resources_for(DEFAULTS["victim_count"]), max_time=DEFAULTS["max_time"],
    )


def build_scenario(seed: int, victim_count: int | None = None, blockage_level: float | None = None,
                    severity_sequence=DEFAULT_SEVERITY_SEQUENCE, max_time: int | None = None) -> ScenarioConfig:
    vc = victim_count if victim_count is not None else DEFAULTS["victim_count"]
    return ScenarioConfig(
        seed=seed, width=DEFAULTS["width"], height=DEFAULTS["height"], victim_count=vc,
        severity_sequence=severity_sequence,
        blockage_level=blockage_level if blockage_level is not None else DEFAULTS["blockage_level"],
        initial_resources=resources_for(vc), max_time=max_time if max_time is not None else DEFAULTS["max_time"],
    )


def named_scenario_configs(name: str) -> list[ScenarioConfig]:
    """All (seed) variants of a named controlled scenario from SCENARIOS."""
    spec = SCENARIOS[name]
    return [
        build_scenario(seed=seed, victim_count=spec["victim_count"], blockage_level=spec["blockage_level"],
                        severity_sequence=spec["severity_sequence"])
        for seed in spec["seeds"]
    ]
