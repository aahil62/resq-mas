from simulation.coordination.messages import Event, EventType
from simulation.coordination.shared_state import SharedState
from simulation.coordination.task_allocation import (
    Proposal,
    UtilityWeights,
    compute_utility,
    resolve_conflicts,
)


def test_compute_utility_rewards_priority_and_penalizes_distance():
    weights = UtilityWeights(distance_weight=0.1)
    high_priority = compute_utility(victim_priority=4.0, travel_distance=5, weights=weights)
    low_priority = compute_utility(victim_priority=1.0, travel_distance=5, weights=weights)
    assert high_priority > low_priority

    far = compute_utility(victim_priority=4.0, travel_distance=50, weights=weights)
    assert far < high_priority


def test_single_proposal_is_assigned_without_conflict():
    proposals = [Proposal(agent_id="rescue_a", victim_id="V1", utility=10.0, travel_distance=3, timestamp=0)]
    result = resolve_conflicts(proposals)
    assert result.assignments == {"V1": "rescue_a"}
    assert result.conflicts == []
    assert result.rejected == []


def test_duplicate_proposal_creates_a_conflict_resolved_by_utility():
    """Both agents proposing the same victim in the same tick is exactly
    the situation MAS mode must catch before either commits."""
    proposals = [
        Proposal(agent_id="rescue_a", victim_id="V1", utility=10.0, travel_distance=3, timestamp=0),
        Proposal(agent_id="rescue_b", victim_id="V1", utility=15.0, travel_distance=4, timestamp=0),
    ]
    result = resolve_conflicts(proposals)
    assert result.assignments["V1"] == "rescue_b"
    assert len(result.conflicts) == 1
    assert result.rejected == [{"agent_id": "rescue_a", "victim_id": "V1", "reason": "lost_conflict"}]


def test_conflict_tie_break_prefers_shorter_distance_then_agent_id():
    proposals = [
        Proposal(agent_id="rescue_b", victim_id="V1", utility=10.0, travel_distance=5, timestamp=0),
        Proposal(agent_id="rescue_a", victim_id="V1", utility=10.0, travel_distance=2, timestamp=0),
    ]
    result = resolve_conflicts(proposals)
    assert result.assignments["V1"] == "rescue_a"  # shorter distance wins the tie

    proposals_equal_distance = [
        Proposal(agent_id="rescue_b", victim_id="V1", utility=10.0, travel_distance=2, timestamp=0),
        Proposal(agent_id="rescue_a", victim_id="V1", utility=10.0, travel_distance=2, timestamp=0),
    ]
    result2 = resolve_conflicts(proposals_equal_distance)
    assert result2.assignments["V1"] == "rescue_a"  # lexicographically first agent_id wins


def test_conflict_resolution_is_deterministic_across_runs():
    proposals = [
        Proposal(agent_id="rescue_a", victim_id="V1", utility=10.0, travel_distance=3, timestamp=0),
        Proposal(agent_id="rescue_b", victim_id="V1", utility=10.0, travel_distance=3, timestamp=0),
    ]
    results = [resolve_conflicts(proposals).assignments for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_shared_state_publish_updates_derived_views():
    state = SharedState()
    state.publish(Event(timestamp=1, source="medical", type=EventType.VICTIM_DETECTED,
                         payload={"victim_id": "V1", "position": (1, 1), "severity": "high",
                                   "required_resources": 1}))
    assert "V1" in state.known_victims
    assert state.unassigned_known_victims()[0].victim_id == "V1"
    assert state.not_yet_rescued_known_victims()[0].victim_id == "V1"

    state.publish(Event(timestamp=2, source="rescue_a", type=EventType.TASK_ASSIGNED,
                         payload={"victim_id": "V1", "agent_id": "rescue_a"}))
    assert state.assignments["V1"] == "rescue_a"
    # MAS-only bookkeeping: once assigned, it drops out of the MAS
    # candidate pool but a No-Coordination agent would still see it (it
    # never consults `assignments`).
    assert state.unassigned_known_victims() == []
    assert state.not_yet_rescued_known_victims()[0].victim_id == "V1"

    state.publish(Event(timestamp=3, source="rescue_a", type=EventType.VICTIM_RESCUED,
                         payload={"victim_id": "V1", "agent_id": "rescue_a", "waiting_time": 5}))
    assert "V1" not in state.assignments
    assert state.known_victims["V1"].status == "rescued"
    assert state.not_yet_rescued_known_victims() == []


def test_shared_state_road_blocked_and_opened_toggle_known_blocked():
    state = SharedState()
    state.publish(Event(timestamp=1, source="system", type=EventType.ROAD_BLOCKED, payload={"cell": (2, 2)}))
    assert (2, 2) in state.known_blocked
    state.publish(Event(timestamp=2, source="system", type=EventType.ROAD_OPENED, payload={"cell": (2, 2)}))
    assert (2, 2) not in state.known_blocked
