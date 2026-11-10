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
OUTPUT = ROOT / "非结构化阴性数据挖掘与应用_文献调研结果清单_带说明.docx"


def set_font(run, size=8, bold=False, color="222222") -> None:
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


def set_margins(cell, value=70) -> None:
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
    size.set(qn("w:val"), "16")
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


def add_intro(doc: Document) -> None:
    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(2)
    heading.paragraph_format.space_after = Pt(3)
    run = heading.add_run("我们做了什么")
    set_font(run, size=11.5, bold=True, color="17365D")

    paragraphs = [
        (
            "文献调研：",
            "我们围绕非结构化阴性数据的挖掘与应用整理了40篇论文。其中24篇涉及阴性结果发表偏倚、否定与不确定性识别、科学信息抽取、原文证据定位和检索增强；另外16篇来自分子胶降解剂领域，用于观察正文中容易被结构化数据库遗漏的失败结果和作用边界。",
        ),
        (
            "提取 pipeline：",
            "我们搭建了从全文解析、句段扫描和阴性候选发现，到实验对象、终点、条件及原文出处恢复的流程，并加入断点续跑、去重、失败记录、引用核对和分区导出。该流程把散落在正文中的阴性描述整理为可追溯的实验记录。",
        ),
        (
            "数据利用：",
            "恢复后的证据一方面接入RAG，与无检索、结构化数据库和原文检索进行对照；另一方面整理成结构化实验记录，为后续预测模型比较阳性偏置与加入阴性数据后的表现提供输入。",
        ),
        (
            "文献记录：",
            "每篇论文保留原始题名、年份、来源，以及DOI、PMID、arXiv或ACL编号等唯一标识，并按核心方法或垂域案例、国内或国外进行分类。整理结果见下表。",
        ),
    ]
    for prefix, text in paragraphs:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.paragraph_format.line_spacing = 1.12
        run = paragraph.add_run(prefix)
        set_font(run, size=9, bold=True, color="17365D")
        run = paragraph.add_run(text)
        set_font(run, size=9)


def build() -> None:
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))

    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(1.25)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.25)
    section.right_margin = Cm(1.25)

    title_style = doc.styles["Title"]
    title_style.font.color.rgb = RGBColor.from_string("111111")
    title_ppr = title_style.element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(5)
    run = title.add_run("非结构化阴性数据挖掘与应用 文献调研结果")
    set_font(run, size=16, bold=True, color="111111")

    add_intro(doc)

    headers = ["编号", "分组与区域", "论文题名", "来源与唯一标识"]
    widths = [Cm(0.9), Cm(2.4), Cm(14.2), Cm(7.5)]
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False

    for idx, header in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.width = widths[idx]
        set_margins(cell)
        shade(cell, "D9EAF7")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(header)
        set_font(run, size=8, bold=True, color="17365D")
    repeat_header(table.rows[0])

    for row_index, data in enumerate(rows, start=1):
        row = table.add_row()
        prevent_row_split(row)
        values = [
            data["编号"],
            f"{data['层级']}\n{data['区域']}",
            data["论文题名"],
            f"{data['年份及来源']}\n{data['DOI或标识']}",
        ]
        for col, value in enumerate(values):
            cell = row.cells[col]
            cell.width = widths[col]
            set_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2 == 0:
                shade(cell, "F5F8FA")
            if data["层级"] == "案例":
                shade(cell, "FFF8E7" if row_index % 2 else "F9F0D8")
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.04
            if col in (0, 1):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if col == 3:
                source, identifier = value.split("\n", 1)
                run = paragraph.add_run(source + "\n")
                set_font(run, size=7.8)
                if url := id_url(identifier):
                    add_hyperlink(paragraph, identifier, url)
                else:
                    run = paragraph.add_run(identifier)
                    set_font(run, size=7.8)
            else:
                run = paragraph.add_run(value)
                set_font(run, size=8, bold=(col == 2))

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("文献调研结果 · 2026.11.10")
    set_font(run, size=7, color="777777")

    properties = doc.core_properties
    properties.title = "非结构化阴性数据挖掘与应用 文献调研结果"
    properties.subject = "文献调研整理结果"
    properties.keywords = "非结构化阴性数据; 信息抽取; RAG; 分子胶"
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
