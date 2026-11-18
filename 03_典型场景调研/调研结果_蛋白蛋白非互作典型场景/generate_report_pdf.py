from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

ROOT = Path(__file__).parent
FONT = r"C:\Windows\Fonts\Deng.ttf"
FONT_BOLD = r"C:\Windows\Fonts\Dengb.ttf"
pdfmetrics.registerFont(TTFont("Deng", FONT))
pdfmetrics.registerFont(TTFont("DengBold", FONT_BOLD))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CNTitle", parent=styles["Title"], fontName="DengBold", fontSize=18,
    leading=24, alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor("#17365D"),
))
styles.add(ParagraphStyle(
    name="CNH1", parent=styles["Heading1"], fontName="DengBold", fontSize=12.5,
    leading=17, spaceBefore=7, spaceAfter=4, textColor=colors.HexColor("#17365D"),
))
styles.add(ParagraphStyle(
    name="CNH2", parent=styles["Heading2"], fontName="DengBold", fontSize=11.5,
    leading=16, spaceBefore=7, spaceAfter=4, textColor=colors.HexColor("#2F5597"),
))
styles.add(ParagraphStyle(
    name="CNBody", parent=styles["BodyText"], fontName="Deng", fontSize=8.7,
    leading=12.2, spaceAfter=3, firstLineIndent=0,
))
styles.add(ParagraphStyle(
    name="CNSmall", parent=styles["BodyText"], fontName="Deng", fontSize=7.2,
    leading=8.8, spaceAfter=1,
))
styles.add(ParagraphStyle(
    name="CNQuote", parent=styles["BodyText"], fontName="Deng", fontSize=9,
    leading=13, leftIndent=12, rightIndent=8, borderPadding=6,
    borderColor=colors.HexColor("#B4C7E7"), borderWidth=0.5, borderLeft=True,
    spaceBefore=4, spaceAfter=7, backColor=colors.HexColor("#F3F6FA"),
))

def esc(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = text.replace("**", "")
    text = text.replace("`", "")
    return text

def para(text, style="CNBody"):
    return Paragraph(esc(text), styles[style])

def parse_table(lines, start):
    rows = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        line = lines[i].strip().strip("|")
        cells = [c.strip() for c in line.split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            i += 1
            continue
        rows.append(cells)
        i += 1
    if not rows:
        return [], i
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    data = [[Paragraph(esc(c), styles["CNSmall"]) for c in row] for row in rows]
    avail = 180 * mm
    widths = [avail / n] * n
    if n == 2:
        widths = [45 * mm, 135 * mm]
    elif n == 3:
        widths = [38 * mm, 60 * mm, 82 * mm]
    elif n == 4:
        widths = [35 * mm, 48 * mm, 50 * mm, 47 * mm]
    elif n == 5:
        widths = [30 * mm, 37 * mm, 42 * mm, 38 * mm, 33 * mm]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Deng"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, 4)], i

def build(md_path: Path, pdf_path: Path):
    lines = md_path.read_text(encoding="utf-8").splitlines()
    story = []
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        s = raw.strip()
        if not s:
            i += 1
            continue
        if s.startswith("# "):
            story.append(para(s[2:], "CNTitle"))
        elif s.startswith("## "):
            story.append(para(s[3:], "CNH1"))
        elif s.startswith("### "):
            story.append(para(s[4:], "CNH2"))
        elif s.startswith("| "):
            items, i = parse_table(lines, i)
            story.extend(items)
            continue
        elif s.startswith("> "):
            quote = s[2:]
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("> "):
                quote += " " + lines[j].strip()[2:]
                j += 1
            story.append(para(quote, "CNQuote"))
            i = j
            continue
        elif s.startswith("```"):
            code_lines = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                if lines[j].strip():
                    code_lines.append(lines[j].strip())
                j += 1
            if code_lines:
                story.append(para(" → ".join(code_lines), "CNQuote"))
            i = j + 1
            continue
        elif re.match(r"^[-*] ", s):
            story.append(para("• " + s[2:], "CNBody"))
        elif re.match(r"^\d+\. ", s):
            story.append(para(s, "CNBody"))
        elif s.startswith("---"):
            story.append(Spacer(1, 4))
        else:
            # Join a simple paragraph with immediately following ordinary lines.
            text = s
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if (not nxt or nxt.startswith("#") or nxt.startswith("|") or
                    nxt.startswith("> ") or re.match(r"^[-*] ", nxt) or re.match(r"^\d+\. ", nxt)):
                    break
                text += " " + nxt
                j += 1
            story.append(para(text, "CNBody"))
            i = j
            continue
        i += 1

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Deng", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(18 * mm, 10 * mm, "大创项目典型场景调研结果")
        canvas.drawRightString(192 * mm, 10 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4, rightMargin=13 * mm, leftMargin=13 * mm,
        topMargin=12 * mm, bottomMargin=14 * mm,
        title=md_path.stem,
        author="调研组",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


FILES = [
    "调研报告_蛋白蛋白非互作_成功_2026-11-13",
]
for stem in FILES:
    build(ROOT / f"{stem}.md", ROOT / f"{stem}.pdf")
    print(ROOT / f"{stem}.pdf")
