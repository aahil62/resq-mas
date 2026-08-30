"""Common intelligent-agent model shared by every agent type.

Each agent has observations, local state, goals, actions, constraints, a
communication channel, and decision logic -- the classic agent/environment
loop:

    observe -> update_state -> communicate -> decide -> act

Rescue agents never read the ground-truth Environment directly -- they
only work from what has been published to SharedState (plus a static,
pre-disaster city map). Medical and Logistics each legitimately read the
one piece of ground truth that is their own domain (victims, resources
respectively) and publish it onward. This is what keeps the system
honestly multi-agent instead of one process wearing four hats.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from simulation.coordination.shared_state import SharedState


class Agent(ABC):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.timestamp: int = 0

    @abstractmethod
    def observe(self, environment) -> Any:
        """Gather raw observations. Only Medical/Logistics touch
        `environment` directly, for their own domain; rescue agents should
        treat it as unavailable and observe via shared state instead."""

    @abstractmethod
    def update_state(self, observations: Any) -> None:
        """Fold new observations into this agent's local state."""

    @abstractmethod
    def communicate(self, shared_state: SharedState) -> None:
        """Publish events derived from local state to the shared knowledge layer."""

    @abstractmethod
    def decide(self, shared_state: SharedState) -> Any:
        """Choose an action (or set of actions) given local state + shared knowledge."""

    @abstractmethod
    def act(self, environment, decision: Any) -> None:
        """Execute the decision, mutating environment/local state as needed."""

    def step(self, environment, shared_state: SharedState, timestamp: int) -> None:
        self.timestamp = timestamp
        observations = self.observe(environment)
        self.update_state(observations)
        self.communicate(shared_state)
        decision = self.decide(shared_state)
        self.act(environment, decision)
