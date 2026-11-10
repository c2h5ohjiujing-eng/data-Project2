"""Build the five-page report from saved, real experiment results.

Optional authoring dependencies: pip install -r tools/requirements-report.txt
The submitted algorithms/tests require none of these packages.
"""

import argparse
import hashlib
from html import escape
import json
import os
from pathlib import Path

from pypdf import PdfReader
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                               Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#183744")
TEAL = colors.HexColor("#177E89")
GRAY = colors.HexColor("#60717B")
LIGHT = colors.HexColor("#F0F5F6")
ORANGE = colors.HexColor("#C78035")
WIDTH = A4[0] - 84


def register_fonts(user_font=None):
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    candidates = [Path(user_font)] if user_font else [
        windir/"Fonts/simsun.ttc", windir/"Fonts/simhei.ttf",
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
    ]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        raise SystemExit("A Chinese TrueType font is required. Pass --font /path/to/font.ttf")
    pdfmetrics.registerFont(TTFont("BodyCN",str(found),subfontIndex=0))
    heading = windir/"Fonts/simhei.ttf"
    pdfmetrics.registerFont(TTFont("HeadCN",str(heading if heading.exists() else found),subfontIndex=0))
    pdfmetrics.registerFontFamily("BodyCN",normal="BodyCN",bold="HeadCN",italic="BodyCN",boldItalic="HeadCN")


def styles():
    return {
        "title":ParagraphStyle("title",fontName="HeadCN",fontSize=19,leading=25,textColor=INK,spaceAfter=10),
        "h1":ParagraphStyle("h1",fontName="HeadCN",fontSize=12,leading=17,textColor=TEAL,spaceBefore=10,spaceAfter=6,keepWithNext=True),
        "body":ParagraphStyle("body",fontName="BodyCN",fontSize=10.3,leading=15.7,textColor=INK,spaceAfter=6,wordWrap="CJK"),
        "small":ParagraphStyle("small",fontName="BodyCN",fontSize=9,leading=13.5,textColor=GRAY,spaceAfter=5,wordWrap="CJK"),
        "cell":ParagraphStyle("cell",fontName="BodyCN",fontSize=9.2,leading=13,textColor=INK,wordWrap="CJK"),
        "header":ParagraphStyle("header",fontName="HeadCN",fontSize=9.2,leading=13,textColor=colors.white,wordWrap="CJK"),
        "caption":ParagraphStyle("caption",fontName="BodyCN",fontSize=9,leading=13,textColor=GRAY,alignment=TA_CENTER,spaceAfter=7,wordWrap="CJK"),
        "code":ParagraphStyle("code",fontName="Courier",fontSize=8.6,leading=12,textColor=INK,spaceAfter=6),
    }


def table(rows, widths=None, highlight=None):
    cells = []
    for i, row in enumerate(rows):
        cells.append([Paragraph(escape(str(v)), ST["header" if i == 0 else "cell"]) for v in row])
    t = Table(cells,colWidths=widths or [WIDTH/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign="LEFT")
    commands = [
        ("BACKGROUND",(0,0),(-1,0),TEAL),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LINEBELOW",(0,0),(-1,0),.5,TEAL),
    ]
    for i in range(1,len(rows)):
        if i % 2:
            commands.append(("BACKGROUND",(0,i),(-1,i),LIGHT))
        commands.append(("LINEBELOW",(0,i),(-1,i),.3,colors.HexColor("#D5E0E3")))
    if highlight:
        for row in highlight:
            commands.append(("BACKGROUND",(0,row),(-1,row),colors.HexColor("#E1F1EC")))
    t.setStyle(TableStyle(commands))
    return t


def p(text, kind="body"):
    return Paragraph(text,ST[kind])


def grid_figure(grid, path):
    d = Drawing(WIDTH,150)
    x0,y0,size = 25,11,25
    pathset = {tuple(x) for x in path}
    for r,row in enumerate(grid):
        for c,cell in enumerate(row):
            x,y = x0+c*size,y0+(4-r)*size
            fill = colors.HexColor("#D9EDE7") if (r,c) in pathset else colors.white
            if cell == "X":
                fill = colors.HexColor("#C3CDD1")
            d.add(Rect(x,y,size,size,fillColor=fill,strokeColor=colors.HexColor("#C6D4D9"),strokeWidth=.55))
            if cell in ("S","E","X"):
                d.add(String(x+size/2,y+9,str(cell),fontName="Helvetica-Bold",fontSize=10,textAnchor="middle",fillColor=INK))
    for a,b in zip(path,path[1:]):
        ax,ay = x0+(a[1]+.5)*size,y0+(4-a[0]+.5)*size
        bx,by = x0+(b[1]+.5)*size,y0+(4-b[0]+.5)*size
        vx,vy = bx-ax,by-ay
        begin=.24 if grid[a[0]][a[1]] in ("S","E") else 0
        end=.74 if grid[b[0]][b[1]] in ("S","E") else 1
        d.add(Line(ax+vx*begin,ay+vy*begin,ax+vx*end,ay+vy*end,strokeColor=TEAL,strokeWidth=2))
    for k in range(5):
        d.add(String(x0+(k+.5)*size,139,str(k),fontName="Helvetica",fontSize=8,textAnchor="middle",fillColor=GRAY))
        d.add(String(13,y0+(4-k)*size+9,str(k),fontName="Helvetica",fontSize=8,textAnchor="middle",fillColor=GRAY))
    lines = ["绿色连线为返回路径，灰色为障碍。", "(0,0) → (0,1) → (0,2) → (1,2)",
             "→ (1,3) → (1,4) → (2,4) → (3,4)", "7 次移动；路径包含起点和终点，共 8 个坐标。",
             "所有路径边均为四邻接，且未穿越 X。"]
    for i,text in enumerate(lines):
        d.add(String(175,119-i*23,text,fontName="BodyCN",fontSize=9.3,fillColor=INK))
    return d


def action_chart(values):
    d = Drawing(WIDTH,155)
    left,right,bottom,top = 50,WIDTH-30,25,133
    lo,hi=-8,4
    def x(v): return left+(v-lo)/(hi-lo)*(right-left)
    for tick in range(-8,5,2):
        d.add(Line(x(tick),bottom,x(tick),top,strokeColor=colors.HexColor("#D7E0E3"),strokeWidth=.5))
        d.add(String(x(tick),10,str(tick),fontName="Helvetica",fontSize=8,textAnchor="middle",fillColor=GRAY))
    d.add(Line(x(0),bottom,x(0),top,strokeColor=GRAY,strokeWidth=.8))
    for i,target in enumerate(("T1","T2","T3","T4")):
        y=top-14-i*26
        d.add(String(12,y-1,target,fontName="Helvetica-Bold",fontSize=10,fillColor=INK))
        for depth,shift,color in (("2",5,ORANGE),("4",-5,TEAL)):
            value=values[depth][target]
            d.add(Rect(min(x(0),x(value)),y+shift-4,abs(x(value)-x(0)),7,fillColor=color,strokeColor=None))
            d.add(String(x(value)+(-5 if value<0 else 5),y+shift-3,str(value),fontName="Helvetica",fontSize=8,
                         textAnchor="end" if value<0 else "start",fillColor=color))
    d.add(Rect(155,143,9,6,fillColor=ORANGE,strokeColor=None))
    d.add(String(169,141,"H=2",fontName="Helvetica",fontSize=8.5,fillColor=INK))
    d.add(Rect(225,143,9,6,fillColor=TEAL,strokeColor=None))
    d.add(String(239,141,"H=4",fontName="Helvetica",fontSize=8.5,fillColor=INK))
    return d


def footer(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CCDBDF"))
    canvas.line(42,36,A4[0]-42,36)
    canvas.setFont("BodyCN",8)
    canvas.setFillColor(GRAY)
    canvas.drawString(42,23,"实验二 / 搜索算法 / 2026-11-04")
    canvas.drawRightString(A4[0]-42,23,"{} / 5".format(doc.page))
    canvas.restoreState()


def build_report(output, font=None):
    global ST
    register_fonts(font)
    ST=styles()
    d=json.loads((ROOT/"results/results.json").read_text(encoding="utf-8"))
    v=json.loads((ROOT/"results/verification.json").read_text(encoding="utf-8"))
    config=json.loads((ROOT/"report_config.json").read_text(encoding="utf-8"))
    if not v["passed"]:
        raise SystemExit("Run python verify.py successfully before building the report")
    def search_rows(case): return [r for r in d["search"] if r["case"]==case]
    def game_row(h,alg,order): return next(r for r in d["game"] if r["depth"]==h and r["algorithm"]==alg and r["order"]==order)
    story=[]
    add=story.append
    # PAGE 1 --------------------------------------------------------------
    add(p("GitHub 仓库链接："+escape(config["github_url"] or "______________________________")))
    add(p("当代人工智能实验二：搜索算法","title"))
    add(p("姓名：{}　　学号：{}".format(escape(config["student_name"] or "__________"),escape(config["student_id"] or "________________")),"small"))
    add(p("1　目标、实现与实验设置","h1"))
    add(p("完成迷宫寻路、加权地形、极大极小博弈树和竞争宝藏分配四题；在给定样例正确的基础上，比较启发函数、访问顺序、搜索深度和缓存的影响。代码使用 Python 标准库，题目一、二、三分别返回坐标列表、整数代价和最优得分；题目四输出距离矩阵与决策。"))
    add(p("A* 将坐标作为状态，g 为已付代价，h 为剩余代价下界，f=g+h。最小堆保存 (f, tie, serial, g, position)，只在新 g 更小时更新父指针并入堆；弹出时跳过陈旧项，目标出堆后回溯路径。默认同 f 优先较小 h，邻居依次为右、下、左、上，无解返回 [] / -1。"))
    add(p("Minimax 在 MAX 层取最大值、MIN 层取最小值；Alpha-beta 维护 MAX 已保证的下界 α 与 MIN 已保证的上界 β，α≥β 时停止搜索剩余兄弟。题三默认严格从左到右访问，叶子读取 value，非叶子读取 children。"))
    add(p("设置：Windows 11、CPython {}；各项预热 1 次、测量 {} 次，perf_counter_ns 计时，报告中时间取中位数。A* 的“扩展”不含目标和陈旧出堆；博弈的“访问”含根、叶与缓存命中。博弈计时不含距离预计算，原始记录见 results/。".format(d["metadata"]["python"],d["metadata"]["repeats"]),"small"))
    add(p("2　题目一：最短路径如何形成","h1"))
    from sys import path as python_path
    python_path.insert(0,str(ROOT))
    from examples import MAZE
    add(grid_figure(MAZE["grid"],d["paths"]["Q1_official"]["path"]))
    add(p("图 1　给定迷宫的最短路径；坐标采用 (row, col)，从 0 开始。","caption"))
    rows=[["启发函数 / 同 f 规则","扩展数","生成数","中位时间 / μs"]]
    for r,label in zip(search_rows("Q1_official"),("h=0 / FIFO","曼哈顿 / FIFO","曼哈顿 / 较小 h")):
        rows.append([label,r["expanded"],r["generated"],r["median_us"]])
    add(table(rows,[223,78,78,WIDTH-379]))
    add(p("表 1　题一给定迷宫的启发函数与同分策略对照。","caption"))
    add(Spacer(1,7))
    add(p("四方向单位代价下，曼哈顿距离既不高估剩余步数，也满足一致性。相同 FIFO 条件下，扩展数从 15 降至 13；再改变同 f 规则才降至 7，因此不能把全部节省都归因于启发函数。每条合法路径至少需要 |3-0|+|4-0|=7 步，返回路径达到此下界，故为最短。"))
    add(PageBreak())
    # PAGE 2 --------------------------------------------------------------
    add(p("3　题目二：进入代价与启发函数","h1"))
    add(p("路径选择依据总代价而非步数。样例返回 (0,0) → (1,0) → (2,0) → (3,0) → (3,1) → (3,2) → (4,2) → (4,3) → (4,4)。起点初始 g=0；最后进入 E 的代价按题意为 0，其余七次进入均为 1，所以 8 步的总代价为 7。"))
    steps=d["paths"]["Q2_official"]["steps"]
    add(table([["位置"]+["({},{})".format(*s["position"]) for s in steps],
               ["进入代价"]+[s["entry_cost"] for s in steps],
               ["累计 g"]+[s["cumulative"] for s in steps]], [60]+[(WIDTH-60)/9]*9))
    add(p("表 2　题二最优路径的逐格进入代价与累计代价。","caption"))
    add(Spacer(1,7))
    add(p("原始 h=D（曼哈顿距离）不再总可采纳：紧邻 E 的格子有 D=1，但真实剩余代价为 0。实现令 m 为非目标可通行格的最小进入代价，使用 h=m·max(D-1,0)。任意路径至少还要走 D 步，除最后一步外至少 D-1 步各花费 m，因此该式是下界。普通相邻格的 h 最多下降 m，而实际边权不少于 m；进入 E 时 h 已为 0，故仍满足一致性。"))
    add(p("若地图含其他 0 代价格，m=0，启发函数安全退化为 Dijkstra；若终点本身非零，则采用全图最小进入代价乘 D。样例在相同 FIFO 下，h=0 与修正 h 的扩展数分别为 14、10，代价均为 7。自设 S→99→E 与下方三个 1 的地图中，程序选择绕路，代价为 3，而非直走的 99。"))
    add(p("4　题目三：数值回传与剪枝依据","h1"))
    add(p("JSON 样例在最底层回传 5、9、9、2，上层两个 MIN 回传 5、2，根 MAX 因而得到 5。左侧 MIN 在首个子树后已有 β=5；下一个 MAX 刚看到叶子 6，便有 α≥β，剩下的 9 无法改变该 MIN 的选择，于是跳过。共享 max2 对象的 Python 构造也得到 5，统计时按树中出现次数访问。"))
    rows=[["输入 / 方法 / 顺序","访问数","叶子数","剪枝点","得分"]]
    for case,alg,order,label in [
        ("official","minimax","original","给定树 / Minimax"),
        ("official","alphabeta","original","给定树 / AB 左→右"),
        ("official","alphabeta","reverse","给定树 / AB 全层逆序"),
        ("order_control","minimax","original","自设树 / Minimax"),
        ("order_control","alphabeta","original","自设树 / AB 左→右"),
        ("order_control","alphabeta","reverse","自设树 / AB 全层逆序")]:
        r=next(r for r in d["tree"] if r["case"]==case and r["algorithm"]==alg and r["order"]==order)
        rows.append([label,r["visited"],r["leaves"],r["cutoffs"],r["value"]])
    add(table(rows,[WIDTH-240,60,60,60,60]))
    add(p("表 3　给定博弈树与自设顺序对照树的搜索开销。","caption"))
    add(Spacer(1,7))
    add(p("给定树正序、逆序恰好都访问 14 个节点，说明逆序不必然更差。为检验顺序影响，自设 MAX 根的三个 MIN 子树，其叶子依次为 [3,4,5]、[1,2,9]、[0,6,7]。正序较早建立 α=3，后两子树各见到 1、0 即剪枝；全层逆序却延迟有效界的建立，需要遍历全部 13 个节点。"))
    add(PageBreak())
    # PAGE 3 --------------------------------------------------------------
    add(p("5　题目四：距离预计算与博弈建模","h1"))
    add(p("将 A、B、T1…T4 的位置视作 6 个寻路端点，分别运行 A* 得到下表。A、B、宝藏格的进入代价均为 1；经过其他宝藏不收集，已取宝藏格仍通行，另一玩家不阻挡。宝藏价值依次为 9、6、7、7。"))
    matrix=[["起点\\终点"]+d["distance_labels"]]
    matrix += [[label]+row for label,row in zip(d["distance_labels"],d["distance_matrix"])]
    add(table(matrix,[WIDTH/7]*7))
    add(p("表 4　6×6 最小移动代价矩阵，行是起点、列是终点；对角线为 0。","caption"))
    add(p("状态为 s=(pA,pB,R,SA,SB,turn)：双方当前位置、剩余宝藏元组、双方累计收益和当前玩家。当前玩家选择 t 后，gain=Vt-d(p,t)，只更新其自身位置与得分，移除 t，再交替行动。深度 H 按单次行动计数；H=0 或 R 为空时评价 U=SA-SB，允许负收益，不能因 gain&lt;0 擅自跳过必须执行的回合。"))
    add(p("每个首步的精确值如下；为避免把剪枝界误当真值，绘图数据由每个首步独立进行完整 Minimax 得到。两种搜索在两种深度下均与题目预期一致。"))
    add(action_chart(d["first_move_values"]))
    add(p("图 2　A 固定首步后，双方最优应对的收益差 U；横轴为收益差。","caption"))
    add(p("H=2 的首步值为 [-4,-1,-2,-4]，所以选择 T2；A 从起点到 T2 花费 4，收益 2，B 随后取 T3 收益 3，故 U=-1。此深度只看各走一步，偏好立即获益。"))
    add(p("H=4 的首步值变为 [-5,1,3,-7]，最优改为 T3。先取 T3 虽使 A 当下收益为 -1，却占据 B 原本可从起点以收益 3 取得的宝藏，同时改变后续两步的路径代价；完整四回合评价因此优于先取 T2 的 U=1。"))
    add(p("当前地图静态、路径中途没有自动收集或碰撞，故只保存端点距离即可保持博弈结果等价。一般“进入格代价”是有向边权，本实现实际计算各有序端点对；样例矩阵对称，是因为各端点的进入代价相同，不能对任意加权图默认对称。","small"))
    add(PageBreak())
    # PAGE 4 --------------------------------------------------------------
    add(p("6　搜索深度、访问顺序与对抗行为","h1"))
    add(p("下表比较同一地图、同一终局函数下的搜索开销。为固定并列首步的选择，根层一律按 T1…T4；顺序变量只作用于所有内部层。正序为编号顺序，逆序反之，收益排序为当前玩家自身 gain 从高到低。B 应优先尝试自身高 gain 的动作，才能更快压低 U。"))
    rows=[["H / 方法 / 内部顺序","访问","叶子","剪枝点","时间 / μs"]]
    for h in (2,4):
        for alg,order,label in [("minimax","original","Minimax 正序"),("alphabeta","original","AB 正序"),
                                ("alphabeta","reverse","AB 逆序"),("alphabeta","gain","AB 收益排序")]:
            r=game_row(h,alg,order)
            rows.append(["{} / {}".format(h,label),r["visited"],r["leaves"],r["cutoffs"],r["median_us"]])
    add(table(rows,[WIDTH-258,51,51,66,90]))
    add(p("表 5　宝藏分配中搜索深度、算法与内部访问顺序的对照。","caption"))
    add(Spacer(1,7))
    add(p("H=4 完整树的节点数为 1+4+12+24+24=65。AB 正序访问 47 个，减少 27.7%；收益排序访问 43 个，减少 33.8%。所有方法的首步与得分不变，减少的是不能影响根决策的分支。“剪枝点”是提前停止搜索兄弟节点的次数，不等于跳过的节点总数。"))
    a=game_row(4,"alphabeta","original")
    b=game_row(4,"alphabeta","gain")
    add(p("节点减少也不保证耗时减少：本次 H=4 中，AB 正序与收益排序的中位时间分别为 {}、{} μs。此处树很小，额外 gain 计算、排序和函数调用会抵消节点节省；单次微秒级耗时还受调度与缓存影响，因此以确定性的节点数为主、时间为辅。".format(a["median_us"],b["median_us"])))
    add(p("H=4 的一条最优对抗序列","h1"))
    rows=[["回合 / 玩家","动作","路费 d","收益 gain","累计 U"]]
    for i,step in enumerate(d["optimal_lines"]["4"],1):
        rows.append(["{} / {}".format(i,step["player"]),step["source"]+" → "+step["target"],step["distance"],step["gain"],step["utility"]])
    add(table(rows,[90,WIDTH-270,60,60,60]))
    add(p("表 6　H=4 的一条最优对抗序列及累计收益差。","caption"))
    add(Spacer(1,7))
    add(p("终局 SA=-1、SB=-4，因而 U=3。B 最后被迫从 T1 去 T4，花费 12、价值仅 7，收益为 -5。这个例子说明竞争目标是相对收益差，A 的最优策略不一定使自身绝对得分非负，也不一定先拿最近或价值最高的宝藏。这里给出的是一条最优序列，并非声称每个中间选择都唯一。"))
    add(p("复杂度：四邻接网格有 E≤4V；在本实现的一致启发函数下，A* 用堆约为 O(V log V)、存储 O(V)。博弈最坏仍为 O(b^H)；良好顺序下 Alpha-beta 可显著减少分支，但不保证最佳情形。若有 n 个宝藏，完整无剪枝树是排列树，叶子为 n!，因此端点预计算、排序和状态复用比单纯提高搜索深度更有实际意义。"))
    add(PageBreak())
    # PAGE 5 --------------------------------------------------------------
    add(p("7　自设对照、优化与验证","h1"))
    add(p("A* 同 f 策略。构造 60×60 空地图，以及障碍率 0.24、种子 20261104 的地图；后者打通顶行和右列以保证存在长 118 的路线。三种方法均得到代价 118，扩展数如下。"))
    rows=[["地图 / 指标","h=0 / FIFO","曼哈顿 / FIFO","曼哈顿 / 较小 h"]]
    for case,label in (("open60","空地图"),("obstacles60_seed20261104","障碍地图")):
        rs=search_rows(case)
        rows.append([label+"：扩展数"]+[r["expanded"] for r in rs])
        rows.append([label+"：时间 / μs"]+[r["median_us"] for r in rs])
    add(table(rows,[WIDTH*.32]+[WIDTH*.68/3]*3))
    add(p("表 7　自设大地图上的启发函数与同分策略对照。","caption"))
    add(Spacer(1,6))
    add(p("空地图上每个单调前进状态都有 f=118，故曼哈顿配 FIFO 仍扩展 3599 个，不能宣称“用了 A* 就一定更快”。同 f 优先较小 h 后只扩展 118 个，但队列峰值由 60 增为 117，节点减少不等于峰值内存同步减少。障碍图预留边界路线且方向顺序有利于该路线，这组结果仅说明机制，不能外推到所有迷宫。"))
    add(p("状态缓存与规模拓展。自设 5×5 单位代价地图、6 个宝藏、H=6；位置、价值完整保存在 results.json 的 extension_fixture。全遍历访问 1957 个节点，最优结果为 T6、U=5。缓存键为双方位置、剩余宝藏、轮次与剩余深度，缓存“未来增量 U”而非当前累计 U，避免不同历史得分污染复用；Alpha-beta 另区分 EXACT / LOWER / UPPER 界。"))
    rows=[["方法","访问","缓存命中","时间 / μs"]]
    for alg,order,cache,label in [("minimax","original",False,"Minimax"),("minimax","original",True,"Minimax + 缓存"),
                                 ("alphabeta","gain",False,"AB + 收益排序"),("alphabeta","gain",True,"AB + 排序 + 缓存")]:
        r=next(r for r in d["extension"] if r["algorithm"]==alg and r["order"]==order and r["cache"]==cache)
        rows.append([label,r["visited"],r["cache_hits"],r["median_us"]])
    add(table(rows,[WIDTH-225,65,75,85]))
    add(p("表 8　自设六宝藏场景中的排序与状态缓存对照。","caption"))
    add(Spacer(1,6))
    add(p("缓存将 Minimax 的重复搜索从 1957 次压到 997 次；AB 排序后为 409 次，再加缓存为 341 次。缓存查表与边界管理也有成本，小型四宝藏问题不保证加速，优化应由规模和重复状态数量决定。"))
    add(p("正确性与复现","h1"))
    add(p("实际通过 {} 项 unittest 测试方法：含 250 张随机迷宫对 BFS、250 张随机加权图对独立 Dijkstra、200 棵随机树对穷举 Minimax，以及 40 个随机宝藏场景的深度、顺序、缓存组合对独立穷举。另测不可达、起终点重合、E=0、零代价退化、绕路优于直走、共享子树、缓存界与累计得分偏移；不是仅比较给定输出。".format(v["test_methods"])))
    add(p("复现命令（在解压目录执行）：","small"))
    add(p("python verify.py<br/>python main.py experiment --repeats 51<br/>python tools/build_report.py","code"))
    add(p("结果与思考：四题样例全部匹配；可采纳性取决于真实边权与终点规则，剪枝收益取决于何时建立有效界，浅层收益不能替代完整对抗评价。实验固定种子并公开原始 JSON/CSV；节点计数应可重现，计时可随设备波动。题目来源：《实验二要求_new.pdf》第 3-17 页；算法实现与对照输入均随代码提交。GitHub 链接按要求暂留空，填写 report_config.json 后可重建本报告。","small"))
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=37,bottomMargin=47,
                          title="当代人工智能实验二：搜索算法",author="",pageCompression=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    pdf=PdfReader(str(output))
    if len(pdf.pages)!=5:
        raise SystemExit("Expected exactly 5 pages, got {}. Report must be repaired before submission.".format(len(pdf.pages)))
    text="\n".join(page.extract_text() for page in pdf.pages)
    assert "GitHub" in pdf.pages[0].extract_text()
    assert "EXACT" in text and "6×6" in text
    validation={"report_file":output.name,"pages":len(pdf.pages),"max_pages":5,
                "github_url":config["github_url"],"bytes":output.stat().st_size,
                "sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
                "page_character_counts":[len(page.extract_text()) for page in pdf.pages]}
    (ROOT/"results/report_validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(output.resolve()),"pages":len(pdf.pages),"github_url":config["github_url"],
                      "tests":v["test_methods"]},ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Rebuild the five-page Chinese report")
    parser.add_argument("--output",type=Path,default=ROOT/"实验二报告.pdf")
    parser.add_argument("--font",help="optional Chinese TrueType/TTC font path")
    args=parser.parse_args()
    build_report(args.output,args.font)
