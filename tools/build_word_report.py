"""Create an editable Word companion from the PDF report's shared content.

Text and tables are native Word elements; only the two figures are images.
Optional requirements: python-docx and Pillow, plus requirements-report.txt.
"""

import argparse
from html import unescape
import json
import os
from pathlib import Path
import re
import tempfile

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table

import build_report

ROOT = Path(__file__).resolve().parents[1]


def plain(value):
    return unescape(re.sub(r"<[^>]+>", "", str(value).replace("<br/>", "\n")))


def capture_story():
    class Captured(Exception):
        pass

    class Collector:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, story, **kwargs):
            self.story = story
            raise Captured(story)

    original = build_report.SimpleDocTemplate
    build_report.SimpleDocTemplate = Collector
    try:
        build_report.build_report(ROOT / "实验二报告.pdf")
    except Captured as result:
        return result.args[0]
    finally:
        build_report.SimpleDocTemplate = original


def color(value):
    if value is None:
        return None
    return tuple(round(255 * c) for c in (value.red, value.green, value.blue))


def figure_png(drawing, destination):
    scale = 4
    canvas = Image.new("RGB", (round(drawing.width * scale), round(drawing.height * scale)), "white")
    pen = ImageDraw.Draw(canvas)
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for item in drawing.contents:
        if isinstance(item, Rect):
            box = [item.x * scale, (drawing.height-item.y-item.height)*scale,
                   (item.x+item.width)*scale, (drawing.height-item.y)*scale]
            pen.rectangle(box, fill=color(item.fillColor), outline=color(item.strokeColor),
                          width=max(1, round(item.strokeWidth*scale)))
        elif isinstance(item, Line):
            pen.line([(item.x1*scale, (drawing.height-item.y1)*scale),
                      (item.x2*scale, (drawing.height-item.y2)*scale)],
                     fill=color(item.strokeColor), width=max(1,round(item.strokeWidth*scale)))
        elif isinstance(item, String):
            filename = "simsun.ttc" if item.fontName == "BodyCN" else (
                "simhei.ttf" if item.fontName == "HeadCN" else (
                    "arialbd.ttf" if "Bold" in item.fontName else "arial.ttf"))
            font = ImageFont.truetype(str(fonts / filename), round(item.fontSize * scale))
            anchor = {"middle": "ms", "end": "rs"}.get(item.textAnchor, "ls")
            pen.text((item.x*scale, (drawing.height-item.y)*scale), item.text,
                     fill=color(item.fillColor), font=font, anchor=anchor)
        else:
            raise TypeError("Unhandled figure primitive: " + type(item).__name__)
    canvas.save(destination)


def set_font(run, size, east="宋体", latin="Times New Roman", bold=False, rgb="183744"):
    run.font.name = latin
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), east)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(rgb)


def build(output):
    story = capture_story()
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Pt(595.276), Pt(841.89)
    section.left_margin = section.right_margin = Pt(42)
    section.top_margin, section.bottom_margin = Pt(37), Pt(47)
    section.footer_distance = Pt(21)
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = "Times New Roman", Pt(10.3)
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    normal.paragraph_format.line_spacing = Pt(15.7)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.widow_control = False
    for name in ("Title", "Heading 1", "Heading 2"):
        document.styles[name].font.color.rgb = RGBColor(0, 0, 0)
    for style in document.styles:
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    document.styles["Footer"].paragraph_format.tab_stops.clear_all()
    footer = section.footer.paragraphs[0]
    footer.paragraph_format.space_after = Pt(0)
    footer.paragraph_format.line_spacing = Pt(10)
    footer.paragraph_format.tab_stops.clear_all()
    footer.paragraph_format.tab_stops.add_tab_stop(Pt(build_report.WIDTH), WD_TAB_ALIGNMENT.RIGHT)
    set_font(footer.add_run("实验二 / 搜索算法 / 2026-11-04\t"), 8, rgb="60717B")
    for field in ("PAGE", "NUMPAGES"):
        if field == "NUMPAGES":
            set_font(footer.add_run(" / "), 8, rgb="60717B")
        node = OxmlElement("w:fldSimple")
        node.set(qn("w:instr"), field)
        footer._p.append(node)
    with tempfile.TemporaryDirectory(prefix="experiment2_word_figures_") as scratch:
        figure_index = 0
        for item in story:
            if isinstance(item, PageBreak):
                p = document.add_paragraph()
                p.paragraph_format.space_after = p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.line_spacing = Pt(1)
                p.add_run().add_break(WD_BREAK.PAGE)
            elif isinstance(item, Paragraph):
                kind = item.style.name
                p = document.add_paragraph(style="Title" if kind == "title" else (
                    "Heading 1" if kind == "h1" else "Normal"))
                fmt = p.paragraph_format
                fmt.space_before = Pt(getattr(item.style, "spaceBefore", 0))
                fmt.space_after = Pt(item.style.spaceAfter)
                fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                fmt.line_spacing = Pt(item.style.leading)
                fmt.keep_with_next = kind in ("title", "h1")
                if kind == "caption":
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                text = plain(item.text)
                set_font(p.add_run(text), item.style.fontSize,
                         east="黑体" if kind in ("title", "h1") else "宋体",
                         latin="Consolas" if kind == "code" else "Times New Roman",
                         bold=kind in ("title", "h1"),
                         rgb="000000" if kind in ("title", "h1") else (
                             "60717B" if kind in ("small", "caption") else "183744"))
            elif isinstance(item, Table):
                rows = item._cellvalues
                table = document.add_table(rows=len(rows), cols=len(rows[0]))
                table.alignment = WD_TABLE_ALIGNMENT.LEFT
                table.autofit = False
                properties = table._tbl.tblPr
                borders = OxmlElement("w:tblBorders")
                for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                    border = OxmlElement("w:" + edge)
                    for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                        border.set(qn("w:" + key), value)
                    borders.append(border)
                properties.append(borders)
                margins = OxmlElement("w:tblCellMar")
                for edge, width in (("top", 60), ("bottom", 60), ("left", 110), ("right", 90)):
                    element = OxmlElement("w:"+edge)
                    element.set(qn("w:w"), str(width))
                    element.set(qn("w:type"), "dxa")
                    margins.append(element)
                properties.append(margins)
                for c, width in enumerate(item._colWidths):
                    table.columns[c].width = Pt(width)
                for r, row in enumerate(rows):
                    no_split = OxmlElement("w:cantSplit")
                    table.rows[r]._tr.get_or_add_trPr().append(no_split)
                    if r == 0:
                        table.rows[r]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
                    for c, value in enumerate(row):
                        cell = table.cell(r, c)
                        cell.width = Pt(item._colWidths[c])
                        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                        p = cell.paragraphs[0]
                        p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(0)
                        p.paragraph_format.line_spacing = Pt(13)
                        p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c == 0 else WD_ALIGN_PARAGRAPH.CENTER
                        set_font(p.add_run(plain(value.text if isinstance(value, Paragraph) else value)),
                                 9.2, bold=r==0, rgb="FFFFFF" if r==0 else "183744")
                        shade = OxmlElement("w:shd")
                        shade.set(qn("w:fill"), "177E89" if r==0 else ("F0F5F6" if r%2 else "FFFFFF"))
                        cell._tc.get_or_add_tcPr().append(shade)
            elif isinstance(item, Drawing):
                figure_index += 1
                png = Path(scratch) / ("figure-%d.png" % figure_index)
                figure_png(item, png)
                p = document.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1
                p.paragraph_format.keep_with_next = True
                p.add_run().add_picture(str(png), width=Pt(item.width), height=Pt(item.height))
            elif isinstance(item, Spacer):
                # Existing paragraph/table spacing already provides the gap.
                continue
            else:
                raise TypeError(type(item).__name__)
        document.core_properties.title = "当代人工智能实验二 搜索算法"
        document.core_properties.author = ""
        output.parent.mkdir(parents=True, exist_ok=True)
        document.save(output)
    print(json.dumps({"output": str(output.resolve()), "native_tables": len(document.tables),
                      "figure_count": figure_index, "paragraphs": len(document.paragraphs)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "实验二报告.docx")
    build(parser.parse_args().output)
