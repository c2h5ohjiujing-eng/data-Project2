"""Official examples transcribed from 实验二要求_new.pdf, pp. 4, 7, 10-14."""

from tree_search import TreeNode

MAZE = {
    "start": [0, 0], "end": [3, 4],
    "grid": [
        ["S", ".", ".", "X", "."],
        [".", "X", ".", ".", "."],
        [".", "X", ".", "X", "."],
        [".", ".", ".", "X", "E"],
        ["X", "X", ".", ".", "."],
    ],
}

WEIGHTED = {
    "start": [0, 0], "end": [4, 4],
    "grid": [
        ["S", 1, 1, 8, 1],
        [1, 8, 3, 1, 1],
        [1, 8, 1, 8, 1],
        [1, 1, 1, 8, 1],
        [8, 8, 1, 1, "E"],
    ],
}

TREE = {"tree_structure": {
    "is_maximizing_player": True,
    "children": [
        {"is_maximizing_player": False, "children": [
            {"is_maximizing_player": True, "children": [{"value": 3}, {"value": 5}]},
            {"is_maximizing_player": True, "children": [{"value": 6}, {"value": 9}]},
        ]},
        {"is_maximizing_player": False, "children": [
            {"is_maximizing_player": True, "children": [{"value": 6}, {"value": 9}]},
            {"is_maximizing_player": True, "children": [{"value": 1}, {"value": 2}]},
        ]},
    ],
}}

TREASURE = {
    "grid": [
        ["A", 1, 1, "X", 2, 1, "T1"],
        [1, "X", 6, "X", 1, "X", 1],
        [1, 1, "T2", 1, 1, 1, 1],
        ["X", 1, "X", 8, "X", 1, "X"],
        [1, 1, 1, 1, "T3", 1, 1],
        [1, "X", 9, "X", 1, "X", 1],
        ["T4", 1, 1, "X", 1, 1, "B"],
    ],
    "positions": {"A": [0, 0], "B": [6, 6], "T1": [0, 6], "T2": [2, 2], "T3": [4, 4], "T4": [6, 0]},
    "values": {"T1": 9, "T2": 6, "T3": 7, "T4": 7},
}


def official_tree():
    return TreeNode.from_dict(TREE["tree_structure"])


def shared_tree():
    """Also reproduce the handout's Python construction with shared max2."""
    a = TreeNode(children=[TreeNode(3), TreeNode(5)])
    b = TreeNode(children=[TreeNode(6), TreeNode(9)])
    c = TreeNode(children=[TreeNode(1), TreeNode(2)])
    return TreeNode(children=[TreeNode(children=[a, b]), TreeNode(children=[b, c])])


def order_control_tree():
    """A self-designed depth-2 tree where reversing traversal delays bounds."""
    return TreeNode(children=[TreeNode(children=[TreeNode(v) for v in values])
                              for values in ((3,4,5),(1,2,9),(0,6,7))])
