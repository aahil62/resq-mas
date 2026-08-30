"""Holds one live, steppable simulation (No Coordination or MAS) for the
dashboard's Live Simulation view. All simulation logic stays in the Python
engine -- this module only serializes engine state into JSON-friendly
dicts and exposes step/reset controls for the API layer to call.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.configs import DEFAULT_SEVERITY_SEQUENCE
from simulation.environment import ScenarioConfig, VictimStatus
from simulation.simulation import Simulation


@dataclass
class ScenarioParams:
    policy: str  # "no_coordination" | "mas"
    seed: int = 11
    victim_count: int = 6
    blockage_level: float = 0.0
    rescue_agent_count: int = 2
    initial_resources: int = 6
    max_time: int = 300
    width: int = 15
    height: int = 15
    use_demo_severities: bool = True


class SimulationSession:
    def __init__(self):
        self.params: ScenarioParams | None = None
        self.engine: Simulation | None = None

    def create(self, params: ScenarioParams) -> dict:
        self.params = params
        severity_sequence = DEFAULT_SEVERITY_SEQUENCE if (params.use_demo_severities and params.victim_count == 6) else None
        cfg = ScenarioConfig(
            seed=params.seed, width=params.width, height=params.height, victim_count=params.victim_count,
            severity_sequence=severity_sequence, blockage_level=params.blockage_level,
            initial_resources=params.initial_resources, max_time=params.max_time,
        )
        self.engine = Simulation(cfg, coordinate=(params.policy == "mas"),
                                  rescue_agent_count=params.rescue_agent_count)
        return self.state()

    def reset(self) -> dict:
        if self.params is None:
            raise ValueError("no scenario has been created yet")
        return self.create(self.params)

    def step(self, n: int = 1) -> dict:
        if self.engine is None:
            raise ValueError("no scenario has been created yet")
        for _ in range(n):
            if self.engine.environment.is_complete() or self.engine._is_stalled():
                break
            self.engine.tick()
        return self.state()

    def events(self, since: int = 0, limit: int = 200) -> list[dict]:
        if self.engine is None:
            return []
        raw = [e.to_dict() for e in self.engine.shared_state.event_log if e.timestamp >= since]
        return raw[-limit:]

    def state(self) -> dict:
        if self.engine is None:
            raise ValueError("no scenario has been created yet")
        env = self.engine.environment

        grid_cells = [[cell.value for cell in row] for row in env.grid]

        victims = [
            {
                "id": v.victim_id, "position": list(v.position), "severity": v.severity.value,
                "status": v.status.value, "waiting_time": v.waiting_time, "priority": v.priority(),
                "rescue_time": v.rescue_time,
            }
            for v in env.victims.values()
        ]

        units = [
            {"id": ra.agent_id, "position": list(ra.position), "status": ra.status,
             "target": ra.current_target, "path": [list(p) for p in ra.path]}
            for ra in self.engine.rescue_agents
        ]

        rescued = sum(1 for v in env.victims.values() if v.status == VictimStatus.RESCUED)
        completed = env.is_complete() or self.engine._is_stalled()

        return {
            "policy": self.params.policy,
            "time": env.time,
            "max_time": env.config.max_time,
            "completed": completed,
            "grid": {"width": env.config.width, "height": env.config.height, "cells": grid_cells},
            "hospital": list(env.hospital),
            "depots": [list(d) for d in env.depots],
            "blocked_cells": [list(c) for c in env.blocked_cells],
            "victims": victims,
            "units": units,
            "resources": {"medical_kits": env.resources.medical_kits, "available": env.config.initial_resources,
                          "denied_count": len(env.resources.denied_log)},
            "metrics": {
                "victims_total": len(env.victims), "victims_rescued": rescued,
                "duplicate_conflicts": self.engine.duplicate_conflicts,
            },
        }


SESSION = SimulationSession()
