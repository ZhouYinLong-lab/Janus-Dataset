import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

ROOT = Path(__file__).parent
FONT = r"C:\Windows\Fonts\simhei.ttf"
pdfmetrics.registerFont(TTFont("Chinese", FONT))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CNTitle", parent=styles["Title"], fontName="Chinese", fontSize=19,
    leading=24, alignment=TA_CENTER, textColor=colors.HexColor("#000000"),
    spaceAfter=9 * mm, wordWrap="CJK"
))
styles.add(ParagraphStyle(
    name="CNH2", parent=styles["Heading2"], fontName="Chinese", fontSize=13,
    leading=17, textColor=colors.HexColor("#000000"), spaceBefore=3.5 * mm,
    spaceAfter=1.8 * mm, wordWrap="CJK", keepWithNext=True
))
styles.add(ParagraphStyle(
    name="CNH3", parent=styles["Heading3"], fontName="Chinese", fontSize=11,
    leading=15, textColor=colors.HexColor("#000000"), spaceBefore=3 * mm,
    spaceAfter=1.5 * mm, wordWrap="CJK", keepWithNext=True
))
styles.add(ParagraphStyle(
    name="CNBody", parent=styles["BodyText"], fontName="Chinese", fontSize=9.4,
    leading=15, alignment=TA_LEFT, textColor=colors.HexColor("#222222"),
    spaceAfter=1.5 * mm, wordWrap="CJK"
))
styles.add(ParagraphStyle(
    name="CNSmall", parent=styles["BodyText"], fontName="Chinese", fontSize=8.2,
    leading=12, alignment=TA_LEFT, textColor=colors.HexColor("#333333"),
    spaceAfter=1.5 * mm, wordWrap="CJK"
))
styles.add(ParagraphStyle(
    name="CNBullet", parent=styles["BodyText"], fontName="Chinese", fontSize=9.2,
    leading=14, leftIndent=5 * mm, firstLineIndent=-4 * mm,
    textColor=colors.HexColor("#222222"), spaceAfter=1.5 * mm, wordWrap="CJK"
))
styles.add(ParagraphStyle(
    name="CNCode", parent=styles["Code"], fontName="Chinese", fontSize=8.5,
    leading=12, leftIndent=5 * mm, rightIndent=5 * mm, backColor=colors.HexColor("#F5F5F5"),
    borderPadding=4, spaceAfter=2.5 * mm, wordWrap="CJK"
))
styles.add(ParagraphStyle(
    name="CNTable", parent=styles["BodyText"], fontName="Chinese", fontSize=7.6,
    leading=10.5, textColor=colors.HexColor("#222222"), wordWrap="CJK"
))
styles.add(ParagraphStyle(
    name="CNTableHead", parent=styles["BodyText"], fontName="Chinese", fontSize=7.7,
    leading=10.5, textColor=colors.white, wordWrap="CJK"
))


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#1F4E79">\1</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font color="#333333">\1</font>', text)
    return text


def is_separator(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def table_flow(lines):
    rows = []
    for line in lines:
        if is_separator(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return []
    n = max(len(r) for r in rows)
    for r in rows:
        r.extend([""] * (n - len(r)))
    data = []
    for i, row in enumerate(rows):
        style = styles["CNTableHead"] if i == 0 else styles["CNTable"]
        data.append([Paragraph(inline(c), style) for c in row])
    usable = 170 * mm
    widths = [usable / n] * n
    if n == 2:
        widths = [46 * mm, usable - 46 * mm]
    elif n == 3:
        widths = [38 * mm, 43 * mm, usable - 81 * mm]
    elif n == 4:
        widths = [32 * mm, 46 * mm, 46 * mm, usable - 124 * mm]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#355C7D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for row in range(1, len(data)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F3F6F8")))
    t.setStyle(TableStyle(commands))
    return [t, Spacer(1, 3 * mm)]


class NumberedDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        frame = self._makeFrame()
        self.addPageTemplates([PageTemplate(id="normal", frames=frame, onPage=self._footer)])

    def _makeFrame(self):
        from reportlab.platypus import Frame
        return Frame(20 * mm, 17 * mm, 170 * mm, 260 * mm, id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Chinese", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(20 * mm, 9 * mm, "候选场景调查 | 用于大创申报书前期筛选")
        canvas.drawRightString(190 * mm, 9 * mm, f"第 {doc.page} 页")
        canvas.restoreState()


def parse_md(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    story = []
    i = 0
    in_code = False
    code_lines = []
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                in_code = False
                story.append(Paragraph(inline("\n".join(code_lines)), styles["CNCode"]))
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            story.extend(table_flow(block))
            continue
        if not line.strip():
            if i > 0 and lines[i - 1].startswith("#"):
                i += 1
                continue
            story.append(Spacer(1, 0.35 * mm))
            i += 1
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["CNTitle"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["CNH2"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), styles["CNH3"]))
        elif re.match(r"^\d+\.\s+", line):
            story.append(Paragraph("• " + inline(re.sub(r"^\d+\.\s+", "", line)), styles["CNBullet"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + inline(line[2:]), styles["CNBullet"]))
        else:
            story.append(Paragraph(inline(line), styles["CNBody"]))
        i += 1
    return story


def main():
    if len(sys.argv) > 1:
        markdown_files = [Path(arg) if Path(arg).is_absolute() else ROOT / arg for arg in sys.argv[1:]]
    else:
        markdown_files = sorted(ROOT.glob("候选领域调研_*.md"))
    for md in markdown_files:
        pdf = md.with_suffix(".pdf")
        doc = NumberedDocTemplate(str(pdf), pagesize=A4, title=md.stem, author="Codex")
        doc.build(parse_md(md))
        print(pdf)


if __name__ == "__main__":
    main()

