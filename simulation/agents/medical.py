"""MedicalTriageAgent: registers every victim into shared knowledge at the
start of the run (assessing the scene is this agent's own domain, so it
legitimately reads the ground-truth Environment for this one purpose --
unlike the rescue agents, which only ever see the shared blackboard) and
republishes priority as waiting time accrues.

Every victim is known to both simulation modes from t=0. This project is
about task-allocation coordination between the two rescue agents, not
sensor/detection latency, so there is no drone and no staggered discovery.
"""

from __future__ import annotations

from simulation.agents.base import Agent
from simulation.coordination.messages import Event, EventType
from simulation.coordination.shared_state import SharedState

PRIORITY_CHANGE_THRESHOLD = 0.05  # only publish PRIORITY_UPDATED on a meaningful change


class MedicalTriageAgent(Agent):
    def __init__(self, agent_id: str = "medical"):
        super().__init__(agent_id)
        self._registered = False
        self._last_published_priority: dict[str, float] = {}

    def observe(self, environment) -> list:
        return list(environment.victims.values())

    def update_state(self, observations: list) -> None:
        self._victims = observations

    def communicate(self, shared_state: SharedState) -> None:
        if not self._registered:
            for v in self._victims:
                shared_state.publish(Event(
                    timestamp=self.timestamp, source=self.agent_id, type=EventType.VICTIM_DETECTED,
                    payload={
                        "victim_id": v.victim_id, "position": v.position, "severity": v.severity.value,
                        "required_resources": v.required_resources,
                    },
                ))
            self._registered = True

        for v in self._victims:
            if v.status == "rescued":
                continue
            priority = v.priority()
            prev = self._last_published_priority.get(v.victim_id)
            if prev is None or abs(prev - priority) >= PRIORITY_CHANGE_THRESHOLD:
                self._last_published_priority[v.victim_id] = priority
                shared_state.publish(Event(
                    timestamp=self.timestamp, source=self.agent_id, type=EventType.PRIORITY_UPDATED,
                    payload={"victim_id": v.victim_id, "priority": priority},
                ))
        shared_state.set_agent_status(self.agent_id, status="triaging")

    def decide(self, shared_state: SharedState) -> None:
        return None

    def act(self, environment, decision) -> None:
        pass
