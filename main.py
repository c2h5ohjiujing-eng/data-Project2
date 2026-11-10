"""Coursework CLI. Run `python main.py --help` for the complete interface."""

import argparse
import ast
from dataclasses import asdict
import json
from pathlib import Path
import sys

from examples import MAZE, WEIGHTED, TREE, TREASURE, official_tree
from search import astar, astar_maze, astar_weighted
from treasure import TreasureGame
from tree_search import TreeNode, alpha_beta, evaluate_tree


def parse_input(text, kind):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Accept precisely the handout's three Python literals; never eval().
        try:
            nodes = ast.parse(text, mode="exec").body
            if kind not in ("maze", "weighted") or len(nodes) != 3 or any(not isinstance(n, ast.Expr) for n in nodes):
                raise ValueError("expected JSON or exactly three literals: start, end, grid")
            start, end, grid = [ast.literal_eval(n.value) for n in nodes]
            return {"start": start, "end": end, "grid": grid}
        except (SyntaxError, TypeError, ValueError) as exc:
            raise ValueError("invalid input; quote S/E/X in literal arrays; JSON examples are in data/") from exc
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def load_input(path, kind, default):
    if path is None:
        return default
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8-sig")
    return parse_input(text, kind)


def dump(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="实验二：A*、Minimax、Alpha-beta 与宝藏分配")
    subs = parser.add_subparsers(dest="task", required=True)
    for task in ("maze", "weighted", "tree", "treasure"):
        sub = subs.add_parser(task)
        sub.add_argument("--input", help="UTF-8 JSON/literal input path; '-' reads stdin; omitted uses official sample")
        sub.add_argument("--details", action="store_true", help="include path, matrix and search statistics")
        if task in ("maze", "weighted"):
            sub.add_argument("--heuristic", choices=("auto", "zero"), default="auto")
            sub.add_argument("--tie-break", choices=("low_h", "fifo"), default="low_h")
        if task in ("tree", "treasure"):
            sub.add_argument("--algorithm", choices=("minimax", "alphabeta"), default="alphabeta")
        if task == "treasure":
            sub.add_argument("--depth", type=int, default=4)
            sub.add_argument("--order", choices=("original", "reverse", "gain"), default="original")
            sub.add_argument("--cache", action="store_true")
    subs.add_parser("demo", help="run and validate all official examples")
    experiment = subs.add_parser("experiment", help="run reproducible control experiments")
    experiment.add_argument("--repeats", type=int, default=51)
    experiment.add_argument("--output", default="results")
    args = parser.parse_args(argv)
    try:
        if args.task in ("maze", "weighted"):
            data = load_input(args.input, args.task, MAZE if args.task == "maze" else WEIGHTED)
            result = astar(data["grid"], data["start"], data["end"], mode=args.task,
                           heuristic=args.heuristic, tie_break=args.tie_break)
            if args.details:
                dump(asdict(result))
            else:
                print(result.path if args.task == "maze" else result.cost)
        elif args.task == "tree":
            data = load_input(args.input, "tree", TREE)
            root = TreeNode.from_dict(data.get("tree_structure", data))
            value, stats = evaluate_tree(root, args.algorithm == "alphabeta")
            dump({"best_value": value, "stats": asdict(stats)}) if args.details else print(value)
        elif args.task == "treasure":
            data = load_input(args.input, "treasure", TREASURE)
            game = TreasureGame(data["grid"], data["positions"], data["values"])
            result = game.solve(args.depth, args.algorithm, args.order, args.cache)
            if args.details:
                dump({**result.answer(), "labels": game.labels, "distance_matrix": game.matrix(),
                      "stats": asdict(result.stats), "optimal_line": game.principal_variation(args.depth)})
            else:
                dump(result.answer())
        elif args.task == "demo":
            path = astar_maze(MAZE["start"], MAZE["end"], MAZE["grid"])
            cost = astar_weighted(WEIGHTED["start"], WEIGHTED["end"], WEIGHTED["grid"])
            value = alpha_beta(official_tree())
            game = TreasureGame(**TREASURE)
            answers = {str(h): game.solve(h).answer() for h in (2, 4)}
            if len(path) != 8 or cost != 7 or value != 5 or answers != {
                    "2": {"best_target": "T2", "best_value": -1},
                    "4": {"best_target": "T3", "best_value": 3}}:
                raise AssertionError("official sample mismatch")
            dump({"q1_path": path, "q1_steps": len(path) - 1, "q2_cost": cost,
                  "q3_value": value, "labels": game.labels, "distance_matrix": game.matrix(),
                  "q4": answers, "official_samples_passed": True})
        elif args.task == "experiment":
            from experiments import run_experiments
            run_experiments(Path(args.output), args.repeats)
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        parser.exit(2, "Error: {}\n".format(exc))


if __name__ == "__main__":
    main()
