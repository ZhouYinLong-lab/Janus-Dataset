"""Check that the concise Markdown and DOCX use the frozen experiment numbers."""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document


ROOT = Path(__file__).parent


def main() -> None:
    data = json.loads((ROOT / "shared_update_numbers.json").read_text(encoding="utf-8"))
    markdown = (ROOT / "共享进展_分子胶非结构化阴性证据.md").read_text(encoding="utf-8")
    document = Document(ROOT / "分子胶非结构化阴性证据共享进展.docx")
    docx_text = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    )
    required = [
        str(data["inventory_papers"]), str(data["scanned_papers"]),
        str(data["reviewed_candidates"]), str(data["reliable_records"]),
        str(data["formal_negative_records"]), str(data["formal_negative_experiments"]),
        "0.897", "0.799", "0.404", "0.673", "0.327",
        "0.0959", "0.2895", "41/57", "42/57",
        "54", "26%", "40%", "61%", "91%",
    ]
    for value in required:
        if value not in markdown:
            raise AssertionError(f"Markdown missing frozen value: {value}")
        if value not in docx_text:
            raise AssertionError(f"DOCX missing frozen value: {value}")
    forbidden = ["专家金标", "全面提升", "阴性数据普遍无用", "找不到原文", "HTML"]
    for value in forbidden:
        if value in markdown or value in docx_text:
            raise AssertionError(f"forbidden wording present: {value}")
    if len(document.tables) != 2:
        raise AssertionError(f"expected two compact tables, found {len(document.tables)}")
    print("shared update consistency ok")


if __name__ == "__main__":
    main()
