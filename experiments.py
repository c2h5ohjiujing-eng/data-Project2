"""Reproduce all report measurements; runtime uses the standard library only."""

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import platform
import random
from pathlib import Path
import statistics
from time import perf_counter_ns

from examples import MAZE, WEIGHTED, TREASURE, official_tree, order_control_tree
from search import astar, entry_cost
from treasure import TreasureGame
from tree_search import evaluate_tree


def measure(function, repeats):
    # One warm-up; timed work includes the whole function, including parsing
    # in-memory grid weights for A*, but excludes file I/O and game distances.
    result = function()
    samples = []
    for _ in range(repeats):
        begin = perf_counter_ns()
        result = function()
        samples.append((perf_counter_ns() - begin) / 1000)
    return result, {"median_us": round(statistics.median(samples), 3),
                    "min_us": round(min(samples), 3), "max_us": round(max(samples), 3)}


def extension_game():
    return TreasureGame([[1] * 5 for _ in range(5)],
                        {"A": (0,0), "B": (4,4), "T1": (0,4), "T2": (1,1),
                         "T3": (2,2), "T4": (4,0), "T5": (1,3), "T6": (3,1)},
                        {"T" + str(i): i+3 for i in range(1,7)})


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_experiments(output=Path("results"), repeats=51):
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261104)
    random_grid = [["X" if rng.random() < .24 else "." for _ in range(60)] for _ in range(60)]
    # Carve a guaranteed route, while retaining obstacles inside the grid.
    for c in range(60):
        random_grid[0][c] = "."
    for r in range(60):
        random_grid[r][-1] = "."
    random_grid[0][0], random_grid[-1][-1] = "S", "E"
    open_grid = [["."]*60 for _ in range(60)]
    open_grid[0][0], open_grid[-1][-1] = "S", "E"
    map_cases = [
        ("Q1_official", MAZE["grid"], MAZE["start"], MAZE["end"], "maze"),
        ("Q2_official", WEIGHTED["grid"], WEIGHTED["start"], WEIGHTED["end"], "weighted"),
        ("open60", open_grid, (0,0), (59,59), "maze"),
        ("obstacles60_seed20261104", random_grid, (0,0), (59,59), "maze"),
        ("unreachable", [["S","X","E"]], (0,0), (0,2), "maze"),
        ("zero_cost", [["S",0,"E"],[1,0,1]], (0,0), (0,2), "weighted"),
    ]
    search_rows, path_details = [], {}
    for name, grid, start, goal, mode in map_cases:
        for heuristic, tie in (("zero","fifo"),("auto","fifo"),("auto","low_h")):
            run = lambda: astar(grid, start, goal, mode, heuristic, tie)
            result, timing = measure(run, repeats)
            search_rows.append({"case":name,"heuristic":heuristic,"tie_break":tie,"cost":result.cost,
                                "path_steps":len(result.path)-1 if result.path else -1,
                                "expanded":result.stats.expanded,"generated":result.stats.generated,
                                "frontier_peak":result.stats.frontier_peak,"stale_pops":result.stats.stale_pops,
                                **timing})
        if name.startswith("Q"):
            result = astar(grid,start,goal,mode,trace=True)
            cumulative, steps = 0, []
            for index, pos in enumerate(result.path):
                entered = 0 if index == 0 else entry_cost(grid[pos[0]][pos[1]],mode)
                cumulative += entered
                steps.append({"position":pos,"entry_cost":entered,"cumulative":cumulative})
            path_details[name] = {"path":result.path,"cost":result.cost,"steps":steps,
                                  "expanded_order":result.stats.expanded_order}
    tree_rows = []
    for case, factory in (("official",official_tree),("order_control",order_control_tree)):
        for pruning in (False,True):
            for order in ("original","reverse"):
                root = factory()
                result, timing = measure(lambda: evaluate_tree(root,pruning,order),repeats)
                value, stats = result
                tree_rows.append({"case":case,"algorithm":"alphabeta" if pruning else "minimax", "order":order,
                                  "value":value, **asdict(stats), **timing})
    game = TreasureGame(**TREASURE)
    game_rows = []
    for depth in (2,4):
        for algorithm in ("minimax","alphabeta"):
            for order in ("original","reverse","gain"):
                result,timing = measure(lambda:game.solve(depth,algorithm,order),repeats)
                game_rows.append({"depth":depth,"algorithm":algorithm,"order":order,
                                  **result.answer(),**asdict(result.stats),**timing})
    extension = extension_game()
    extension_rows = []
    for algorithm in ("minimax","alphabeta"):
        for order in ("original","gain"):
            for cache in (False,True):
                result,timing = measure(lambda:extension.solve(6,algorithm,order,cache),repeats)
                extension_rows.append({"depth":6,"algorithm":algorithm,"order":order,"cache":cache,
                                       **result.answer(),**asdict(result.stats),**timing})
    results = {
        "metadata": {"python":platform.python_version(),"implementation":platform.python_implementation(),
                     "platform":platform.platform(),"processor":platform.processor(),
                     "run_utc":datetime.now(timezone.utc).isoformat(),"repeats":repeats,"warmups":1,
                     "seed":20261104,"timer":"perf_counter_ns; median microseconds",
                     "search_expanded_definition":"nonstale nongoal heap pops; goal excluded",
                     "game_visited_definition":"recursive entries including root, leaves and cache hits",
                     "game_expanded_definition":"nonterminal nodes whose children are searched",
                     "root_order":"T1..Tn fixed for stable lexical tie-breaking; order changes all interior nodes",
                     "timing_scope":"A*: complete call; game: solve only, precomputed distances excluded"},
        "search":search_rows,"paths":path_details,"tree":tree_rows,"game":game_rows,
        "distance_labels":game.labels,"distance_matrix":game.matrix(),
        "first_move_values":{str(h):game.first_move_values(h) for h in (2,4)},
        "optimal_lines":{str(h):game.principal_variation(h) for h in (2,4)},
        "distance_searches":game.distance_search_stats,
        "extension":extension_rows,
        "extension_fixture":{"grid":extension.grid,"positions":extension.positions,"values":extension.values},
    }
    # Cross-control consistency is verified before saving measurements.
    for h,target,value in ((2,"T2",-1),(4,"T3",3)):
        assert all(r["best_target"] == target and r["best_value"] == value for r in game_rows if r["depth"] == h)
    assert all(r["best_value"] == extension_rows[0]["best_value"] for r in extension_rows)
    for name, *_ in map_cases:
        assert len({r["cost"] for r in search_rows if r["case"] == name}) == 1
    (output/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    for name, rows in (("astar",search_rows),("tree",tree_rows),("treasure",game_rows),("extension",extension_rows)):
        write_csv(output/(name+".csv"),rows)
    print(json.dumps({"output":str(output.resolve()),"repeats":repeats,"controls_passed":True},ensure_ascii=False))
    return results


if __name__ == "__main__":
    run_experiments()
