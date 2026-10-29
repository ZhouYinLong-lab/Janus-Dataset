"""Build the concise shared progress DOCX from frozen project numbers."""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).parent
NUMBERS = ROOT / "shared_update_numbers.json"
OUTPUT = ROOT / "分子胶非结构化阴性证据共享进展.docx"
BLUE = "1F4E78"
PALE = "EAF2F8"
GRID = "D9D9D9"


def set_cell_fill(cell, color: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), color)


def set_cell_margins(cell, top=90, start=100, bottom=90, end=100) -> None:
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        properties.append(margins)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        element = margins.find(qn(f"w:{side}"))
        if element is None:
            element = OxmlElement(f"w:{side}")
            margins.append(element)
        element.set(qn("w:w"), str(value))


def remove_paragraph_borders(paragraph_or_style) -> None:
    element = paragraph_or_style._element
    properties = element.find(qn("w:pPr"))
    if properties is None:
        return
    borders = properties.find(qn("w:pBdr"))
    if borders is not None:
        properties.remove(borders)
        element.set(qn("w:type"), "dxa")


def set_table_borders(table) -> None:
    properties = table._tbl.tblPr
    borders = properties.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        properties.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = borders.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            borders.append(tag)
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), "5")
        tag.set(qn("w:color"), GRID)


def set_font(run, name: str, size: float, bold: bool = False, color: str = "000000") -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def remove_paragraph_borders(paragraph_or_style) -> None:
    element = paragraph_or_style._element
    properties = element.get_or_add_pPr()
    borders = properties.find(qn("w:pBdr"))
    if borders is not None:
        properties.remove(borders)


def add_text(paragraph, text: str, bold: bool = False, size: float = 10.5):
    run = paragraph.add_run(text)
    set_font(run, "Microsoft YaHei", size, bold)
    return run


def style_paragraph(paragraph, before=0, after=4, line=1.12) -> None:
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = line


def add_heading(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph(style="Heading 1")
    style_paragraph(paragraph, before=5, after=3, line=1.0)
    add_text(paragraph, text, bold=True, size=12.5)
    paragraph.paragraph_format.keep_with_next = True


def add_body(doc: Document, text: str, after=4) -> None:
    paragraph = doc.add_paragraph()
    style_paragraph(paragraph, after=after)
    add_text(paragraph, text)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.width = Inches(widths[index])
        set_cell_fill(cell, BLUE)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style_paragraph(paragraph, after=0, line=1.0)
        run = paragraph.add_run(header)
        set_font(run, "Microsoft YaHei", 9.0, bold=True, color="FFFFFF")
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cell = cells[index]
            cell.width = Inches(widths[index])
            if row_index % 2:
                set_cell_fill(cell, PALE)
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if index == 1 else WD_ALIGN_PARAGRAPH.LEFT
            style_paragraph(paragraph, after=0, line=1.0)
            run = paragraph.add_run(str(value))
            set_font(run, "Microsoft YaHei", 8.6)
    spacer = doc.add_paragraph()
    style_paragraph(spacer, after=1)


def build() -> Path:
    data = json.loads(NUMBERS.read_text(encoding="utf-8"))
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.58)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)

    styles = doc.styles
    for style_name in ("Normal", "Title", "Heading 1"):
        style = styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.color.rgb = RGBColor(0, 0, 0)
        remove_paragraph_borders(style)

    title = doc.add_paragraph(style="Title")
    remove_paragraph_borders(title)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_paragraph(title, after=2, line=1.0)
    add_text(title, "分子胶非结构化阴性证据项目进展", bold=True, size=18)
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_paragraph(meta, after=6, line=1.0)
    add_text(meta, f"胤龙  {data['date']}", size=9.5)

    add_heading(doc, "目前在解决什么问题")
    add_body(doc, "分子胶论文往往详细展示有效化合物，却只在正文或图注中简短描述失败实验。本项目把这些已经做过、但没有达到预期效果的实验恢复成可追溯记录，再检验它们是否能帮助模型认识分子胶的作用边界。")
    flow = doc.add_paragraph()
    flow.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_paragraph(flow, after=5, line=1.0)
    add_text(flow, "正文阴性  →  对象和条件恢复  →  引用核对与实验归并  →  RAG或结构化预测  →  对照评价", bold=True, size=9.6)

    add_heading(doc, "管线和数据")
    add_table(
        doc,
        ["阶段", "数量", "含义"],
        [
            ["论文库存", f"{data['inventory_papers']}篇", "当前分子胶来源清单"],
            ["完成正文扫描", f"{data['scanned_papers']}篇", "已完成句段扫描和候选发现"],
            ["进入双审与裁定", f"{data['reviewed_candidates']}条", "原始候选与后续恢复记录"],
            ["裁定为可靠", f"{data['reliable_records']}条", "对象、终点、方向、条件和出处受支持"],
            ["正式模型用途数据", f"{data['formal_negative_records']}条", f"覆盖{data['formal_negative_dois']}篇论文和{data['formal_negative_experiments']}个独立实验"],
        ],
        [1.45, 0.9, 4.75],
    )
    add_body(doc, "每条记录保留论文、化合物、靶标、实验终点、观察方向、条件、引用位置和修正历史。同一实验在正文和图注中的重复叙述只计一个实验。", after=3)

    doc.add_page_break()
    add_heading(doc, "利用实验结果")
    add_table(
        doc,
        ["实验", "主要结果", "当前认识"],
        [
            ["直接证据RAG", "恢复0.897；原文0.799；结构化0.291", "直接对应证据时，恢复记录便于定位答案"],
            ["提高难度RAG", "恢复0.404；原文0.673；结构化0.327", "优于数据库，但压缩会丢失比较对象和条件"],
            ["Qwen3 0.6B LoRA", "41/57；41/57；42/57；41/57", "平衡阴性微调没有显示增量"],
            ["MG2Act回归", "ExtraTrees MAE 0.0959；语言模型0.2895", "结构化X到Y任务更适合任务专用模型"],
            ["阴性平衡分类", "恢复组误报26%–40%；结构化组61%–91%", "恢复阴性减少了过度阳性判断"],
        ],
        [1.35, 2.3, 3.45],
    )
    add_body(doc, "提高难度RAG中，恢复证据相对结构化资料提高0.063，95%区间为0.025至0.107；原文检索仍更强。传统分类使用54个阴性实体单元，来自41个实验和23篇论文。恢复阴性组的准确率提高1.1至3.6个百分点，宏F1提高0.064至0.116；AUROC下降0.015至0.037，增量主要体现为减少阴性误报。", after=3)

    add_heading(doc, "三个具体案例")
    cases = [
        ("β-catenin降解", "恢复证据组得分1.0，结构化资料和背景材料均为0.333。正文阴性补足了数据库没有表达的突变体边界。"),
        ("E7820与线粒体呼吸", "原文组得分1.0，恢复证据组为0.333。压缩记录遗漏比较对象和条件，模型无法完整回答。"),
        ("LXH-3-71与PHGDH", "四个语言模型组都把酶抑制问题误答成蛋白降解，加入阴性LoRA没有解决终点串用。"),
    ]
    for index, (name, explanation) in enumerate(cases, start=1):
        paragraph = doc.add_paragraph()
        style_paragraph(paragraph, after=2, line=1.08)
        add_text(paragraph, f"{index}. {name}：", bold=True, size=9.8)
        add_text(paragraph, explanation, size=9.8)

    add_heading(doc, "当前结论和下一步")
    add_body(doc, "提取管线已经形成带出处、可复核、可归并的正文阴性证据。恢复证据对RAG有局部增量，但不能替代原文；小参数语言模型LoRA没有显示收益；传统模型更适合MG2Act结构化预测。把恢复阴性加入传统分类训练后，模型对真实阴性实验的误报明显下降，这与阴性数据帮助模型认识作用边界的假设一致。", after=3)
    add_body(doc, "下一步扩展高置信化合物—靶标映射，并为结构化阳性补充可比较的剂量、时间和细胞条件。共享文档持续记录新增数据、实验设计、结果和失败案例。", after=0)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_paragraph(footer, after=0, line=1.0)
    add_text(footer, "胤龙  分子胶非结构化阴性证据项目进展", size=8.0)
    doc.core_properties.author = "胤龙"
    doc.core_properties.title = "分子胶非结构化阴性证据项目进展"
    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())

