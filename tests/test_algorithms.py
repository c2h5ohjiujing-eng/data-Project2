"""Correctness tests with independent BFS/Dijkstra/exhaustive oracles."""

from collections import deque
from copy import deepcopy
from heapq import heappop, heappush
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

from examples import MAZE, WEIGHTED, TREASURE, official_tree, shared_tree, order_control_tree
from main import parse_input
from search import admissible_heuristic, astar, astar_maze, astar_weighted, entry_cost, manhattan
from treasure import GameState, TreasureGame
from tree_search import TreeNode, alpha_beta, evaluate_tree, minimax


def reference_distance(grid, start, goal, mode):
    """Independent Dijkstra: no heuristic, no production A* calls."""
    rows, cols = len(grid), len(grid[0])
    queue, distance = [(0, start)], {start: 0}
    while queue:
        cost, p = heappop(queue)
        if cost != distance[p]:
            continue
        if p == goal:
            return cost
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            r, c = p[0] + dr, p[1] + dc
            if not (0 <= r < rows and 0 <= c < cols) or grid[r][c] == "X":
                continue
            cell = grid[r][c]
            if mode == "maze":
                weight = 1
            elif cell == "E" and mode == "weighted":
                weight = 0
            elif isinstance(cell, str) and (cell in ("S", "E", "A", "B", ".") or cell.startswith("T")):
                weight = 1
            else:
                weight = int(cell)
            q = (r, c)
            alt = cost + weight
            if alt < distance.get(q, float("inf")):
                distance[q] = alt
                heappush(queue, (alt, q))
    return -1


def reference_game(game, depth, state=None):
    """Independent exhaustive recursion: no production move/search method."""
    if state is None:
        state = ("A", "B", tuple(sorted(game.values)), 0, 0, "A")
    pa, pb, remaining, sa, sb, player = state
    if not remaining or depth == 0:
        return None, sa - sb
    choices = []
    for target in sorted(remaining):
        rest = tuple(t for t in remaining if t != target)
        if player == "A":
            child = (target, pb, rest, sa + game.values[target] - game.distances[pa, target], sb, "B")
        else:
            child = (pa, target, rest, sa, sb + game.values[target] - game.distances[pb, target], "A")
        choices.append((target, reference_game(game, depth - 1, child)[1]))
    best = (max if player == "A" else min)(v for _, v in choices)
    return next(t for t, v in choices if v == best), best


def validate_path(test, grid, path, start, goal, expected_cost, mode):
    if expected_cost < 0:
        test.assertEqual(path, [])
        return
    test.assertEqual(path[0], start)
    test.assertEqual(path[-1], goal)
    test.assertTrue(all(manhattan(a, b) == 1 for a, b in zip(path, path[1:])))
    test.assertTrue(all(grid[r][c] != "X" for r, c in path))
    test.assertEqual(sum(entry_cost(grid[r][c], mode) for r, c in path[1:]), expected_cost)


class AStarTests(unittest.TestCase):
    def test_official_maze(self):
        path = astar_maze(MAZE["start"], MAZE["end"], MAZE["grid"])
        self.assertEqual(path, [(0,0), (0,1), (0,2), (1,2), (1,3), (1,4), (2,4), (3,4)])

    def test_official_weighted(self):
        self.assertEqual(astar_weighted(WEIGHTED["start"], WEIGHTED["end"], WEIGHTED["grid"]), 7)

    def test_unreachable(self):
        grid = [["S", "X", "E"]]
        self.assertEqual(astar_maze((0,0), (0,2), grid), [])
        self.assertEqual(astar_weighted((0,0), (0,2), grid), -1)

    def test_same_start_and_goal(self):
        self.assertEqual(astar_maze((0,0), (0,0), [["S"]]), [(0,0)])
        self.assertEqual(astar_weighted((0,0), (0,0), [["S"]]), 0)

    def test_blocked_endpoint(self):
        self.assertEqual(astar([["X", "E"]], (0,0), (0,1)).path, [])

    def test_free_final_step(self):
        r = astar([["S", "E"]], (0,0), (0,1), mode="weighted")
        self.assertEqual(r.cost, 0)
        costs = {(0,0): 1, (0,1): 0}
        self.assertEqual(admissible_heuristic(costs, (0,1), (0,0)), 0)

    def test_zero_cost_fallback(self):
        grid = [["S", 0, "E"], [1, 0, 1]]
        self.assertEqual(astar_weighted((0,0), (0,2), grid), 0)

    def test_weighted_detour(self):
        grid = [["S", 99, "E"], [1, 1, 1]]
        self.assertEqual(astar_weighted((0,0), (0,2), grid), 3)

    def test_invalid_grids_and_costs(self):
        for grid in ([], [[]], [["S"], ["E", 1]], [["S", -2]], [["S", True]], [["S", 1.5]]):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                astar(grid, (0,0), (0,0), mode="weighted")
        with self.assertRaises(ValueError):
            astar([["S"]], (-1,0), (0,0))

    def test_input_immutable(self):
        before = deepcopy(WEIGHTED)
        astar_weighted(before["start"], before["end"], before["grid"])
        self.assertEqual(before, WEIGHTED)

    def test_random_mazes_against_bfs(self):
        rng = random.Random(20261104)
        for index in range(250):
            rows, cols = rng.randint(2,10), rng.randint(2,10)
            grid = [["X" if rng.random() < .28 else "." for _ in range(cols)] for _ in range(rows)]
            start, goal = (0,0), (rows-1,cols-1)
            grid[0][0], grid[-1][-1] = "S", "E"
            q, visited, expected = deque([(start,0)]), {start}, -1
            while q:
                p, depth = q.popleft()
                if p == goal:
                    expected = depth
                    break
                for dr, dc in ((0,1),(1,0),(0,-1),(-1,0)):
                    n = p[0]+dr, p[1]+dc
                    if 0 <= n[0] < rows and 0 <= n[1] < cols and n not in visited and grid[n[0]][n[1]] != "X":
                        visited.add(n)
                        q.append((n,depth+1))
            for heuristic in ("zero", "auto"):
                for tie in ("fifo", "low_h"):
                    with self.subTest(index=index, heuristic=heuristic, tie=tie):
                        result = astar(grid, start, goal, heuristic=heuristic, tie_break=tie)
                        self.assertEqual(result.cost, expected)
                        validate_path(self, grid, result.path, start, goal, expected, "maze")

    def test_random_weighted_against_dijkstra_and_consistency(self):
        rng = random.Random(4011)
        for index in range(250):
            rows, cols = rng.randint(2,9), rng.randint(2,9)
            grid = [["X" if rng.random() < .18 else rng.choice([0,1,1,2,3,8]) for _ in range(cols)] for _ in range(rows)]
            grid[0][0], grid[-1][-1] = "S", "E"
            start, goal = (0,0), (rows-1,cols-1)
            expected = reference_distance(grid, start, goal, "weighted")
            result = astar(grid, start, goal, mode="weighted")
            with self.subTest(index=index):
                self.assertEqual(result.cost, expected)
                validate_path(self, grid, result.path, start, goal, expected, "weighted")
                costs = {(r,c): entry_cost(grid[r][c], "weighted") for r in range(rows) for c in range(cols)}
                for p, weight in costs.items():
                    if weight is None:
                        continue
                    hp = admissible_heuristic(costs, goal, p)
                    for dr, dc in ((0,1),(1,0),(0,-1),(-1,0)):
                        n = p[0]+dr, p[1]+dc
                        if costs.get(n) is not None:
                            self.assertLessEqual(hp, costs[n] + admissible_heuristic(costs, goal, n))


class TreeTests(unittest.TestCase):
    def test_official_and_shared_tree(self):
        for tree in (official_tree(), shared_tree()):
            self.assertEqual(minimax(tree), 5)
            self.assertEqual(alpha_beta(tree), 5)

    def test_exact_left_to_right_counts(self):
        _, mm = evaluate_tree(official_tree(), False)
        _, ab = evaluate_tree(official_tree(), True)
        self.assertEqual(mm.visited, 15)
        self.assertEqual(mm.leaves, 8)
        self.assertLess(ab.visited, mm.visited)
        self.assertEqual(ab.leaves, 7)

    def test_negative_single_and_irregular(self):
        self.assertEqual(alpha_beta(TreeNode(-7)), -7)
        root = TreeNode(children=[TreeNode(-2), TreeNode(children=[TreeNode(-9),TreeNode(-5),TreeNode(4)])])
        self.assertEqual(alpha_beta(root), minimax(root))

    def test_designed_order_control(self):
        left, left_stats = evaluate_tree(order_control_tree(),True,"original")
        right, right_stats = evaluate_tree(order_control_tree(),True,"reverse")
        self.assertEqual(left,3)
        self.assertEqual(right,3)
        self.assertLess(left_stats.visited,right_stats.visited)

    def test_invalid_leaf_and_cycle(self):
        with self.assertRaises(ValueError):
            alpha_beta(TreeNode())
        root = TreeNode(children=[])
        root.children.append(root)
        with self.assertRaises(ValueError):
            alpha_beta(root)

    def test_random_trees(self):
        rng = random.Random(993)
        def build(depth):
            if depth == 0 or rng.random() < .20:
                return TreeNode(rng.randint(-30,30))
            return TreeNode(children=[build(depth-1) for _ in range(rng.randint(1,4))])
        def oracle(node, maximizing=True):
            if not node.children:
                return node.value
            return (max if maximizing else min)(oracle(child, not maximizing) for child in node.children)
        for index in range(200):
            root = build(5)
            expected = oracle(root)
            for order in ("original", "reverse"):
                for pruning in (False, True):
                    with self.subTest(index=index, order=order, pruning=pruning):
                        self.assertEqual(evaluate_tree(root, pruning, order)[0], expected)


class TreasureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = TreasureGame(**TREASURE)

    def test_distance_matrix_against_independent_dijkstra(self):
        for a in self.game.labels:
            for b in self.game.labels:
                with self.subTest(a=a,b=b):
                    self.assertEqual(self.game.distances[a,b], reference_distance(TREASURE["grid"], tuple(TREASURE["positions"][a]), tuple(TREASURE["positions"][b]), "game"))

    def test_official_results_all_variants(self):
        for h, target, value in ((2,"T2",-1),(4,"T3",3)):
            for alg in ("minimax","alphabeta"):
                for order in ("original","reverse","gain"):
                    for cache in (False,True):
                        with self.subTest(h=h,alg=alg,order=order,cache=cache):
                            result = self.game.solve(h,alg,order,cache)
                            self.assertEqual((result.best_target,result.best_value),(target,value))

    def test_move_scores_positions_and_no_auto_collect(self):
        before = self.game.initial_state()
        after = self.game.move(before, "T1")
        self.assertEqual(after.pos_a, "T1")
        self.assertEqual(after.pos_b, "B")
        self.assertEqual(after.score_a, self.game.values["T1"]-self.game.distances["A","T1"])
        self.assertEqual(after.remaining, ("T2","T3","T4"))
        self.assertEqual(before.remaining, ("T1","T2","T3","T4"))
        self.assertEqual(after.player, "B")

    def test_depth_zero_and_excess_depth(self):
        result = self.game.solve(0)
        self.assertIsNone(result.best_target)
        self.assertEqual(result.best_value, 0)
        self.assertEqual(self.game.solve(20).answer(),self.game.solve(4).answer())
        with self.assertRaises(ValueError):
            self.game.solve(-1)

    def test_optimal_line(self):
        line = self.game.principal_variation(4)
        self.assertEqual(len(line),4)
        self.assertEqual(line[-1]["utility"],3)
        self.assertEqual(len({step["target"] for step in line}),4)

    def test_all_variants_random_games_against_exhaustive_oracle(self):
        rng = random.Random(7004)
        for index in range(40):
            grid = [[rng.randint(1,5) for _ in range(4)] for _ in range(4)]
            positions = {"A":(0,0), "B":(3,3), "T1":(0,3), "T2":(1,1), "T3":(2,2), "T4":(3,0)}
            values = {"T"+str(i):rng.randint(-5,14) for i in range(1,5)}
            game = TreasureGame(grid, positions, values)
            for h in (1,2,3,4):
                expected = reference_game(game,h)
                for alg in ("minimax","alphabeta"):
                    for order in ("original","reverse","gain"):
                        for cache in (False,True):
                            with self.subTest(index=index,h=h,alg=alg,order=order,cache=cache):
                                result = game.solve(h,alg,order,cache)
                                self.assertEqual((result.best_target,result.best_value),expected)

    def test_six_treasures_transposition_bounds_and_offset(self):
        grid = [[1]*5 for _ in range(5)]
        positions = {"A":(0,0),"B":(4,4),"T1":(0,4),"T2":(1,1),"T3":(2,2),"T4":(4,0),"T5":(1,3),"T6":(3,1)}
        game = TreasureGame(grid, positions, {"T"+str(i):i+3 for i in range(1,7)})
        expected = reference_game(game,6)
        for order in ("original","reverse","gain"):
            for alg in ("minimax","alphabeta"):
                result = game.solve(6,alg,order,True)
                self.assertEqual((result.best_target,result.best_value),expected)
        self.assertGreater(game.solve(6,"minimax",use_cache=True).stats.cache_hits,0)
        offset = GameState("A","B",game.treasures,17,-4,"A")
        self.assertEqual(game.solve(6,state=offset,use_cache=True).best_value,expected[1]+21)

    def test_unreachable_named_position_rejected(self):
        with self.assertRaises(ValueError):
            TreasureGame([["A","X","T1"],[1,"X","B"]],{"A":(0,0),"B":(1,2),"T1":(0,2)},{"T1":5})


class InputTests(unittest.TestCase):
    def test_literal_input_and_json(self):
        data = parse_input("(0,0)\n(0,2)\n[['S', '.', 'E']]", "maze")
        self.assertEqual(astar_maze(data["start"],data["end"],data["grid"]),[(0,0),(0,1),(0,2)])
        self.assertEqual(parse_input(json.dumps(MAZE),"maze"),MAZE)

    def test_no_eval_execution(self):
        with self.assertRaises(ValueError):
            parse_input("__import__('os').system('echo unsafe')\n(0,0)\n[['S']]", "maze")

    def test_cli_demo_and_custom_input(self):
        root = Path(__file__).resolve().parents[1]
        process = subprocess.run([sys.executable,"main.py","demo"],cwd=str(root),capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertTrue(json.loads(process.stdout)["official_samples_passed"])
        process = subprocess.run([sys.executable,"main.py","weighted","--input","-"],cwd=str(root),
                                 input=json.dumps({"start":[0,0],"end":[0,1],"grid":[["S","E"]]}),capture_output=True,text=True)
        self.assertEqual(process.stdout.strip(),"0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
