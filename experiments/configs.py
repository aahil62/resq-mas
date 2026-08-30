"""Default demo scenario + the 5 controlled scenarios used by
experiments/runner.py. Every scenario is run under both No Coordination and
MAS with identical initial conditions (grid, victim positions/priorities,
starting positions, obstacles, resources, seed) -- the only thing that
differs is whether the two rescue agents exchange proposals before
committing to a target.
"""

from __future__ import annotations

from simulation.environment import Severity

# 2 critical, 2 high, 2 moderate -- deliberately arranged (see
# experiments/scenarios.py for placement) so the two rescue agents'
# candidate lists genuinely overlap: this is what gives No Coordination a
# real chance to produce duplicate targeting, without hardcoding a result.
DEFAULT_SEVERITY_SEQUENCE = (
    Severity.CRITICAL, Severity.CRITICAL, Severity.HIGH, Severity.HIGH, Severity.MODERATE, Severity.MODERATE,
)

DEFAULT_SEED = 11  # curated flagship demo seed: both agents naturally pick the same critical victim at t=0

DEFAULTS = {
    "width": 15,
    "height": 15,
    "victim_count": 6,
    "blockage_level": 0.0,
    "max_time": 300,
}


def resources_for(victim_count: int) -> int:
    """One kit per victim -- resources are a simple feasibility gate here,
    not the thing under study, so they should not become the bottleneck."""
    return victim_count


# Each controlled scenario: a handful of seeds, run under both modes.
# ~10 (scenario, seed) combinations x 2 modes = ~20 total runs.
SCENARIOS = {
    "high_overlap": {
        "seeds": [11, 17],
        "victim_count": 6,
        "severity_sequence": DEFAULT_SEVERITY_SEQUENCE,
        "blockage_level": 0.0,
        "description": "Both agents' best candidate is naturally the same critical victim.",
    },
    "moderate_overlap": {
        "seeds": [2, 5],
        "victim_count": 6,
        "severity_sequence": DEFAULT_SEVERITY_SEQUENCE,
        "blockage_level": 0.0,
        "description": "Agents start on different victims but their candidate sets overlap as priorities shift.",
    },
    "more_victims_than_agents": {
        "seeds": [1, 2],
        "victim_count": 10,
        "severity_sequence": None,  # randomly distributed severities
        "blockage_level": 0.0,
        "description": "10 victims, 2 rescue agents -- more opportunity for both wasted duplicate effort and parallel coverage.",
    },
    "low_conflict": {
        "seeds": [25, 30],
        "victim_count": 6,
        "severity_sequence": DEFAULT_SEVERITY_SEQUENCE,
        "blockage_level": 0.0,
        "description": "A scenario where the two agents' preferences rarely collide -- coordination has little to fix.",
    },
    "blocked_route": {
        "seeds": [1, 9],
        "victim_count": 6,
        "severity_sequence": DEFAULT_SEVERITY_SEQUENCE,
        "blockage_level": 0.2,
        "description": "Same overlap-prone layout, plus roads that block and reopen mid-run (BFS replanning).",
    },
}
