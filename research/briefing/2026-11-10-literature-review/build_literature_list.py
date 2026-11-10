from __future__ import annotations

import csv
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "文献调研结果汇总清单.csv"
OUTPUT = ROOT / "非结构化阴性数据挖掘与应用_文献调研结果清单.docx"


def set_font(run, size=7.5, bold=False, color="222222") -> None:
    run.font.name = "Aptos"
    rpr = run._element.get_or_add_rPr()
    rpr.rFonts.set(qn("w:eastAsia"), "宋体")
    rpr.rFonts.set(qn("w:ascii"), "Aptos")
    rpr.rFonts.set(qn("w:hAnsi"), "Aptos")
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_margins(cell, value=55) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge in ("top", "start", "bottom", "end"):
        node = tc_mar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def add_hyperlink(paragraph, text: str, url: str) -> None:
    rid = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4E79")
    rpr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Aptos")
    fonts.set(qn("w:hAnsi"), "Aptos")
    fonts.set(qn("w:eastAsia"), "宋体")
    rpr.append(fonts)
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "14")
    rpr.append(size)
    run.append(rpr)
    text_el = OxmlElement("w:t")
    text_el.text = text
    run.append(text_el)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def id_url(identifier: str) -> str | None:
    value = identifier.strip()
    if re.fullmatch(r"10\.\d{4,9}/\S+", value):
        return f"https://doi.org/{value}"
    if value.startswith("PMID: "):
        return f"https://pubmed.ncbi.nlm.nih.gov/{value.split(':', 1)[1].strip()}/"
    if value.startswith("PMCID: "):
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{value.split(':', 1)[1].strip()}/"
    if value.startswith("arXiv: "):
        return f"https://arxiv.org/abs/{value.split(':', 1)[1].strip()}"
    if value.startswith("ACL: "):
        return f"https://aclanthology.org/{value.split(':', 1)[1].strip()}/"
    return None


def build() -> None:
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(1.35)
    section.bottom_margin = Cm(1.25)
    section.left_margin = Cm(1.25)
    section.right_margin = Cm(1.25)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(3)
    run = title.add_run("非结构化阴性数据挖掘与应用：文献调研结果清单")
    set_font(run, size=16, bold=True, color="111111")

    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.space_after = Pt(7)
    run = note.add_run("供队长统一整合｜仅保留论文题名与检索信息，不含综述正文｜核心方法24篇，垂域案例16篇")
    set_font(run, size=8.5, color="666666")

    headers = ["编号", "层级", "区域", "研究方向", "论文题名", "年份及来源", "DOI或标识"]
    widths = [Cm(0.8), Cm(1.15), Cm(1.65), Cm(2.25), Cm(10.8), Cm(4.6), Cm(4.9)]
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False

    for idx, header in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.width = widths[idx]
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_margins(cell)
        shade(cell, "D9EAF7")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(header)
        set_font(r, size=7.5, bold=True, color="17365D")
    repeat_header(table.rows[0])

    for row_index, data in enumerate(rows, start=1):
        table_row = table.add_row()
        prevent_row_split(table_row)
        cells = table_row.cells
        values = [data[h] for h in headers]
        for col, value in enumerate(values):
            cell = cells[col]
            cell.width = widths[col]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_margins(cell)
            if row_index % 2 == 0:
                shade(cell, "F5F8FA")
            if data["层级"] == "案例":
                shade(cell, "FFF8E7" if row_index % 2 else "F9F0D8")
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.02
            if col in (0, 1, 2):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if col == 6 and (url := id_url(value)):
                add_hyperlink(p, value, url)
            else:
                r = p.add_run(value)
                set_font(r, size=7.2, bold=(col == 4))

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run("文献调研结果清单 · 2026.11.10")
    set_font(r, size=7, color="777777")

    props = doc.core_properties
    props.title = "非结构化阴性数据挖掘与应用：文献调研结果清单"
    props.subject = "供队长整合国内外研究现状与文献综述"
    props.keywords = "非结构化阴性数据; 文献清单; 信息抽取; RAG; 分子胶案例"
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
