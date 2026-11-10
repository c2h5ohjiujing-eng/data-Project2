"""Left-to-right Minimax and Alpha-beta; no implicit move reordering."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real


class TreeNode:
    def __init__(self, value=None, children=None):
        self.value = value
        self.children = children if children is not None else []

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("each tree node must be a JSON object")
        children = data.get("children", [])
        if not isinstance(children, list):
            raise ValueError("children must be a list")
        return cls(data.get("value"), [cls.from_dict(child) for child in children])


@dataclass
class TreeStats:
    visited: int = 0
    leaves: int = 0
    cutoffs: int = 0
    pruned_children: int = 0


def _leaf_value(node):
    if isinstance(node.value, bool) or not isinstance(node.value, Real) or not isfinite(node.value):
        raise ValueError("a leaf must have a finite numeric value")
    return node.value


def evaluate_tree(root, pruning=True, order="original"):
    """Return (best_value, stats); root is MAX, children alternate roles.

    original is the required left-to-right traversal. reverse is an
    experimental control only. No cache: shared child objects are visited
    at each tree occurrence, matching the handout's shared max2 example.
    """
    if order not in ("original", "reverse"):
        raise ValueError("order must be original or reverse")
    stats = TreeStats()
    active = set()

    def visit(node, maximizing, alpha, beta):
        if id(node) in active:
            raise ValueError("cyclic graph is not a game tree")
        stats.visited += 1
        if not node.children:
            stats.leaves += 1
            return _leaf_value(node)
        active.add(id(node))
        try:
            children = node.children if order == "original" else list(reversed(node.children))
            value = float("-inf") if maximizing else float("inf")
            for index, child in enumerate(children):
                child_value = visit(child, not maximizing, alpha, beta)
                if maximizing:
                    value = max(value, child_value)
                    alpha = max(alpha, value)
                else:
                    value = min(value, child_value)
                    beta = min(beta, value)
                if pruning and alpha >= beta and index + 1 < len(children):
                    stats.cutoffs += 1
                    stats.pruned_children += len(children) - index - 1
                    break
            return value
        finally:
            active.remove(id(node))

    return visit(root, True, float("-inf"), float("inf")), stats


def minimax(root):
    return evaluate_tree(root, pruning=False)[0]


def alpha_beta(root):
    """Q3's required public interface: the optimal numeric value for MAX."""
    return evaluate_tree(root, pruning=True, order="original")[0]
