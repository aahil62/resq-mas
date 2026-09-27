"""Tests for the extended task-allocation protocols used in the paper
(claim broadcast, iterative negotiation, centralized Hungarian reference)
and for lossy communication."""

import pytest

from simulation.coordination.task_allocation import optimal_assignment
from simulation.environment import ScenarioConfig, Severity
from simulation.simulation import POLICIES, Simulation, run_policy

SEVERITY_SEQUENCE = (Severity.CRITICAL, Severity.CRITICAL, Severity.HIGH, Severity.HIGH,
                     Severity.MODERATE, Severity.MODERATE)


def demo_config(seed=11, **overrides):
    cfg = ScenarioConfig(seed=seed, width=15, height=15, victim_count=6, severity_sequence=SEVERITY_SEQUENCE,
                          blockage_level=0.0, initial_resources=6, max_time=300)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


@pytest.mark.parametrize("policy", POLICIES)
def test_every_policy_rescues_every_victim(policy):
    result = run_policy(demo_config(), policy)
    assert result.victims_rescued == result.victims_total == 6


@pytest.mark.parametrize("policy", ["mas", "mas_iterative", "hungarian"])
@pytest.mark.parametrize("agents", [2, 4, 6])
def test_negotiating_policies_never_duplicate_without_message_loss(policy, agents):
    for seed in range(1000, 1010):
        cfg = ScenarioConfig(seed=seed, width=20, height=20, victim_count=12, initial_resources=12, max_time=2000)
        result = run_policy(cfg, policy, rescue_agent_count=agents)
        assert result.duplicate_conflicts == 0
        assert result.wasted_ticks == 0


def test_legacy_coordinate_flag_maps_to_policies():
    assert Simulation(demo_config(), coordinate=True).policy == "mas"
    assert Simulation(demo_config(), coordinate=False).policy == "independent"
    with pytest.raises(ValueError):
        Simulation(demo_config(), policy="telepathy")


def test_iterative_negotiation_leaves_no_loser_idle_on_the_conflict_tick():
    """Single-round MAS idles the conflict loser for one tick; the
    iterative protocol re-proposes within the same tick."""
    single = Simulation(demo_config(), policy="mas")
    single.tick()
    assert sorted(ra.status for ra in single.rescue_agents) == ["idle", "moving_to_victim"]

    iterative = Simulation(demo_config(), policy="mas_iterative")
    iterative.tick()
    assert all(ra.status == "moving_to_victim" for ra in iterative.rescue_agents)
    assert len({ra.current_target for ra in iterative.rescue_agents}) == 2


def test_claim_broadcast_blocks_later_duplicates_but_not_same_tick_ones():
    sim = Simulation(demo_config(), policy="claim")
    sim.tick()
    # Same-tick choices are not negotiated, so the curated overlap still happens.
    assert len({ra.current_target for ra in sim.rescue_agents}) == 1
    assert sim.shared_state.assignments  # but the claim is now public


def test_total_message_loss_degrades_mas_to_duplicate_prone_behaviour():
    lossless = run_policy(demo_config(), "mas", comm_loss=0.0)
    lossy = run_policy(demo_config(), "mas", comm_loss=1.0)
    assert lossless.duplicate_conflicts == 0
    assert lossy.duplicate_conflicts > 0
    assert lossy.victims_rescued == 6


def test_message_loss_does_not_change_the_world():
    a = Simulation(demo_config(), policy="mas", comm_loss=0.5)
    b = Simulation(demo_config(), policy="mas", comm_loss=0.0)
    assert a.environment.grid == b.environment.grid
    assert [v.position for v in a.environment.victims.values()] == \
        [v.position for v in b.environment.victims.values()]


def test_optimal_assignment_maximizes_total_utility():
    # Greedy would give A its favourite (v1, 10) and leave B with v2 (1): total 11.
    # The optimum sends A to v2 (9) and B to v1 (9): total 18.
    rows = {"A": {"v1": (10.0, 1), "v2": (9.0, 1)}, "B": {"v1": (9.0, 1), "v2": (1.0, 1)}}
    assert optimal_assignment(rows) == {"A": "v2", "B": "v1"}


def test_optimal_assignment_leaves_surplus_agents_unmatched():
    rows = {"A": {"v1": (5.0, 1)}, "B": {"v1": (4.0, 1)}, "C": {}}
    assert optimal_assignment(rows) == {"A": "v1"}


def test_messages_are_counted_only_for_communicating_policies():
    assert run_policy(demo_config(), "independent").messages == 0
    assert run_policy(demo_config(), "mas").messages > 0
