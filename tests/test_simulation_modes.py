"""Tests for the core story of this project: two independent rescue agents
can duplicate effort without coordination, and MAS mode detects/resolves
that before either commits.
"""

from simulation.environment import ScenarioConfig, Severity, VictimStatus
from simulation.simulation import Simulation, run_mas, run_no_coordination

SEVERITY_SEQUENCE = (Severity.CRITICAL, Severity.CRITICAL, Severity.HIGH, Severity.HIGH,
                     Severity.MODERATE, Severity.MODERATE)

# Curated seed (see experiments/configs.DEFAULT_SEED): both rescue agents'
# best candidate is naturally the same critical victim at t=0.
OVERLAP_SEED = 11


def demo_config(seed=OVERLAP_SEED, **overrides):
    cfg = ScenarioConfig(seed=seed, width=15, height=15, victim_count=6, severity_sequence=SEVERITY_SEQUENCE,
                          blockage_level=0.0, initial_resources=6, max_time=300)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def small_config(seed=1, **overrides):
    cfg = ScenarioConfig(seed=seed, width=12, height=12, victim_count=6, severity_sequence=SEVERITY_SEQUENCE,
                          blockage_level=0.1, initial_resources=6, max_time=300)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def test_both_modes_see_an_identical_scenario():
    cfg_a = demo_config()
    cfg_b = demo_config()
    sim_nc = Simulation(cfg_a, coordinate=False)
    sim_mas = Simulation(cfg_b, coordinate=True)
    assert sim_nc.environment.grid == sim_mas.environment.grid
    assert [v.position for v in sim_nc.environment.victims.values()] == \
        [v.position for v in sim_mas.environment.victims.values()]
    assert [v.severity for v in sim_nc.environment.victims.values()] == \
        [v.severity for v in sim_mas.environment.victims.values()]


def test_independent_target_selection_does_not_consult_other_agent():
    """In No-Coordination mode, each rescue agent's candidate pool comes
    from not_yet_rescued_known_victims(), which never looks at what target
    the other agent just picked -- that is the whole mechanism under test."""
    sim = Simulation(demo_config(), coordinate=False)
    sim.tick()
    selections = [e for e in sim.shared_state.event_log if e.type.value == "TARGET_SELECTED" and e.timestamp == 0]
    assert len(selections) == 2  # both agents picked independently, in the same tick


def test_duplicate_target_selection_emerges_in_no_coordination():
    """This is the natural failure mode No Coordination is expected to
    exhibit -- not hardcoded, but a real consequence of both agents
    evaluating the same candidate list with no exchange of intent."""
    sim = Simulation(demo_config(), coordinate=False)
    sim.tick()
    targets = {ra.current_target for ra in sim.rescue_agents}
    assert len(targets) == 1  # both agents committed to the same victim
    assert sim.duplicate_conflicts >= 1


def test_mas_detects_conflict_when_both_agents_propose_the_same_victim():
    sim = Simulation(demo_config(), coordinate=True)
    sim.tick()
    conflicts = [e for e in sim.shared_state.event_log if e.type.value == "TASK_CONFLICT"]
    assert len(conflicts) == 1


def test_mas_resolves_conflict_so_agents_end_up_on_different_victims():
    """Tick 0: the conflict is resolved and the winner commits; the loser
    stays idle that tick (receive_assignment(None)) and picks its
    next-best candidate on tick 1 -- by tick 1 both should be on distinct
    victims, exactly the "A -> V1, B -> V2" outcome from the brief."""
    sim = Simulation(demo_config(), coordinate=True)
    sim.tick()
    sim.tick()
    targets = {ra.current_target for ra in sim.rescue_agents if ra.current_target}
    assert len(targets) == 2  # the loser moved on to a different victim
    assert sim.duplicate_conflicts == 0


def test_mas_never_produces_duplicate_conflicts_across_seeds():
    for seed in range(1, 11):
        result = run_mas(demo_config(seed=seed))
        assert result.duplicate_conflicts == 0, f"seed={seed} should have 0 duplicate conflicts under MAS"


def test_no_coordination_agent_reassigns_after_finding_victim_already_rescued():
    """When both agents chase the same victim, whichever arrives second
    must discover it is already rescued and pick something else instead of
    idling forever."""
    sim = Simulation(demo_config(), coordinate=False)
    sim.tick()
    contested_victim = next(iter({ra.current_target for ra in sim.rescue_agents}))
    for _ in range(200):
        if sim.environment.victims[contested_victim].status == VictimStatus.RESCUED:
            break
        sim.tick()
    assert sim.environment.victims[contested_victim].status == VictimStatus.RESCUED

    reassign_events = [e for e in sim.shared_state.event_log
                        if e.type.value == "TASK_REASSIGNED" and e.payload.get("reason") == "victim_already_rescued"]
    assert len(reassign_events) >= 1


def test_victim_rescue_reaches_rescued_status():
    sim = Simulation(demo_config(), coordinate=True)
    run_result = sim.run()
    rescued_count = sum(1 for v in sim.environment.victims.values() if v.status == VictimStatus.RESCUED)
    assert rescued_count == run_result.victims_rescued
    assert run_result.victims_rescued >= 1


def test_waiting_time_is_recorded_for_rescued_victims():
    result = run_mas(demo_config())
    assert all(w >= 0 for w in result.waiting_times)
    assert len(result.waiting_times) == result.victims_rescued


def test_no_coordination_is_deterministic_for_fixed_seed():
    r1 = run_no_coordination(small_config(seed=5))
    r2 = run_no_coordination(small_config(seed=5))
    assert r1.completion_time == r2.completion_time
    assert r1.victims_rescued == r2.victims_rescued
    assert r1.duplicate_conflicts == r2.duplicate_conflicts
    assert r1.waiting_times == r2.waiting_times


def test_mas_is_deterministic_for_fixed_seed():
    r1 = run_mas(small_config(seed=5))
    r2 = run_mas(small_config(seed=5))
    assert r1.completion_time == r2.completion_time
    assert r1.victims_rescued == r2.victims_rescued
    assert r1.duplicate_conflicts == r2.duplicate_conflicts
    assert r1.waiting_times == r2.waiting_times


def test_scarce_resources_cap_how_many_victims_can_be_rescued():
    result = run_mas(demo_config(initial_resources=3))
    assert result.victims_rescued <= 3
