"""The shared knowledge / communication layer (a blackboard).

Every victim is registered here at t=0 (published by the Medical Agent, see
agents/medical.py) so both simulation modes start with identical
information -- this project is about task-allocation coordination, not
sensing. What differs between modes is `assignments`: in MAS mode it is the
authoritative record of who is going after which victim, checked before a
new proposal is made; in No-Coordination mode it is never consulted by the
rescue agents when picking a target, which is exactly what lets two agents
independently commit to the same victim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulation.coordination.messages import Event, EventType

Position = tuple[int, int]


@dataclass
class KnownVictim:
    victim_id: str
    position: Position
    severity: str
    priority: float = 0.0
    status: str = "detected"
    assigned_agent: str | None = None
    required_resources: int = 1


class SharedState:
    """Blackboard shared by all agents. Publishing an event both appends to
    the searchable log and updates the small derived views (known victims,
    known blocked cells, assignments) that agents query when they decide.
    """

    def __init__(self):
        self.event_log: list[Event] = []
        self.known_victims: dict[str, KnownVictim] = {}
        self.known_blocked: set[Position] = set()
        self.resource_snapshot: dict = {"medical_kits": 0}
        self.assignments: dict[str, str] = {}  # victim_id -> agent_id
        self.agent_status: dict[str, dict] = {}  # agent_id -> {position, status, target}
        self.resource_responses: dict[tuple[str, str], str] = {}  # (agent_id, victim_id) -> "granted"/"denied"
        # Claims whose TASK_ASSIGNED broadcast was lost in transit (lossy
        # communication experiments): the claimant knows, nobody else does.
        self.hidden_claims: set[str] = set()

    # -- publishing -----------------------------------------------------
    def publish(self, event: Event) -> None:
        self.event_log.append(event)
        p = event.payload

        if event.type == EventType.VICTIM_DETECTED:
            self.known_victims[p["victim_id"]] = KnownVictim(
                victim_id=p["victim_id"], position=p["position"], severity=p["severity"],
                priority=p.get("priority", 0.0), required_resources=p.get("required_resources", 1),
            )
        elif event.type == EventType.PRIORITY_UPDATED:
            kv = self.known_victims.get(p["victim_id"])
            if kv:
                kv.priority = p["priority"]
        elif event.type == EventType.ROAD_BLOCKED:
            self.known_blocked.add(tuple(p["cell"]))
        elif event.type == EventType.ROAD_OPENED:
            self.known_blocked.discard(tuple(p["cell"]))
        elif event.type == EventType.RESOURCE_ALLOCATED:
            self.resource_snapshot["medical_kits"] = p.get("remaining", self.resource_snapshot["medical_kits"])
        elif event.type == EventType.RESOURCE_DENIED:
            self.resource_snapshot["medical_kits"] = p.get("remaining", self.resource_snapshot["medical_kits"])
        elif event.type in (EventType.TASK_ASSIGNED, EventType.TASK_REASSIGNED):
            self.assignments[p["victim_id"]] = p["agent_id"]
            kv = self.known_victims.get(p["victim_id"])
            if kv:
                kv.status = "assigned"
                kv.assigned_agent = p["agent_id"]
        elif event.type == EventType.VICTIM_RESCUED:
            self.assignments.pop(p["victim_id"], None)
            self.hidden_claims.discard(p["victim_id"])
            kv = self.known_victims.get(p["victim_id"])
            if kv:
                kv.status = "rescued"

    def set_agent_status(self, agent_id: str, **fields) -> None:
        self.agent_status.setdefault(agent_id, {}).update(fields)

    # -- querying ---------------------------------------------------------
    def unassigned_known_victims(self, viewer: str | None = None) -> list[KnownVictim]:
        """MAS mode: candidates that are neither rescued nor already
        claimed by another agent's resolved assignment. A claim whose
        broadcast was lost is invisible to every agent except its owner."""
        return [
            v for v in self.known_victims.values()
            if v.status != "rescued" and (
                v.victim_id not in self.assignments
                or (v.victim_id in self.hidden_claims and self.assignments[v.victim_id] != viewer))
        ]

    def not_yet_rescued_known_victims(self) -> list[KnownVictim]:
        """No-Coordination mode: candidates are simply "not rescued yet" --
        deliberately does not consult `assignments`, since checking what
        another agent is already going after would itself be a form of
        coordination."""
        return [v for v in self.known_victims.values() if v.status != "rescued"]

    def events_since(self, timestamp: int) -> list[Event]:
        return [e for e in self.event_log if e.timestamp >= timestamp]

    def log_lines(self, limit: int | None = None) -> list[str]:
        events = self.event_log[-limit:] if limit else self.event_log
        return [e.to_log_line() for e in events]
