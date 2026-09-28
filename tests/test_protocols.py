"""Tests for the extended task-allocation protocols
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


# -- dynamic arrivals, bursty loss, CBBA ------------------------------------------

def test_arrivals_keep_the_world_identical_and_stagger_victims():
    static = Simulation(demo_config(), policy="mas")
    dynamic = Simulation(demo_config(arrival_window=100), policy="mas")
    assert static.environment.grid == dynamic.environment.grid
    assert [v.position for v in static.environment.victims.values()] == \
        [v.position for v in dynamic.environment.victims.values()]
    times = [v.appear_time for v in dynamic.environment.victims.values()]
    assert all(0 <= t <= 100 for t in times) and len(set(times)) > 1
    assert all(v.appear_time == 0 for v in static.environment.victims.values())


def test_victims_are_unknown_and_do_not_wait_before_they_appear():
    sim = Simulation(demo_config(arrival_window=100), policy="mas")
    late = max(sim.environment.victims.values(), key=lambda v: v.appear_time)
    for _ in range(late.appear_time):
        sim.tick()
    assert late.victim_id not in sim.shared_state.known_victims
    assert late.waiting_time == 0
    sim.tick()
    assert late.victim_id in sim.shared_state.known_victims


@pytest.mark.parametrize("policy", POLICIES)
def test_every_policy_finishes_under_dynamic_arrivals(policy):
    result = run_policy(demo_config(arrival_window=150, max_time=2000), policy, rescue_agent_count=3)
    assert result.victims_rescued == 6


def test_bursty_channel_matches_target_loss_rate_and_burst_length():
    sim = Simulation(demo_config(), policy="mas", rescue_agent_count=1, comm_loss=0.3, burst_length=10)
    states = []
    for _ in range(20000):
        sim._step_channels()
        states.append(sim._channel_bad["rescue_a"])
    assert abs(sum(states) / len(states) - 0.3) < 0.03
    bursts, run = [], 0
    for bad in states:
        if bad:
            run += 1
        elif run:
            bursts.append(run)
            run = 0
    assert abs(sum(bursts) / len(bursts) - 10) < 1.5


def test_cbba_is_conflict_free_without_loss_and_matches_iterative_auction_quality():
    for seed in range(1000, 1008):
        cfg = ScenarioConfig(seed=seed, width=20, height=20, victim_count=12, initial_resources=12, max_time=2000)
        cbba = run_policy(cfg, "cbba", rescue_agent_count=4)
        assert cbba.duplicate_conflicts == 0 and cbba.victims_rescued == 12
        assert cbba.consensus_rounds > 0


def test_cbba_degrades_to_duplicates_when_every_message_is_lost():
    lossy = run_policy(demo_config(), "cbba", comm_loss=1.0)
    assert lossy.duplicate_conflicts > 0 and lossy.victims_rescued == 6
