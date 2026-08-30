from simulation.search.bfs import GridSpec, bfs


def make_grid(width=5, height=5, blocked=None):
    return GridSpec(width=width, height=height, blocked=set(blocked or []))


def test_bfs_finds_shortest_path_on_open_grid():
    grid = make_grid()
    result = bfs(grid, (0, 0), (4, 4))
    assert result.found
    assert result.path[0] == (0, 0)
    assert result.path[-1] == (4, 4)
    # Manhattan distance is the shortest possible on a 4-connected open grid.
    assert result.path_length == 8


def test_bfs_start_equals_goal():
    grid = make_grid()
    result = bfs(grid, (2, 2), (2, 2))
    assert result.found
    assert result.path == [(2, 2)]
    assert result.path_length == 0


def test_bfs_no_path_when_goal_is_enclosed():
    blocked = {(0, 1), (1, 0), (1, 1)}
    grid = make_grid(width=2, height=2, blocked=blocked)
    result = bfs(grid, (0, 0), (1, 1))
    assert not result.found
    assert result.path is None
    assert result.path_length == -1


def test_bfs_routes_around_a_wall():
    # Vertical wall at column 2, rows 0-3, with a gap at row 4.
    blocked = {(r, 2) for r in range(4)}
    grid = make_grid(width=5, height=5, blocked=blocked)
    result = bfs(grid, (0, 0), (0, 4))
    assert result.found
    assert all(p not in blocked for p in result.path)


def test_bfs_reports_nodes_expanded_and_runtime():
    grid = make_grid()
    result = bfs(grid, (0, 0), (4, 4))
    assert result.nodes_expanded > 0
    assert result.runtime >= 0.0


def test_bfs_unreachable_when_start_or_goal_blocked():
    grid = make_grid(blocked={(4, 4)})
    result = bfs(grid, (0, 0), (4, 4))
    assert not result.found
