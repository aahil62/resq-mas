"""Event/message types exchanged between agents through the shared
knowledge layer. This is the explicit communication mechanism the MAS
agents use instead of any agent knowing everything about the environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    VICTIM_DETECTED = "VICTIM_DETECTED"  # published once at setup by the Medical Agent, for every victim
    ROAD_BLOCKED = "ROAD_BLOCKED"
    ROAD_OPENED = "ROAD_OPENED"
    PRIORITY_UPDATED = "PRIORITY_UPDATED"
    TARGET_SELECTED = "TARGET_SELECTED"  # No-Coordination mode: an agent commits without checking others
    TASK_PROPOSED = "TASK_PROPOSED"      # MAS mode: an agent proposes, pending conflict resolution
    TASK_CONFLICT = "TASK_CONFLICT"      # MAS mode: two proposals targeted the same victim this tick
    TASK_ASSIGNED = "TASK_ASSIGNED"      # MAS mode: proposal won (no conflict, or won a conflict)
    TASK_REASSIGNED = "TASK_REASSIGNED"  # an agent gave up a target (resource timeout / already rescued)
    DUPLICATE_DETECTED = "DUPLICATE_DETECTED"  # two agents are simultaneously committed to the same victim
    RESOURCE_REQUEST = "RESOURCE_REQUEST"
    RESOURCE_ALLOCATED = "RESOURCE_ALLOCATED"
    RESOURCE_DENIED = "RESOURCE_DENIED"
    ROUTE_INVALIDATED = "ROUTE_INVALIDATED"
    ROUTE_REPLANNED = "ROUTE_REPLANNED"
    VICTIM_RESCUED = "VICTIM_RESCUED"


@dataclass
class Event:
    timestamp: int
    source: str
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "type": self.type.value,
            "payload": self.payload,
        }

    def to_log_line(self) -> str:
        # Modeling assumption: 1 simulation timestep = 1 simulated minute.
        return f"[{self.timestamp} min] {self.source}: {self.type.value} {self.payload}"
