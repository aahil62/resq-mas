from simulation.environment import (
    CellType,
    Environment,
    ResourcePool,
    ScenarioConfig,
    Severity,
    Victim,
    VictimStatus,
)


def make_env(**overrides):
    cfg = ScenarioConfig(seed=7, width=10, height=10, victim_count=5, blockage_level=0.1,
                          initial_resources=10, max_time=200)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return Environment(cfg)


def test_environment_initializes_grid_and_victims():
    env = make_env()
    assert len(env.grid) == env.config.height
    assert len(env.grid[0]) == env.config.width
    assert len(env.victims) == 5
    assert env.grid[env.hospital[0]][env.hospital[1]] == CellType.HOSPITAL


def test_environment_is_deterministic_for_same_seed():
    env_a = make_env()
    env_b = make_env()
    assert env_a.grid == env_b.grid
    assert [v.position for v in env_a.victims.values()] == [v.position for v in env_b.victims.values()]
    assert [(e.timestep, e.kind, e.payload) for e in env_a.schedule] == \
        [(e.timestep, e.kind, e.payload) for e in env_b.schedule]


def test_different_seeds_produce_different_layouts():
    env_a = make_env(seed=1)
    env_b = make_env(seed=2)
    positions_a = sorted(v.position for v in env_a.victims.values())
    positions_b = sorted(v.position for v in env_b.victims.values())
    assert positions_a != positions_b


def test_explicit_severity_sequence_is_applied_in_order():
    seq = (Severity.CRITICAL, Severity.CRITICAL, Severity.HIGH, Severity.HIGH, Severity.MODERATE)
    env = make_env(severity_sequence=seq)
    severities = [v.severity for v in env.victims.values()]
    assert severities == list(seq)


def test_all_victims_known_from_the_start_no_staggered_spawning():
    env = make_env()
    assert len(env.victims) == 5
    for v in env.victims.values():
        assert v.status == VictimStatus.DETECTED


def test_building_cells_are_not_traversable():
    env = make_env()
    for r in range(env.config.height):
        for c in range(env.config.width):
            if env.grid[r][c] == CellType.BUILDING:
                assert not env.is_traversable((r, c))


def test_dynamic_blockage_events_toggle_traversability():
    env = make_env()
    block_events = [e for e in env.schedule if e.kind == "block"]
    assert block_events, "scenario with blockage_level>0 should schedule at least one block event"
    ev = block_events[0]
    cell = ev.payload["cell"]

    env.time = ev.timestep
    assert env.is_traversable(cell)
    env.apply_scheduled_events()
    assert not env.is_traversable(cell)


def test_no_blockage_schedules_no_events():
    env = make_env(blockage_level=0.0)
    assert env.schedule == []


def test_waiting_time_increments_for_unrescued_victims():
    env = make_env()
    v = next(iter(env.victims.values()))
    assert v.waiting_time == 0
    env.tick_waiting_times()
    assert v.waiting_time == 1
    env.tick_waiting_times()
    assert v.waiting_time == 2


def test_waiting_time_does_not_increment_after_rescue():
    env = make_env()
    v = next(iter(env.victims.values()))
    v.status = VictimStatus.RESCUED
    env.tick_waiting_times()
    assert v.waiting_time == 0


def test_priority_formula_orders_by_severity_then_waiting_time():
    critical = Victim(victim_id="c", position=(0, 0), severity=Severity.CRITICAL)
    low = Victim(victim_id="l", position=(0, 0), severity=Severity.LOW)
    assert critical.priority() > low.priority()

    low_waited = Victim(victim_id="l2", position=(0, 0), severity=Severity.LOW, waiting_time=1000)
    assert low_waited.priority() > low.priority()


def test_is_complete_when_all_victims_rescued():
    env = make_env(victim_count=1)
    v = next(iter(env.victims.values()))
    v.status = VictimStatus.RESCUED
    assert env.is_complete()


def test_is_complete_false_before_max_time_if_unrescued():
    env = make_env(victim_count=1)
    assert not env.is_complete()


def test_is_complete_true_at_max_time_even_if_unrescued():
    env = make_env(victim_count=1, max_time=5)
    env.time = 5
    assert env.is_complete()


# -- resources --------------------------------------------------------------

def test_resource_pool_grants_when_available():
    pool = ResourcePool(medical_kits=3)
    assert pool.request("v1", 1, "agent_a", timestamp=0)
    assert pool.medical_kits == 2
    assert pool.allocations["v1"] == 1


def test_resource_pool_denies_when_insufficient():
    pool = ResourcePool(medical_kits=0)
    granted = pool.request("v1", 1, "agent_a", timestamp=0)
    assert not granted
    assert pool.medical_kits == 0
    assert len(pool.denied_log) == 1
    assert pool.denied_log[0]["victim_id"] == "v1"


def test_resource_pool_never_goes_negative():
    pool = ResourcePool(medical_kits=1)
    assert pool.request("v1", 1, "a", 0)
    assert not pool.request("v2", 1, "b", 1)
    assert pool.medical_kits == 0


def test_resource_pool_denies_second_request_for_same_victim():
    """A second agent asking for a kit for a victim someone already has a
    kit reserved for should be denied -- one victim only needs one kit,
    regardless of how many agents are (independently) heading there."""
    pool = ResourcePool(medical_kits=5)
    assert pool.request("v1", 1, "agent_a", timestamp=0)
    granted = pool.request("v1", 1, "agent_b", timestamp=1)
    assert not granted
    assert pool.medical_kits == 4  # only one kit consumed, not two
    assert pool.denied_log[-1]["reason"] == "already_allocated"


def test_resource_pool_release_returns_kits():
    pool = ResourcePool(medical_kits=2)
    pool.request("v1", 2, "a", 0)
    assert pool.medical_kits == 0
    pool.release("v1")
    assert pool.medical_kits == 2
    assert "v1" not in pool.allocations
