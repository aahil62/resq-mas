"""Breadth-first search over the disaster grid.

BFS is used (rather than DFS/IDS/A*/etc.) because the grid has uniform
per-step movement cost, so the first path BFS finds to a goal is already a
shortest path. This module answers a single, narrow question: "how does an
agent get from A to B on the current known grid?" It has no knowledge of
victim priority, resource cost, or which agent should go where -- that
decision is made by the coordination layer (see coordination/task_allocation.py).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

Position = tuple[int, int]

_NEIGHBOR_DELTAS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


@dataclass
class BFSResult:
    path: list[Position] | None
    path_length: int
    nodes_expanded: int
    runtime: float

    @property
    def found(self) -> bool:
        return self.path is not None


@dataclass
class GridSpec:
    """Minimal read-only view BFS needs: which cells are traversable."""

    width: int
    height: int
    blocked: set[Position] = field(default_factory=set)

    def in_bounds(self, pos: Position) -> bool:
        r, c = pos
        return 0 <= r < self.height and 0 <= c < self.width

    def is_traversable(self, pos: Position) -> bool:
        return self.in_bounds(pos) and pos not in self.blocked


def bfs(grid: GridSpec, start: Position, goal: Position) -> BFSResult:
    """Shortest-path search on a 4-connected grid.

    Returns a BFSResult with the path (inclusive of start and goal), its
    length in steps (edges, i.e. len(path) - 1), the number of nodes
    expanded (dequeued), and wall-clock runtime in seconds.
    """
    t0 = time.perf_counter()

    if start == goal:
        return BFSResult(path=[start], path_length=0, nodes_expanded=0,
                          runtime=time.perf_counter() - t0)

    if not grid.is_traversable(start) or not grid.is_traversable(goal):
        return BFSResult(path=None, path_length=-1, nodes_expanded=0,
                          runtime=time.perf_counter() - t0)

    visited = {start}
    parent: dict[Position, Position] = {}
    queue: deque[Position] = deque([start])
    nodes_expanded = 0

    while queue:
        current = queue.popleft()
        nodes_expanded += 1

        if current == goal:
            path = _reconstruct(parent, start, goal)
            return BFSResult(path=path, path_length=len(path) - 1,
                              nodes_expanded=nodes_expanded,
                              runtime=time.perf_counter() - t0)

        cr, cc = current
        for dr, dc in _NEIGHBOR_DELTAS:
            nxt = (cr + dr, cc + dc)
            if nxt in visited or not grid.is_traversable(nxt):
                continue
            visited.add(nxt)
            parent[nxt] = current
            queue.append(nxt)

    return BFSResult(path=None, path_length=-1, nodes_expanded=nodes_expanded,
                      runtime=time.perf_counter() - t0)


def _reconstruct(parent: dict[Position, Position], start: Position, goal: Position) -> list[Position]:
    path = [goal]
    node = goal
    while node != start:
        node = parent[node]
        path.append(node)
    path.reverse()
    return path
