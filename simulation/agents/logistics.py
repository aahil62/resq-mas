"""LogisticsAgent: the sole owner of the shared resource pool (medical
kits). Rescue agents never touch the resource pool directly -- they publish
a RESOURCE_REQUEST event and wait for RESOURCE_ALLOCATED/RESOURCE_DENIED.
This keeps allocation centralized in exactly one place (so resources can
never go negative or be double-allocated) while still routing through the
shared event log rather than a direct method call, so the exchange is
visible to everyone and logged like any other coordination event.
"""

from __future__ import annotations

from simulation.agents.base import Agent
from simulation.coordination.messages import Event, EventType
from simulation.coordination.shared_state import SharedState


class LogisticsAgent(Agent):
    def __init__(self, agent_id: str = "logistics"):
        super().__init__(agent_id)
        self._processed_idx = 0
        self._resources = None

    def observe(self, environment) -> dict:
        self._resources = environment.resources
        return {"medical_kits": environment.resources.medical_kits}

    def update_state(self, observations: dict) -> None:
        self._last_snapshot = observations

    def communicate(self, shared_state: SharedState) -> None:
        new_events = shared_state.event_log[self._processed_idx:]
        self._processed_idx = len(shared_state.event_log)

        for e in new_events:
            if e.type != EventType.RESOURCE_REQUEST:
                continue
            victim_id = e.payload["victim_id"]
            amount = e.payload["amount"]
            requester = e.source
            granted = self._resources.request(victim_id, amount, requester, self.timestamp)
            shared_state.resource_responses[(requester, victim_id)] = "granted" if granted else "denied"
            event_type = EventType.RESOURCE_ALLOCATED if granted else EventType.RESOURCE_DENIED
            shared_state.publish(Event(
                timestamp=self.timestamp, source=self.agent_id, type=event_type,
                payload={
                    "victim_id": victim_id, "agent_id": requester, "amount": amount,
                    "remaining": self._resources.medical_kits,
                },
            ))

        shared_state.resource_snapshot["medical_kits"] = self._resources.medical_kits
        shared_state.set_agent_status(self.agent_id, status="managing_resources",
                                       medical_kits=self._resources.medical_kits)

    def decide(self, shared_state: SharedState) -> None:
        return None

    def act(self, environment, decision) -> None:
        pass
