"""The disaster grid-world: state shared by both simulation modes (No
Coordination and MAS).

The Environment holds ground truth. It does not decide anything -- it just
tracks the grid, victims, resources, units, time, and the scripted schedule
of dynamic blockage events. Both modes are driven against an Environment
built from the same ScenarioConfig/seed, and every victim is known to both
modes from t=0 (there is no sensor/detection delay in this project -- the
thing under study is task-allocation coordination, not information
latency). Any behavioural difference between the two modes comes from
whether the two rescue agents exchange proposals before committing to a
target, not from what they know about the world.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

Position = tuple[int, int]


class CellType(str, Enum):
    ROAD = "road"
    BUILDING = "building"
    HOSPITAL = "hospital"
    DEPOT = "depot"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# Documented, deterministic severity -> score mapping used by the triage
# formula (matches the assessment brief exactly: critical=4, high=3,
# moderate=2, low=1).
SEVERITY_SCORE = {
    Severity.CRITICAL: 4.0,
    Severity.HIGH: 3.0,
    Severity.MODERATE: 2.0,
    Severity.LOW: 1.0,
}
WAITING_WEIGHT = 0.1  # small, so severity dominates but long waits still matter


class VictimStatus(str, Enum):
    DETECTED = "detected"  # known, unassigned
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"  # being carried to hospital
    RESCUED = "rescued"


@dataclass
class Victim:
    victim_id: str
    position: Position
    severity: Severity
    required_resources: int = 1
    status: VictimStatus = VictimStatus.DETECTED
    rescue_time: int | None = None
    waiting_time: int = 0
    hospital: Position | None = None

    def priority(self) -> float:
        """priority = severity_score + waiting_weight * waiting_time.

        Deterministic and transparent by design -- a rule, not a learned
        model. See docs/methodology.md.
        """
        return SEVERITY_SCORE[self.severity] + WAITING_WEIGHT * self.waiting_time


@dataclass
class ResourcePool:
    medical_kits: int
    allocations: dict[str, int] = field(default_factory=dict)  # victim_id -> kits allocated
    denied_log: list[dict] = field(default_factory=list)

    def request(self, victim_id: str, amount: int, requester: str, timestamp: int) -> bool:
        if victim_id in self.allocations:
            # Someone already secured a kit for this victim -- a second
            # request for the same victim needs no extra resource.
            self.denied_log.append({
                "timestamp": timestamp, "victim_id": victim_id, "requester": requester,
                "requested": amount, "available": self.medical_kits, "reason": "already_allocated",
            })
            return False
        if amount <= self.medical_kits:
            self.medical_kits -= amount
            self.allocations[victim_id] = amount
            return True
        self.denied_log.append({
            "timestamp": timestamp, "victim_id": victim_id, "requester": requester,
            "requested": amount, "available": self.medical_kits, "reason": "insufficient",
        })
        return False

    def release(self, victim_id: str) -> None:
        amount = self.allocations.pop(victim_id, 0)
        self.medical_kits += amount


@dataclass
class ScheduledEvent:
    timestep: int
    kind: str  # "block" | "unblock"
    payload: dict


@dataclass
class ScenarioConfig:
    seed: int
    width: int = 15
    height: int = 15
    victim_count: int = 6
    severity_sequence: tuple[Severity, ...] | None = None  # explicit severities, in order; else random
    blockage_level: float = 0.0  # fraction of road cells that get blocked at some point
    initial_resources: int = 6
    max_time: int = 300
    # Window (in ticks) over which blockages are scheduled; None keeps the
    # original behaviour of scaling it with max_time. Pinning it lets a long
    # safety cap on max_time coexist with blockages that land mid-run.
    blockage_horizon: int | None = None


def _carve_grid(rng: random.Random, width: int, height: int) -> tuple[list[list[CellType]], Position, list[Position]]:
    """Deterministically lay out a grid with a hospital, depots, and buildings.

    Uses a light density of "building" obstacles (~10% of cells), keeping
    the grid well-connected for BFS.
    """
    grid = [[CellType.ROAD for _ in range(width)] for _ in range(height)]

    hospital = (height // 2, width - 1)
    grid[hospital[0]][hospital[1]] = CellType.HOSPITAL

    depots = [(0, 0), (height - 1, 0)]
    for d in depots:
        grid[d[0]][d[1]] = CellType.DEPOT

    reserved = {hospital, *depots}
    n_buildings = int(0.10 * width * height)
    placed = 0
    attempts = 0
    while placed < n_buildings and attempts < n_buildings * 20:
        attempts += 1
        r = rng.randint(0, height - 1)
        c = rng.randint(0, width - 1)
        if (r, c) in reserved:
            continue
        grid[r][c] = CellType.BUILDING
        placed += 1

    return grid, hospital, depots


def generate_scenario(config: ScenarioConfig) -> tuple[list[list[CellType]], Position, list[Position], list[Victim], list[ScheduledEvent]]:
    """Build a fully deterministic scenario (grid, victims, blockage
    schedule) from a seed. Re-running with the same ScenarioConfig always
    produces the same world, which is what makes No-Coordination-vs-MAS
    comparison fair: both are driven against an identical world and an
    identical sequence of blockage events. Every victim exists and is known
    from t=0 -- there is no detection delay.
    """
    rng = random.Random(config.seed)
    grid, hospital, depots = _carve_grid(rng, config.width, config.height)

    road_cells = [
        (r, c)
        for r in range(config.height)
        for c in range(config.width)
        if grid[r][c] == CellType.ROAD
    ]
    rng.shuffle(road_cells)

    if config.severity_sequence is not None:
        severities = list(config.severity_sequence)
        if len(severities) < config.victim_count:
            severities += [Severity.MODERATE] * (config.victim_count - len(severities))
    else:
        all_severities = list(Severity)
        weights = [0.2, 0.3, 0.3, 0.2]  # critical, high, moderate, low
        severities = rng.choices(all_severities, weights=weights, k=config.victim_count)

    victims: list[Victim] = []
    victim_cells = road_cells[: config.victim_count]
    for i, (pos, severity) in enumerate(zip(victim_cells, severities)):
        victims.append(Victim(
            victim_id=f"V{i + 1}", position=pos, severity=severity, required_resources=1, hospital=hospital,
        ))

    # Blockage schedule: choose blockage_level fraction of remaining road
    # cells (not used by victims/reserved) to block-then-reopen at random times.
    used = {v.position for v in victims} | {hospital, *depots}
    blockable = [c for c in road_cells if c not in used]
    n_block = int(config.blockage_level * len(blockable))
    events: list[ScheduledEvent] = []
    horizon = config.blockage_horizon if config.blockage_horizon is not None else config.max_time
    for cell in blockable[:n_block]:
        block_t = rng.randint(1, max(1, int(horizon * 0.4)))
        duration = rng.randint(10, max(11, horizon // 4))
        events.append(ScheduledEvent(timestep=block_t, kind="block", payload={"cell": cell}))
        events.append(ScheduledEvent(timestep=block_t + duration, kind="unblock", payload={"cell": cell}))

    events.sort(key=lambda e: e.timestep)
    return grid, hospital, depots, victims, events


class Environment:
    """Ground-truth world state. Owns the grid, victims, resources, units,
    clock, and blockage schedule."""

    def __init__(self, config: ScenarioConfig):
        self.config = config
        grid, hospital, depots, victims, events = generate_scenario(config)
        self.grid = grid
        self.hospital = hospital
        self.depots = depots
        self.victims: dict[str, Victim] = {v.victim_id: v for v in victims}
        self.schedule = events
        self._schedule_idx = 0

        self.resources = ResourcePool(medical_kits=config.initial_resources)

        self.time = 0
        self.blocked_cells: set[Position] = set()
        self.units: dict[str, Position] = {}
        self.event_history: list[dict] = []

    # -- geometry -----------------------------------------------------
    def in_bounds(self, pos: Position) -> bool:
        r, c = pos
        return 0 <= r < self.config.height and 0 <= c < self.config.width

    def is_traversable(self, pos: Position) -> bool:
        if not self.in_bounds(pos):
            return False
        if pos in self.blocked_cells:
            return False
        return self.grid[pos[0]][pos[1]] != CellType.BUILDING

    # -- simulation clock ----------------------------------------------
    def apply_scheduled_events(self) -> list[dict]:
        """Apply every scheduled event due at the current timestep and
        return them as plain dicts, for logging."""
        applied = []
        while self._schedule_idx < len(self.schedule) and self.schedule[self._schedule_idx].timestep == self.time:
            ev = self.schedule[self._schedule_idx]
            self._schedule_idx += 1
            if ev.kind == "block":
                self.blocked_cells.add(ev.payload["cell"])
                applied.append({"type": "ROAD_BLOCKED", "payload": {"cell": ev.payload["cell"]}})
            elif ev.kind == "unblock":
                self.blocked_cells.discard(ev.payload["cell"])
                applied.append({"type": "ROAD_OPENED", "payload": {"cell": ev.payload["cell"]}})
        return applied

    def tick_waiting_times(self) -> None:
        for v in self.victims.values():
            if v.status != VictimStatus.RESCUED:
                v.waiting_time += 1

    def advance_time(self) -> None:
        self.time += 1

    def is_complete(self) -> bool:
        return all(v.status == VictimStatus.RESCUED for v in self.victims.values()) or self.time >= self.config.max_time
