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

# Blockages start within the first 120 min and last 10-75 min, as in the paper,
# independent of the (generous) safety cap on run length.
BLOCKAGE_HORIZON = 300


# The dashboard and API keep the original "no_coordination" name for the
# independent protocol; the engine calls it "independent".
ENGINE_POLICY = {"no_coordination": "independent"}


@dataclass
class ScenarioParams:
    policy: str  # "no_coordination" | "claim" | "mas" | "mas_iterative" | "hungarian" | "cbba"
    seed: int = 11
    victim_count: int = 6
    blockage_level: float = 0.0
    rescue_agent_count: int = 2
    initial_resources: int = 6
    max_time: int = 300
    width: int = 15
    height: int = 15
    use_demo_severities: bool = True
    arrival_window: int = 0
    comm_loss: float = 0.0
    burst_length: float | None = None


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
            arrival_window=params.arrival_window, blockage_horizon=BLOCKAGE_HORIZON,
        )
        self.engine = Simulation(cfg, policy=ENGINE_POLICY.get(params.policy, params.policy),
                                  rescue_agent_count=params.rescue_agent_count, comm_loss=params.comm_loss,
                                  burst_length=params.burst_length)
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
                "rescue_time": v.rescue_time, "appear_time": v.appear_time,
                "appeared": v.appear_time <= env.time,
            }
            for v in env.victims.values()
        ]

        units = [
            {"id": ra.agent_id, "position": list(ra.position), "status": ra.status,
             "target": ra.current_target, "path": [list(p) for p in ra.path],
             "wasted_ticks": ra.wasted_ticks,
             "channel_ok": not self.engine._channel_bad.get(ra.agent_id, False)}
            for ra in self.engine.rescue_agents
        ]

        rescued_victims = [v for v in env.victims.values() if v.status == VictimStatus.RESCUED]
        rescued = len(rescued_victims)
        waits = [v.waiting_time for v in rescued_victims]
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
                "victims_known": sum(1 for v in env.victims.values() if v.appear_time <= env.time),
                "duplicate_conflicts": self.engine.duplicate_conflicts,
                "avg_waiting_time": sum(waits) / len(waits) if waits else None,
                "wasted_ticks": sum(ra.wasted_ticks for ra in self.engine.rescue_agents),
                "idle_ticks": self.engine.idle_ticks,
                "messages": self.engine.messages,
                "message_payload": self.engine.message_payload,
                "consensus_rounds": self.engine.consensus_rounds,
            },
            "settings": {
                "arrival_window": self.params.arrival_window, "comm_loss": self.params.comm_loss,
                "burst_length": self.params.burst_length, "rescue_agent_count": self.params.rescue_agent_count,
            },
        }


SESSION = SimulationSession()
