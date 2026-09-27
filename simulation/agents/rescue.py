"""RescueAgent: the workhorse of the project. Rescue Agent A and Rescue
Agent B are both instances of this class, run independently. The `coordinate`
flag is the ONLY thing that differs between the two simulation modes:

- coordinate=True (MAS): communicate() only *proposes* a target
  (`TASK_PROPOSED`). The orchestrator collects every rescue agent's
  proposal for the tick and resolves conflicts (see
  coordination/task_allocation.py) BEFORE any agent commits -- so two
  agents never end up actually moving toward the same victim.
- coordinate=False (No Coordination): communicate() evaluates candidates
  exactly the same way, but the orchestrator commits every agent's choice
  unconditionally (`TARGET_SELECTED`), with no exchange of intentions
  first. If both agents' best candidate is the same victim, both commit to
  it -- that duplication is the entire point of this mode.

Either way, once a target is committed, everything downstream (BFS routing,
resource requests, movement, pickup, delivery, replanning on a blocked
route) is identical code -- coordination and route-following are separate
concerns on purpose (see docs/architecture.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulation.agents.base import Agent
from simulation.coordination.messages import Event, EventType
from simulation.coordination.shared_state import SharedState
from simulation.coordination.task_allocation import Proposal, UtilityWeights, compute_utility
from simulation.environment import VictimStatus
from simulation.search.bfs import GridSpec, Position, bfs, bfs_distances

RESOURCE_RETRY_INTERVAL = 5
RESOURCE_WAIT_TIMEOUT = 40  # ticks a unit will wait for a denied resource before abandoning the target


@dataclass
class WorldMap:
    """Static, pre-disaster knowledge every rescue agent legitimately has
    (the city layout: roads/buildings/hospital/depots) -- as opposed to
    *who else is going after which victim*, which coordination is about."""

    width: int
    height: int
    static_blocked: frozenset[Position]
    hospital: Position
    depots: list[Position] = field(default_factory=list)


class RescueAgent(Agent):
    def __init__(self, agent_id: str, world_map: WorldMap, coordinate: bool, weights: UtilityWeights | None = None,
                 start_position: Position | None = None):
        super().__init__(agent_id)
        self.world_map = world_map
        self.coordinate = coordinate
        self.weights = weights or UtilityWeights()
        self.position = start_position or (world_map.depots[0] if world_map.depots else (0, 0))

        self.status = "idle"  # idle | moving_to_victim | moving_to_hospital
        self.current_target: str | None = None
        self.carrying: str | None = None
        self.path: list[Position] = []
        self.resource_state = "none"  # none | requested | granted | denied
        self._last_request_tick = -RESOURCE_RETRY_INTERVAL
        self._resource_wait_start = 0
        self.pending_proposal: Proposal | None = None
        self._commit_tick = 0
        self.wasted_ticks = 0  # ticks spent committed to targets this agent later abandoned

    # -- Agent interface --------------------------------------------------
    def observe(self, environment) -> None:
        return None  # rescue agents never sense the environment directly

    def update_state(self, observations) -> None:
        pass

    def _grid_spec(self, shared_state: SharedState) -> GridSpec:
        blocked = set(self.world_map.static_blocked) | set(shared_state.known_blocked)
        return GridSpec(width=self.world_map.width, height=self.world_map.height, blocked=blocked)

    def communicate(self, shared_state: SharedState) -> None:
        """Evaluate candidate victims and either propose (MAS) or select
        (No Coordination) a target. In both modes this only decides *what*
        this agent wants -- committing happens afterward, in
        receive_assignment(), once the orchestrator has (for MAS) resolved
        any conflicts."""
        self.pending_proposal = None
        shared_state.set_agent_status(self.agent_id, position=self.position, status=self.status,
                                       target=self.current_target)
        if self.status != "idle":
            return

        ranked = self.rank_candidates(shared_state)
        if not ranked:
            return

        best_kv, best_distance, best_utility = ranked[0]
        proposal = Proposal(agent_id=self.agent_id, victim_id=best_kv.victim_id, utility=best_utility,
                             travel_distance=best_distance, timestamp=self.timestamp)
        self.pending_proposal = proposal
        event_type = EventType.TASK_PROPOSED if self.coordinate else EventType.TARGET_SELECTED
        shared_state.publish(Event(
            timestamp=self.timestamp, source=self.agent_id, type=event_type,
            payload={"victim_id": best_kv.victim_id, "utility": best_utility, "travel_distance": best_distance},
        ))
        shared_state.set_agent_status(self.agent_id, position=self.position, status=self.status,
                                       target=best_kv.victim_id)

    def rank_candidates(self, shared_state: SharedState, exclude: set[str] | frozenset[str] = frozenset()
                        ) -> list[tuple]:
        """Every reachable candidate as (known_victim, travel_distance,
        utility), best first. Ties keep blackboard order (stable sort), so
        ranked[0] is exactly the target the single-proposal protocol picks.
        `exclude` lets multi-round protocols drop victims already won by
        another agent earlier in the same tick."""
        candidates = (shared_state.unassigned_known_victims(viewer=self.agent_id) if self.coordinate
                      else shared_state.not_yet_rescued_known_victims())
        dist = bfs_distances(self._grid_spec(shared_state), self.position)
        scored = []
        for kv in candidates:
            if kv.victim_id in exclude:
                continue
            d = dist.get(tuple(kv.position))
            if d is None:
                continue
            scored.append((kv, d, compute_utility(kv.priority, d, self.weights)))
        scored.sort(key=lambda x: -x[2])
        return scored

    def receive_assignment(self, shared_state: SharedState, victim_id: str | None, environment=None) -> None:
        """Called by the orchestrator once, after every rescue agent's
        communicate(): with the resolved winner in MAS mode, or
        unconditionally with this agent's own selection in No-Coordination
        mode (see simulation.py -- that unconditional-vs-resolved call is
        the one line of difference between the two modes)."""
        if victim_id is None:
            if self.pending_proposal is not None:
                shared_state.set_agent_status(self.agent_id, position=self.position, status=self.status,
                                               target=None)
            return

        self.status = "moving_to_victim"
        self.current_target = victim_id
        self._commit_tick = self.timestamp
        self.resource_state = "none"
        self._resource_wait_start = self.timestamp
        if environment is not None:
            environment.victims[victim_id].status = VictimStatus.ASSIGNED
        if self.coordinate:
            shared_state.publish(Event(
                timestamp=self.timestamp, source=self.agent_id, type=EventType.TASK_ASSIGNED,
                payload={"victim_id": victim_id, "agent_id": self.agent_id},
            ))
        # else: No-Coordination mode already published TARGET_SELECTED for
        # this exact commitment in communicate() -- selecting *is*
        # committing there, so a second event would just be noise.
        kv = shared_state.known_victims[victim_id]
        grid = self._grid_spec(shared_state)
        result = bfs(grid, self.position, kv.position)
        self.path = result.path[1:] if result.found else []

    def decide(self, shared_state: SharedState) -> None:
        """Validate the current route against the latest known blockages
        and replan with BFS if it is no longer traversable."""
        if self.status not in ("moving_to_victim", "moving_to_hospital") or not self.path:
            return
        grid = self._grid_spec(shared_state)
        if all(grid.is_traversable(p) for p in self.path):
            return

        shared_state.publish(Event(
            timestamp=self.timestamp, source=self.agent_id, type=EventType.ROUTE_INVALIDATED,
            payload={"agent_id": self.agent_id, "target": self.current_target},
        ))
        goal = self._current_goal(shared_state)
        result = bfs(grid, self.position, goal)
        self.path = result.path[1:] if result.found else []
        shared_state.publish(Event(
            timestamp=self.timestamp, source=self.agent_id, type=EventType.ROUTE_REPLANNED,
            payload={"agent_id": self.agent_id, "target": self.current_target,
                     "path_length": result.path_length, "found": result.found},
        ))

    def _current_goal(self, shared_state: SharedState) -> Position:
        if self.status == "moving_to_victim":
            return shared_state.known_victims[self.current_target].position
        return self.world_map.hospital

    def act(self, environment, shared_state: SharedState) -> None:  # noqa: D401 - wider signature, see module docstring
        if self.status == "moving_to_victim":
            self._act_moving_to_victim(environment, shared_state)
        elif self.status == "moving_to_hospital":
            self._act_moving_to_hospital(environment, shared_state)
        shared_state.set_agent_status(self.agent_id, position=self.position, status=self.status,
                                       target=self.current_target)

    def _act_moving_to_victim(self, environment, shared_state: SharedState) -> None:
        victim = environment.victims.get(self.current_target)
        if victim is not None and victim.status == VictimStatus.RESCUED:
            # Another rescue agent already got there first (only possible
            # in No-Coordination mode). Give up and go looking for
            # something else instead of camping on an empty cell.
            self._abandon_target(shared_state, environment, reason="victim_already_rescued")
            return

        self._handle_resource_request(shared_state, environment)
        if self.status == "idle":
            return  # abandoned this target: resource wait exceeded RESOURCE_WAIT_TIMEOUT

        if self.path:
            self.position = self.path.pop(0)
            environment.units[self.agent_id] = self.position

        if self.path:
            return  # not there yet

        if self.resource_state != "granted":
            return  # wait at the victim's location until a kit is available

        victim.status = VictimStatus.EN_ROUTE
        self.carrying = self.current_target
        self.status = "moving_to_hospital"
        grid = self._grid_spec(shared_state)
        result = bfs(grid, self.position, self.world_map.hospital)
        self.path = result.path[1:] if result.found else []

    def _act_moving_to_hospital(self, environment, shared_state: SharedState) -> None:
        if self.path:
            self.position = self.path.pop(0)
            environment.units[self.agent_id] = self.position

        if self.path:
            return  # not there yet

        victim = environment.victims[self.carrying]
        victim.status = VictimStatus.RESCUED
        victim.rescue_time = self.timestamp
        shared_state.publish(Event(
            timestamp=self.timestamp, source=self.agent_id, type=EventType.VICTIM_RESCUED,
            payload={"victim_id": victim.victim_id, "agent_id": self.agent_id, "waiting_time": victim.waiting_time},
        ))
        self.carrying = None
        self.current_target = None
        self.status = "idle"
        self.resource_state = "none"

    def _handle_resource_request(self, shared_state: SharedState, environment) -> None:
        key = (self.agent_id, self.current_target)

        if self.resource_state == "none":
            self._request_resource(shared_state)
            return

        if self.resource_state == "requested":
            response = shared_state.resource_responses.get(key)
            if response == "granted":
                self.resource_state = "granted"
                return
            if response == "denied":
                self.resource_state = "denied"

        if self.resource_state != "denied":
            return

        if self.timestamp - self._resource_wait_start >= RESOURCE_WAIT_TIMEOUT:
            self._abandon_target(shared_state, environment, reason="resource_timeout")
        elif self.timestamp - self._last_request_tick >= RESOURCE_RETRY_INTERVAL:
            self._request_resource(shared_state)

    def _request_resource(self, shared_state: SharedState) -> None:
        kv = shared_state.known_victims.get(self.current_target)
        amount = kv.required_resources if kv else 1
        shared_state.resource_responses.pop((self.agent_id, self.current_target), None)
        shared_state.publish(Event(
            timestamp=self.timestamp, source=self.agent_id, type=EventType.RESOURCE_REQUEST,
            payload={"victim_id": self.current_target, "amount": amount},
        ))
        self.resource_state = "requested"
        self._last_request_tick = self.timestamp

    def _abandon_target(self, shared_state: SharedState, environment, reason: str) -> None:
        victim_id = self.current_target
        # Logged directly (not via shared_state.publish) because
        # TASK_REASSIGNED's normal handler would re-mark the victim
        # assigned to this agent, the opposite of an abandonment.
        shared_state.event_log.append(Event(
            timestamp=self.timestamp, source=self.agent_id, type=EventType.TASK_REASSIGNED,
            payload={"agent_id": self.agent_id, "victim_id": victim_id, "reason": reason},
        ))
        self.wasted_ticks += self.timestamp - self._commit_tick + 1
        # Release only a claim this agent itself holds: after a lost
        # message two agents can be committed to one victim, and the
        # loser giving up must not erase the winner's claim.
        if shared_state.assignments.get(victim_id) == self.agent_id:
            shared_state.assignments.pop(victim_id, None)
            shared_state.hidden_claims.discard(victim_id)
            kv = shared_state.known_victims.get(victim_id)
            if kv and kv.status != "rescued":
                kv.status = "detected"
                kv.assigned_agent = None
        if environment is not None and victim_id in environment.victims:
            v = environment.victims[victim_id]
            if v.status == VictimStatus.ASSIGNED and victim_id not in shared_state.assignments:
                v.status = VictimStatus.DETECTED
        self.status = "idle"
        self.current_target = None
        self.resource_state = "none"
        self.path = []
        shared_state.set_agent_status(self.agent_id, position=self.position, status=self.status, target=None)
