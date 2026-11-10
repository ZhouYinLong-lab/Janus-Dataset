from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "分子胶非结构化阴性证据研究文献调研.md"
OUTPUT = ROOT / "分子胶非结构化阴性证据研究文献调研.docx"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=90, start=100, bottom=90, end=100) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_run_font(run, east_asia="宋体", latin="Aptos", size=10.5, bold=None, color=None) -> None:
    run.font.name = latin
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), east_asia)
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), latin)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), latin)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_hyperlink(paragraph, text: str, url: str, color="1F4E79") -> None:
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    r_pr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    r_pr.append(u)
    r_fonts = OxmlElement("w:rFonts")
    r_fonts.set(qn("w:ascii"), "Aptos")
    r_fonts.set(qn("w:hAnsi"), "Aptos")
    r_fonts.set(qn("w:eastAsia"), "宋体")
    r_pr.append(r_fonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "20")
    r_pr.append(sz)
    new_run.append(r_pr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


INLINE_RE = re.compile(r"(\*\*.+?\*\*|DOI:\s*10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")


def add_inline(paragraph, text: str, size=10.5) -> None:
    pos = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            set_run_font(run, size=size)
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=size, bold=True)
        elif token.startswith("DOI:"):
            doi = token.split("DOI:", 1)[1].strip().rstrip(".")
            run = paragraph.add_run("DOI: ")
            set_run_font(run, size=size)
            add_hyperlink(paragraph, doi, f"https://doi.org/{doi}")
            if token.endswith("."):
                run = paragraph.add_run(".")
                set_run_font(run, size=size)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_run_font(run, size=size)


def style_document(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Cm(2.1)
    section.bottom_margin = Cm(1.9)
    section.left_margin = Cm(2.35)
    section.right_margin = Cm(2.15)

    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(10.5)
    pf = normal.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_after = Pt(5)
    pf.first_line_indent = Cm(0.74)

    for name, size, color, before, after in (
        ("Title", 20, "111111", 0, 12),
        ("Heading 1", 14, "17365D", 14, 6),
        ("Heading 2", 11.5, "1F4E79", 10, 4),
    ):
        style = doc.styles[name]
        style.font.name = "Aptos Display"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.first_line_indent = Cm(0)

    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("分子胶降解剂非结构化阴性证据研究文献调研  ·  2026.11")
    set_run_font(run, east_asia="微软雅黑", latin="Aptos", size=8, color="777777")


def add_table(doc: Document, rows: list[list[str]]) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    widths = [Cm(3.0), Cm(5.2), Cm(7.4)]
    for i, row in enumerate(table.rows):
        row.cells[0].width = widths[0]
        row.cells[1].width = widths[1]
        row.cells[2].width = widths[2]
        for j, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            add_inline(p, rows[i][j], size=9)
            if i == 0:
                set_cell_shading(cell, "D9EAF7")
                for r in p.runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor.from_string("17365D")
            elif i % 2 == 0:
                set_cell_shading(cell, "F5F8FA")
    set_repeat_table_header(table.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def build() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    doc = Document()
    style_document(doc)

    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        text = raw.strip()
        if not text:
            i += 1
            continue
        if text.startswith("# "):
            p = doc.add_paragraph(style="Title")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            add_inline(p, text[2:], size=20)
            i += 1
            continue
        if text.startswith("## "):
            doc.add_heading(text[3:], level=1)
            i += 1
            continue
        if text.startswith("### "):
            doc.add_heading(text[4:], level=2)
            i += 1
            continue
        if text.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            block = [row for idx, row in enumerate(block) if idx != 1]
            add_table(doc, block)
            continue
        if re.match(r"^\d+\. ", text):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.62)
            p.paragraph_format.first_line_indent = Cm(-0.62)
            p.paragraph_format.line_spacing = 1.08
            p.paragraph_format.space_after = Pt(1.5)
            add_inline(p, text, size=8.8)
            i += 1
            continue
        if text.startswith("更新日期：") or text.startswith("用途："):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_after = Pt(1)
            add_inline(p, text.rstrip("  "), size=9)
            for r in p.runs:
                r.font.color.rgb = RGBColor.from_string("666666")
            i += 1
            continue

        p = doc.add_paragraph()
        p.paragraph_format.widow_control = True
        add_inline(p, text, size=10.5)
        i += 1

    props = doc.core_properties
    props.title = "分子胶降解剂非结构化阴性证据研究文献调研"
    props.subject = "国内外研究现状、发展动态与项目定位"
    props.keywords = "分子胶降解剂; 非结构化阴性证据; 文献综述; 科学文本抽取"
    props.comments = "截至2026年11月10日"
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
