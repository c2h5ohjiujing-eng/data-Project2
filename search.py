"""Four-directional A* with explicit, reproducible search statistics.

Runtime dependency: Python standard library, Python 3.8 or newer.
"""

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from numbers import Integral
from typing import Dict, List, Optional, Sequence, Tuple

Position = Tuple[int, int]
# A fixed direction order makes tied shortest paths reproducible.
DIRECTIONS = ((0, 1), (1, 0), (0, -1), (-1, 0))


@dataclass
class SearchStats:
    popped: int = 0
    expanded: int = 0
    generated: int = 0
    relaxed: int = 0
    stale_pops: int = 0
    frontier_peak: int = 0
    expanded_order: List[Position] = field(default_factory=list)


@dataclass
class PathResult:
    path: List[Position]
    cost: int
    stats: SearchStats


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _shape(grid: Sequence[Sequence]) -> Tuple[int, int]:
    if not grid or not grid[0]:
        raise ValueError("grid must be a nonempty rectangular array")
    rows, cols = len(grid), len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("grid must be rectangular")
    return rows, cols


def _position(pos: Sequence[int], rows: int, cols: int) -> Position:
    if len(pos) != 2 or any(isinstance(x, bool) or not isinstance(x, Integral) for x in pos):
        raise ValueError("coordinates must contain two integers")
    r, c = int(pos[0]), int(pos[1])
    if not (0 <= r < rows and 0 <= c < cols):
        raise ValueError("coordinates out of bounds")
    return r, c


def entry_cost(cell, mode: str) -> Optional[int]:
    """None means blocked. Q2's E costs zero; game treasure cells cost one."""
    if cell == "X":
        return None
    if mode == "maze":
        if cell not in ("S", "E", "."):
            raise ValueError("maze cells must be S, E, . or X")
        return 1
    if mode not in ("weighted", "game"):
        raise ValueError("mode must be maze, weighted or game")
    if cell in ("S", "E", "A", "B", "."):
        return 0 if mode == "weighted" and cell == "E" else 1
    if isinstance(cell, str) and cell.startswith("T") and cell[1:].isdigit():
        return 1
    if isinstance(cell, bool):
        raise ValueError("boolean terrain costs are not supported")
    if isinstance(cell, Integral):
        value = int(cell)
    elif isinstance(cell, str) and cell.isdecimal():
        value = int(cell)
    else:
        raise ValueError("terrain costs must be nonnegative integers or valid markers")
    if value < 0:
        raise ValueError("negative terrain costs are not supported by A*")
    return value


def admissible_heuristic(costs, goal: Position, pos: Position) -> int:
    """A consistent lower bound, including a free final step if goal costs 0.

    Every nonterminal edge costs at least m. When E=0, at least D-1
    such edges are needed, so h=m*max(D-1,0), rather than plain D.
    Zero-cost nonterminal cells cause m=0 (a safe Dijkstra fallback).
    """
    others = [v for p, v in costs.items() if p != goal and v is not None]
    minimum = min(others, default=0)
    distance = manhattan(pos, goal)
    if costs[goal] == 0:
        return minimum * max(distance - 1, 0)
    return min(minimum, costs[goal]) * distance


def astar(grid, start, goal, mode="maze", heuristic="auto", tie_break="low_h", trace=False) -> PathResult:
    """Return an optimal path/cost; unreachable -> []/-1.

    Equal f: low_h prefers smaller h, fifo prefers insertion order. The
    goal is tested only after a nonstale heap pop. Improved g can reopen
    nodes, so a permanent closed set cannot suppress a better path.
    """
    rows, cols = _shape(grid)
    start, goal = _position(start, rows, cols), _position(goal, rows, cols)
    costs = {(r, c): entry_cost(grid[r][c], mode) for r in range(rows) for c in range(cols)}
    stats = SearchStats()
    if costs[start] is None or costs[goal] is None:
        return PathResult([], -1, stats)
    if heuristic not in ("auto", "zero", "manhattan"):
        raise ValueError("heuristic must be auto, zero or manhattan")
    if heuristic == "manhattan" and mode != "maze":
        raise ValueError("plain Manhattan is only exposed for unit-cost mazes; use auto for weighted terrain")
    if tie_break not in ("low_h", "fifo"):
        raise ValueError("tie_break must be low_h or fifo")

    other_costs = [v for p, v in costs.items() if p != goal and v is not None]
    minimum = min(other_costs, default=0)
    free_goal = costs[goal] == 0
    scale = minimum if free_goal else min(minimum, costs[goal])

    def h(pos):
        if heuristic == "zero":
            return 0
        d = manhattan(pos, goal)
        return scale * (max(d - 1, 0) if free_goal else d)

    serial = count()
    start_h = h(start)
    queue = [(start_h, start_h if tie_break == "low_h" else 0, next(serial), 0, start)]
    best_g: Dict[Position, int] = {start: 0}
    parent: Dict[Position, Position] = {}
    stats.generated = stats.frontier_peak = 1
    while queue:
        _, _, _, g, current = heappop(queue)
        stats.popped += 1
        if g != best_g.get(current):
            stats.stale_pops += 1
            continue
        if current == goal:
            path = [current]
            while current != start:
                current = parent[current]
                path.append(current)
            path.reverse()
            return PathResult(path, g, stats)
        stats.expanded += 1
        if trace:
            stats.expanded_order.append(current)
        for dr, dc in DIRECTIONS:
            neighbor = (current[0] + dr, current[1] + dc)
            weight = costs.get(neighbor)
            if weight is None:
                continue
            candidate = g + weight
            if candidate < best_g.get(neighbor, float("inf")):
                best_g[neighbor] = candidate
                parent[neighbor] = current
                hn = h(neighbor)
                heappush(queue, (candidate + hn, hn if tie_break == "low_h" else 0,
                                 next(serial), candidate, neighbor))
                stats.generated += 1
                stats.relaxed += 1
        stats.frontier_peak = max(stats.frontier_peak, len(queue))
    return PathResult([], -1, stats)


def astar_maze(start, end, grid):
    """Q1's required public interface: List[Tuple[int,int]]."""
    return astar(grid, start, end, mode="maze").path


def astar_weighted(start, end, grid):
    """Q2's required public interface: int, or -1 if unreachable."""
    return astar(grid, start, end, mode="weighted").cost
