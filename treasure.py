"""A* distances + depth-limited adversarial treasure allocation."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from search import astar


@dataclass(frozen=True)
class GameState:
    pos_a: str
    pos_b: str
    remaining: Tuple[str, ...]
    score_a: int = 0
    score_b: int = 0
    player: str = "A"

    @property
    def utility(self):
        return self.score_a - self.score_b


@dataclass
class GameStats:
    visited: int = 0
    expanded: int = 0
    leaves: int = 0
    cutoffs: int = 0
    pruned_children: int = 0
    cache_hits: int = 0
    cache_entries: int = 0


@dataclass
class GameResult:
    best_target: Optional[str]
    best_value: int
    stats: GameStats

    def answer(self):
        return {"best_target": self.best_target, "best_value": self.best_value}


class TreasureGame:
    def __init__(self, grid, positions, values):
        if not values or "A" not in positions or "B" not in positions:
            raise ValueError("provide A, B and at least one treasure")
        if any(t not in positions for t in values):
            raise ValueError("each treasure needs a position")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in values.values()):
            raise ValueError("treasure values must be integers")
        self.grid = grid
        self.positions = {name: tuple(pos) for name, pos in positions.items()}
        self.values = dict(values)
        self.treasures = tuple(sorted(values))
        self.labels = ("A", "B") + self.treasures
        self.distances: Dict[Tuple[str, str], int] = {}
        self.distance_search_stats = []
        # Do not assume symmetry: entering-cell weights form a directed graph.
        for source in self.labels:
            for target in self.labels:
                result = astar(grid, self.positions[source], self.positions[target], mode="game")
                if result.cost < 0:
                    raise ValueError("all named positions must be mutually reachable")
                self.distances[source, target] = result.cost
                self.distance_search_stats.append({"source": source, "target": target,
                                                   "cost": result.cost, "expanded": result.stats.expanded})

    def matrix(self):
        return [[self.distances[a, b] for b in self.labels] for a in self.labels]

    def initial_state(self):
        return GameState("A", "B", self.treasures)

    def gain(self, source, target):
        return self.values[target] - self.distances[source, target]

    def move(self, state, target):
        if target not in state.remaining:
            raise ValueError("target already collected or unknown")
        remaining = tuple(t for t in state.remaining if t != target)
        if state.player == "A":
            return GameState(target, state.pos_b, remaining,
                             state.score_a + self.gain(state.pos_a, target), state.score_b, "B")
        if state.player == "B":
            return GameState(state.pos_a, target, remaining, state.score_a,
                             state.score_b + self.gain(state.pos_b, target), "A")
        raise ValueError("player must be A or B")

    def ordered_targets(self, state, order):
        if order == "original":
            return list(state.remaining)
        if order == "reverse":
            return list(reversed(state.remaining))
        if order == "gain":
            # Both players prefer their OWN high gains; B minimizes U=SA-SB.
            source = state.pos_a if state.player == "A" else state.pos_b
            return sorted(state.remaining, key=lambda t: (-self.gain(source, t), t))
        raise ValueError("order must be original, reverse or gain")

    def solve(self, depth=4, algorithm="alphabeta", order="original", use_cache=False, state=None):
        """Depth counts individual moves. Tied targets use lexical order.

        Transposition entries cache FUTURE utility (returned U - current U),
        not the accumulated score. Flags distinguish EXACT/LOWER/UPPER;
        a cutoff bound must never be reused as an exact minimax value.
        """
        if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
            raise ValueError("depth must be a nonnegative integer")
        if algorithm not in ("minimax", "alphabeta"):
            raise ValueError("algorithm must be minimax or alphabeta")
        if order not in ("original", "reverse", "gain"):
            raise ValueError("order must be original, reverse or gain")
        pruning = algorithm == "alphabeta"
        initial = self.initial_state() if state is None else state
        stats, table = GameStats(), {}

        def visit(current, remaining_depth, alpha, beta):
            stats.visited += 1
            if remaining_depth == 0 or not current.remaining:
                stats.leaves += 1
                return current.utility
            key = (current.pos_a, current.pos_b, current.remaining, current.player, remaining_depth)
            original_alpha, original_beta = alpha, beta
            if use_cache and key in table:
                stats.cache_hits += 1
                residual, flag = table[key]
                stored = current.utility + residual
                if flag == "EXACT":
                    return stored
                if flag == "LOWER":
                    alpha = max(alpha, stored)
                else:
                    beta = min(beta, stored)
                if pruning and alpha >= beta:
                    return stored
            stats.expanded += 1
            maximizing = current.player == "A"
            value = float("-inf") if maximizing else float("inf")
            targets = self.ordered_targets(current, order)
            for index, target in enumerate(targets):
                child_value = visit(self.move(current, target), remaining_depth - 1, alpha, beta)
                if maximizing:
                    value = max(value, child_value)
                    if pruning:
                        alpha = max(alpha, value)
                else:
                    value = min(value, child_value)
                    if pruning:
                        beta = min(beta, value)
                if pruning and alpha >= beta and index + 1 < len(targets):
                    stats.cutoffs += 1
                    stats.pruned_children += len(targets) - index - 1
                    break
            if use_cache:
                flag = "EXACT"
                if pruning and value <= original_alpha:
                    flag = "UPPER"
                elif pruning and value >= original_beta:
                    flag = "LOWER"
                table[key] = (value - current.utility, flag)
            return value

        if depth == 0 or not initial.remaining:
            value = visit(initial, depth, float("-inf"), float("inf"))
            return GameResult(None, value, stats)
        # The root is always visited and expanded once. Enumerating root moves
        # lexically gives a stable earliest target for ties under any ordering.
        stats.visited = stats.expanded = 1
        best_target, best_value = None, float("-inf") if initial.player == "A" else float("inf")
        alpha, beta = float("-inf"), float("inf")
        for target in sorted(initial.remaining):
            value = visit(self.move(initial, target), depth - 1, alpha, beta)
            better = value > best_value if initial.player == "A" else value < best_value
            if better:
                best_target, best_value = target, value
            if pruning:
                if initial.player == "A":
                    alpha = max(alpha, best_value)
                else:
                    beta = min(beta, best_value)
        stats.cache_entries = len(table)
        return GameResult(best_target, int(best_value), stats)

    def first_move_values(self, depth=4):
        """Exact values for EVERY root action, using independent full windows."""
        if depth < 1:
            raise ValueError("depth must be positive")
        state = self.initial_state()
        return {t: self.solve(depth - 1, "minimax", state=self.move(state, t)).best_value
                for t in state.remaining}

    def principal_variation(self, depth=4):
        """Recompute exact choices at each turn for an explanatory optimal line."""
        state, line = self.initial_state(), []
        for remaining_depth in range(depth, 0, -1):
            if not state.remaining:
                break
            decision = self.solve(remaining_depth, "minimax", state=state)
            source = state.pos_a if state.player == "A" else state.pos_b
            gain = self.gain(source, decision.best_target)
            before = state
            state = self.move(state, decision.best_target)
            line.append({"player": before.player, "source": source, "target": decision.best_target,
                         "distance": self.distances[source, decision.best_target], "gain": gain,
                         "score_a": state.score_a, "score_b": state.score_b, "utility": state.utility})
        return line
