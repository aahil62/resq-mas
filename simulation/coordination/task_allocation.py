"""Multi-agent task allocation: utility scoring and conflict resolution.

This is the main intelligence of the project and it is deliberately kept
separate from BFS. BFS answers "how do I get there?"; this module answers
"which rescue agent should go, given what everyone else is doing?"

resolve_conflicts() is a pure, deterministic function of publicly-published
proposals (not a hidden "super agent"). Any rescue agent could run it
locally against the same proposal set and reach the same answer -- it is a
shared protocol, not a centralized decision-maker with private state.

In No-Coordination mode this module's resolve_conflicts() is never called --
each rescue agent commits to its own top candidate directly. That is the
entire, deliberate difference between the two modes (see simulation.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UtilityWeights:
    # utility = priority - distance_weight * travel_distance. Priority is
    # small (1-4, see environment.SEVERITY_SCORE) so distance_weight is
    # kept small too -- otherwise distance would swamp severity entirely
    # and priority would never actually influence which victim gets picked.
    distance_weight: float = 0.1


@dataclass
class Proposal:
    agent_id: str
    victim_id: str
    utility: float
    travel_distance: float
    timestamp: int


def compute_utility(victim_priority: float, travel_distance: float, weights: UtilityWeights) -> float:
    """utility = priority - distance_weight * distance"""
    return victim_priority - weights.distance_weight * travel_distance


@dataclass
class ConflictResolution:
    assignments: dict[str, str] = field(default_factory=dict)  # victim_id -> winning agent_id
    conflicts: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def resolve_conflicts(proposals: list[Proposal]) -> ConflictResolution:
    """Deterministic conflict resolution.

    Groups proposals by target victim. A victim with a single proposal is
    assigned outright. A victim with multiple proposals (both rescue agents
    targeted it in the same tick) is a conflict: the winner is the proposal
    with the highest utility, ties broken by shorter travel distance, then
    by agent_id (lexicographic) so the outcome is fully reproducible.
    """
    result = ConflictResolution()
    by_victim: dict[str, list[Proposal]] = {}
    for p in proposals:
        by_victim.setdefault(p.victim_id, []).append(p)

    for victim_id, props in by_victim.items():
        if len(props) == 1:
            result.assignments[victim_id] = props[0].agent_id
            continue

        ranked = sorted(props, key=lambda p: (-p.utility, p.travel_distance, p.agent_id))
        winner = ranked[0]
        losers = ranked[1:]
        result.assignments[victim_id] = winner.agent_id
        result.conflicts.append({
            "victim_id": victim_id,
            "proposals": [(p.agent_id, p.utility, p.travel_distance) for p in props],
            "winner": winner.agent_id,
        })
        for loser in losers:
            result.rejected.append({"agent_id": loser.agent_id, "victim_id": victim_id, "reason": "lost_conflict"})

    return result


def optimal_assignment(rows: dict[str, dict[str, tuple[float, float]]]) -> dict[str, str]:
    """Centralized reference allocator: match agents to distinct victims so
    that total utility is maximal (Hungarian method via SciPy).

    `rows` maps agent_id -> {victim_id: (utility, travel_distance)} over the
    victims that agent can reach. Returns agent_id -> victim_id; with more
    agents than victims the surplus agents are left unmatched. Unreachable
    pairs get a prohibitive cost so they are never chosen.
    """
    from scipy.optimize import linear_sum_assignment

    agents = sorted(rows)
    victims = sorted({v for r in rows.values() for v in r})
    if not agents or not victims:
        return {}
    big = 1e9
    cost = [[-rows[a][v][0] if v in rows[a] else big for v in victims] for a in agents]
    r_idx, c_idx = linear_sum_assignment(cost)
    return {agents[r]: victims[c] for r, c in zip(r_idx, c_idx) if cost[r][c] < big}
