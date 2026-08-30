"""The simulation loop: instantiates Medical, Logistics, Rescue A, Rescue B
around a SharedState blackboard and steps them through an Environment.

One class, `Simulation`, drives both modes -- `coordinate=True` (MAS) and
`coordinate=False` (No Coordination) -- because they are the same system
with exactly one behavioural difference (see agents/rescue.py and the
`tick()` method below): whether conflicting proposals are resolved before
either rescue agent commits to a target, or each commits unconditionally.
Everything else -- the environment, the agents, BFS routing, resource
handling -- is identical code for both modes, which is what makes the
comparison fair.

Per tick:
 1. apply scheduled blockage events
 2. Medical Agent registers victims (once) and republishes priority
 3. Logistics Agent resolves last tick's resource requests
 4. rescue agents evaluate candidates and propose/select a target
 5. MAS only: conflicts among this tick's proposals are resolved
 6. targets are committed (resolved winners for MAS; unconditionally for
    No Coordination) and BFS routes are planned
 7. routes are re-validated / replanned if a known blockage now blocks them
 8. actions are executed (movement, resource requests, pickup, delivery)
 9. a tick-level check logs any victim two agents are simultaneously,
    genuinely committed to (the "duplicate_conflicts" metric)
 10. victim waiting times are updated
 11. repeat until every victim is rescued or max_time is reached
"""

from __future__ import annotations

from simulation.agents.logistics import LogisticsAgent
from simulation.agents.medical import MedicalTriageAgent
from simulation.agents.rescue import RescueAgent, WorldMap
from simulation.coordination.messages import Event, EventType
from simulation.coordination.shared_state import SharedState
from simulation.coordination.task_allocation import UtilityWeights, resolve_conflicts
from simulation.environment import CellType, Environment, ScenarioConfig, VictimStatus
from simulation.metrics.metrics import RunResult


def _build_world_map(environment: Environment) -> WorldMap:
    static_blocked = frozenset(
        (r, c)
        for r in range(environment.config.height)
        for c in range(environment.config.width)
        if environment.grid[r][c] == CellType.BUILDING
    )
    return WorldMap(
        width=environment.config.width, height=environment.config.height,
        static_blocked=static_blocked, hospital=environment.hospital, depots=list(environment.depots),
    )


class Simulation:
    def __init__(self, config: ScenarioConfig, coordinate: bool, rescue_agent_count: int = 2,
                 weights: UtilityWeights | None = None, scenario_name: str = "default"):
        self.coordinate = coordinate
        self.scenario_name = scenario_name
        self.environment = Environment(config)
        self.shared_state = SharedState()
        self.medical = MedicalTriageAgent("medical")
        self.logistics = LogisticsAgent("logistics")

        world_map = _build_world_map(self.environment)
        names = self._agent_names(rescue_agent_count)
        starts = self.environment.depots or [(0, 0)]
        self.rescue_agents = [
            RescueAgent(name, world_map, coordinate=coordinate, weights=weights,
                        start_position=starts[i % len(starts)])
            for i, name in enumerate(names)
        ]
        for ra in self.rescue_agents:
            self.environment.units[ra.agent_id] = ra.position

        self.duplicate_conflicts = 0
        self._logged_duplicate_victims: set[str] = set()

    @staticmethod
    def _agent_names(n: int) -> list[str]:
        if n <= 2:
            return ["rescue_a", "rescue_b"][:max(n, 1)]
        return [f"rescue_{chr(ord('a') + i)}" for i in range(n)]

    def tick(self) -> None:
        t = self.environment.time
        for e in self.environment.apply_scheduled_events():
            self.environment.event_history.append({"timestamp": t, **e})
            # Blockages are ground truth known to both modes immediately --
            # there is no sensor agent in this project (the point under
            # study is coordination, not information latency).
            self.shared_state.publish(Event(timestamp=t, source="system", type=EventType(e["type"]),
                                             payload=e["payload"]))

        self.medical.step(self.environment, self.shared_state, t)
        self.logistics.step(self.environment, self.shared_state, t)

        for ra in self.rescue_agents:
            ra.timestamp = t
            ra.observe(self.environment)
            ra.update_state(None)
            ra.communicate(self.shared_state)

        proposals = [ra.pending_proposal for ra in self.rescue_agents if ra.pending_proposal]

        if self.coordinate:
            # MAS: resolve conflicts among this tick's proposals BEFORE
            # anyone commits, so two agents never end up genuinely moving
            # toward the same victim.
            resolution = resolve_conflicts(proposals)
            for c in resolution.conflicts:
                self.shared_state.publish(Event(timestamp=t, source="coordinator",
                                                 type=EventType.TASK_CONFLICT, payload=c))
            for ra in self.rescue_agents:
                if ra.pending_proposal is None:
                    continue
                victim_id = ra.pending_proposal.victim_id
                winner = resolution.assignments.get(victim_id)
                ra.receive_assignment(self.shared_state, victim_id if winner == ra.agent_id else None,
                                       self.environment)
        else:
            # No Coordination: every proposal is committed unconditionally,
            # with no exchange between agents first. If both agents' best
            # candidate is the same victim, both commit to it.
            for ra in self.rescue_agents:
                if ra.pending_proposal is not None:
                    ra.receive_assignment(self.shared_state, ra.pending_proposal.victim_id, self.environment)

        for ra in self.rescue_agents:
            ra.decide(self.shared_state)
        for ra in self.rescue_agents:
            ra.act(self.environment, self.shared_state)

        self._check_duplicate_targets(t)
        self.environment.tick_waiting_times()
        self.environment.advance_time()

    def _check_duplicate_targets(self, t: int) -> None:
        """Detects victims two rescue agents are simultaneously, genuinely
        committed to (both `status != "idle"` and pointed at the same
        target). Runs identically in both modes; under MAS it should
        essentially never find anything, since resolve_conflicts() already
        prevented it before either agent committed."""
        targets: dict[str, list[str]] = {}
        for ra in self.rescue_agents:
            if ra.status != "idle" and ra.current_target:
                targets.setdefault(ra.current_target, []).append(ra.agent_id)

        for victim_id, agent_ids in targets.items():
            if len(agent_ids) > 1 and victim_id not in self._logged_duplicate_victims:
                self._logged_duplicate_victims.add(victim_id)
                self.duplicate_conflicts += 1
                self.shared_state.event_log.append(Event(
                    timestamp=t, source="system", type=EventType.DUPLICATE_DETECTED,
                    payload={"victim_id": victim_id, "agents": agent_ids},
                ))

    def run(self) -> RunResult:
        while not self.environment.is_complete() and not self._is_stalled():
            self.tick()
        return self._collect_result()

    def _is_stalled(self) -> bool:
        """True once resources are permanently exhausted and every rescue
        agent is idle: no further rescue can ever happen, so continuing to
        tick until max_time would only waste simulated time."""
        if self.environment.resources.medical_kits > 0:
            return False
        return all(ra.status == "idle" for ra in self.rescue_agents)

    def _collect_result(self) -> RunResult:
        victims = list(self.environment.victims.values())
        rescued = [v for v in victims if v.status == VictimStatus.RESCUED]

        return RunResult(
            policy="mas" if self.coordinate else "no_coordination",
            seed=self.environment.config.seed,
            scenario=self.scenario_name,
            completion_time=self.environment.time,
            victims_total=len(victims),
            victims_rescued=len(rescued),
            waiting_times=[float(v.waiting_time) for v in rescued],
            duplicate_conflicts=self.duplicate_conflicts,
            event_log=[e.to_dict() for e in self.shared_state.event_log],
        )


def run_mas(config: ScenarioConfig, rescue_agent_count: int = 2, weights: UtilityWeights | None = None,
            scenario_name: str = "default") -> RunResult:
    sim = Simulation(config, coordinate=True, rescue_agent_count=rescue_agent_count, weights=weights,
                      scenario_name=scenario_name)
    return sim.run()


def run_no_coordination(config: ScenarioConfig, rescue_agent_count: int = 2, weights: UtilityWeights | None = None,
                         scenario_name: str = "default") -> RunResult:
    sim = Simulation(config, coordinate=False, rescue_agent_count=rescue_agent_count, weights=weights,
                      scenario_name=scenario_name)
    return sim.run()


SCENARIO_PRESETS = {
    "small": {"victim_count": 6, "blockage_level": 0.0},
    "medium": {"victim_count": 6, "blockage_level": 0.1},
    "large": {"victim_count": 10, "blockage_level": 0.15},
}


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run one RESQ-MAS simulation.")
    parser.add_argument("--mode", choices=["mas", "no_coordination"], default="mas")
    parser.add_argument("--scenario", choices=sorted(SCENARIO_PRESETS), default="medium")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--victim-count", type=int, default=None)
    parser.add_argument("--blockage-level", type=float, default=None)
    parser.add_argument("--rescue-agents", type=int, default=2)
    parser.add_argument("--max-time", type=int, default=300)
    args = parser.parse_args()

    preset = SCENARIO_PRESETS[args.scenario]
    victim_count = args.victim_count if args.victim_count is not None else preset["victim_count"]
    blockage_level = args.blockage_level if args.blockage_level is not None else preset["blockage_level"]

    config = ScenarioConfig(seed=args.seed, victim_count=victim_count, blockage_level=blockage_level,
                             initial_resources=victim_count, max_time=args.max_time)
    runner = run_mas if args.mode == "mas" else run_no_coordination
    result = runner(config, rescue_agent_count=args.rescue_agents, scenario_name=args.scenario)

    print(f"RESQ-MAS -- mode={args.mode} scenario={args.scenario} seed={args.seed} victims={victim_count} "
          f"blockage={blockage_level} rescue_agents={args.rescue_agents}")
    for k, v in result.to_row().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _cli()
