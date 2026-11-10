# 实验二：搜索算法

## 1. 环境与快速运行

程序、自动化测试、性能实验均只依赖 **Python 3.8 及以上版本的标准库**，无需安装第三方包。已实际在 CPython 3.8 与 3.12 上通过测试；提交报告中的性能数据使用 CPython 3.12.14、Windows 11 测得。

解压后进入 `experiment2` 文件夹：

```bash
python main.py demo
python verify.py
python main.py experiment --repeats 51
```

- `demo` 运行所有给定样例并检查预期结果，包含 6×6 距离矩阵。
- `verify.py` 执行自动化测试，并保存测试日志、官方样例输出、验证摘要。
- `experiment` 运行完整对照实验，保存 JSON 与 CSV；预热 1 次，默认测量 51 次。
- 不需要安装依赖即可运行以上三个命令。若 Windows 的命令是 `py`，可将 `python` 改为 `py -3`。

## 2. 目录与四题入口

```text
experiment2/
  实验二报告.pdf             # 唯一报告，恰好 5 页
  README.md
  main.py                    # 命令行入口，样例与自定义输入
  search.py                  # A*、启发函数、路径与统计
  tree_search.py             # TreeNode、Minimax、Alpha-beta
  treasure.py                # 状态、距离矩阵、博弈搜索、缓存
  examples.py                # 题目原始样例与自设树
  experiments.py             # 可复现实验与计时
  verify.py                  # 测试与样例核验
  report_config.json         # GitHub 链接与个人信息（当前为空）
  data/                      # 四题 UTF-8 JSON 样例
  tests/test_algorithms.py   # 自动化测试与独立参考算法
  results/                   # 已运行的原始数据、日志、校验结果
  tools/build_report.py      # 从真实测量结果重新生成 5 页报告
  tools/package_submission.py # 校验、打包与解压后运行验证
  MANIFEST.sha256            # 压缩包内文件校验和（不含自身）
```

Python 函数接口与题面保持一致，坐标均为零起始 `(row, col)`：

```python
from search import astar_maze, astar_weighted
from tree_search import TreeNode, minimax, alpha_beta
from treasure import TreasureGame
from examples import MAZE, WEIGHTED, TREASURE

path = astar_maze(MAZE['start'], MAZE['end'], MAZE['grid'])
cost = astar_weighted(WEIGHTED['start'], WEIGHTED['end'], WEIGHTED['grid'])
root = TreeNode(children=[TreeNode(3), TreeNode(5)])
score = alpha_beta(root)
game = TreasureGame(**TREASURE)
matrix = game.matrix()
answer = game.solve(depth=4, algorithm='alphabeta').answer()
```

## 3. 四题命令、输入与预期输出

### 题一：迷宫 A*

```bash
python main.py maze
python main.py maze --input data/maze.json
python main.py maze --input data/maze.json --details
```

默认输出 Python 坐标元组列表：

```text
[(0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (1, 4), (2, 4), (3, 4)]
```

无解返回 `[]`，起终点相同返回仅含该坐标的列表。方向固定为右、下、左、上，只允许四邻接移动，不穿越 `X`；默认同 f 时优先较小 h，因此给定样例的路径与题面示例相同。

### 题二：加权 A*

```bash
python main.py weighted
python main.py weighted --input data/weighted.json --details
```

默认输出 `7`。移动代价取进入格权值；初始位置不收费，`E` 的进入代价为 **0**，普通 `S` 标记按可通行单位代价格处理（初始时仍不收费）。不可达返回 `-1`。支持数字及数字字符串，拒绝负数、非整数代价和非法网格。

终点 E 免费时采用 `h=m*max(D-1,0)`，D 为曼哈顿距离，m 为非目标可通行格的最小进入代价；若有其他零代价格则安全退化为 `h=0`。不会将普通曼哈顿距离直接用于此情形。`--heuristic zero` 用于 Dijkstra 对照；`--tie-break fifo` 固定同 f 的入队顺序。

### 题三：博弈树

```bash
python main.py tree
python main.py tree --input data/tree.json --algorithm minimax --details
python main.py tree --input data/tree.json --algorithm alphabeta --details
```

默认输出 `5`。输入支持题面的 `{"tree_structure": {...}}` 包装或直接根对象。根固定 MAX，逐层交替 MAX/MIN，严格从左到右；`is_maximizing_player` 字段仅是题面结构说明，递归角色按规则交替。支持非二叉树、负数叶值、单叶树与题面共享子树构造；非法无值叶子和循环引用报错。

### 题四：宝藏分配

```bash
python main.py treasure --depth 2
python main.py treasure --depth 4
python main.py treasure --input data/treasure.json --depth 4 --details
python main.py treasure --depth 4 --algorithm minimax --details
python main.py treasure --depth 4 --order gain --cache --details
```

预期结果：

```json
{"best_target": "T2", "best_value": -1}
{"best_target": "T3", "best_value": 3}
```

`--details` 输出全部端点标签、距离矩阵、最优首步、收益差、搜索统计和一条完整最优序列。矩阵按 `A,B,T1,T2,T3,T4` 排列：

```text
     A   B  T1  T2  T3  T4
A    0  12  10   4   8   8
B   12   0   8   8   4  10
T1  10   8   0   6   6  12
T2   4   8   6   0   6   6
T3   8   4   6   6   0   6
T4   8  10  12   6   6   0
```

题四必须按本题自己的规则：`A/B/T` 格均花费 1，不能沿用题二 E=0；经过宝藏不自动获得，已获得宝藏格可走，另一方不挡路。每次行动只取一个宝藏，更新当前位置与累计收益，A/B 交替；深度按个人行动次数计，不是双方各走一次算一层。负收益仍是合法且必须考虑的动作；H=0 或宝藏取尽时返回当前收益差。

对照顺序为 `original`、`reverse`、`gain`，作用于内部所有节点；**根层始终按编号顺序**，使并列最优目标稳定取字典序最先的目标。Gain 排序对 A、B 都按其自身收益降序；不能把 B 误排为自身收益升序。缓存保存未来增量并带 EXACT/LOWER/UPPER 标记，不将剪枝时的界误作精确值。

### 自定义输入

JSON 文件结构请直接参考 `data/`。题一、二还接受题面三个 Python 字面量的形式：

```text
(0, 0)
(0, 2)
[['S', '.', 'E']]
```

保存为 UTF-8 文本后运行 `python main.py maze --input 文件名.txt`；或 `--input -` 从标准输入读入。采用 `ast.literal_eval`，不执行输入中的代码。S/E/X 是符号，必须加引号，不能复制 PDF 中未加引号的排版示意直接当作 Python 程序。

## 4. 对照实验、统计口径与已测结果

`results/results.json` 包含环境、重复次数、全部原始测量摘要、路径累计代价、6×6 距离矩阵、逐首步精确值、最优序列和六宝藏扩展输入。四张 CSV 分别为 A*、树搜索、宝藏博弈、六宝藏缓存实验。

| 对照 | 结果 |
| --- | --- |
| 题一：h=0 FIFO / 曼哈顿 FIFO / 曼哈顿较小h | 扩展 15 / 13 / 7；都是 7 步 |
| 题二：h=0 FIFO / 修正h FIFO | 扩展 14 / 10；代价都是 7 |
| 题三：Minimax / Alpha-beta 左到右 | 访问 15 / 14；得分都是 5 |
| 题四 H=4：Minimax / AB正序 / AB逆序 / AB收益排序 | 访问 65 / 47 / 51 / 43；都是 T3，U=3 |
| 六宝藏：Minimax / Minimax缓存 / AB排序 / AB排序缓存 | 访问 1957 / 997 / 409 / 341；都是 T6，U=5 |

自设实验还包括：60×60 空地图、随机障碍地图、顺序敏感的博弈树、无路可达与零代价地形。

- A* `expanded`：非陈旧且非目标的出堆次数；`generated`：堆推入次数，包含起点及更优 g 的重复推入；`frontier_peak`：实际堆长度峰值，可能含陈旧项。
- 树 `visited` 与博弈 `visited`：递归进入次数，包含根、叶及缓存命中；博弈 `expanded`：确实展开孩子的非终止节点。
- `cutoffs`：尚有未访问兄弟时发生的提前终止次数；`pruned_children`：直接跳过的孩子数，不是跳过的整个子树节点总量。缓存界命中导致的立即返回记入缓存命中，不冒充普通兄弟剪枝。
- 时间为单次完整调用的微秒中位数，另存最小/最大值。A* 包括网格权值建表，博弈仅测 `solve()`，不含 36 次距离预计算或文件 I/O。生成全部有序距离对避免对任意地形错误假设对称。
- 60×60 障碍图打通顶行、右列以保证通路，该设计对同分策略有利；报告明确给出这一限制，不把此结果推广为所有地图均有同等收益。
- 子节点排序、缓存均不改变精确搜索的得分，但有额外成本。报告保留“节点减少而小规模计时反而增加”等实测现象，没有用编造的时间或截图代替实验分析。

## 5. 正确性测试

```bash
python verify.py
# 或只运行测试：
python -m unittest discover -s tests -v
```

已通过 **29 项测试方法**，其中单个方法还包含多组固定随机种子的子用例：

- 250 个随机迷宫，独立 BFS 校验；测试两种启发与两种同分策略。
- 250 个随机加权图，独立 Dijkstra 校验路径代价，并逐边检查修正启发函数的一致性。
- 200 棵随机不规则树，独立穷举校验两种算法与两种访问顺序。
- 40 个随机宝藏场景，H=1/2/3/4、两种算法、三种内部顺序、有/无缓存均对独立穷举校验。
- 六宝藏缓存与得分偏移校验，以及不可达、重复坐标、零代价、非法输入、循环树、共享子树、命令行和字面量输入。

`results/test_log.txt` 是真实执行日志，`verification.json` 为摘要，`official_output.json` 为给定样例的实际输出。随机场景数量和 unittest 方法数量分开记载。
