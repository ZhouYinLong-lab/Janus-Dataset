"""Validate and structure the public B204 supporting-information PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


EXPECTED = {
    "size": 10891786,
    "md5": "d008947e9c85dcd9717f7db0557fe631",
    "sha256": "95ff327539528e5fb96307182404a20c7f74d8ef02f850ac3cbac7227a469048",
    "resource_doi": "10.1021/acsmedchemlett.4c00250",
    "supplement_doi": "10.1021/acsmedchemlett.4c00250.s001",
    "figshare_id": 27004095,
    "figshare_file_id": 49149912,
}

TABLE_COMPOUNDS = ["7", "8", "9", "10", "11", "12", "13", "14", "15", "16",
                   "17", "18", "19", "20", "21", "22", "SJ3149", "23", "24"]
GSPT1_GT10 = {"8", "13", "14", "15", "16", "18", "20", "21", "22", "SJ3149", "23", "24"}
GSPT1_ND = set(TABLE_COMPOUNDS) - GSPT1_GT10


def _experiment_id(compound: str, target: str) -> str:
    return f"B204:supplement:{compound}:{target}:24h"


def _digest(path: Path, name: str):
    h = hashlib.new(name)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(pdf: Path, out: Path):
    pdf = Path(pdf).resolve()
    if pdf.stat().st_size != EXPECTED["size"]:
        raise ValueError("supplement_size_mismatch")
    if _digest(pdf, "md5") != EXPECTED["md5"] or _digest(pdf, "sha256") != EXPECTED["sha256"]:
        raise ValueError("supplement_hash_mismatch")
    reader = PdfReader(str(pdf))
    if len(reader.pages) != 33:
        raise ValueError("supplement_page_count_mismatch")
    page5 = reader.pages[4].extract_text() or ""
    page7 = reader.pages[6].extract_text() or ""
    for needle in ("Table S1", "GSPT1", "IKZF1", "24 hrs endpoint"):
        if needle not in page5:
            raise ValueError("table_s1_marker_missing:" + needle)
    for needle in ("Figure S5", "CK1", "IKZF1", "24 hours"):
        if needle not in page7:
            raise ValueError("figure_s5_marker_missing:" + needle)
    rows = []
    for compound in TABLE_COMPOUNDS:
        rows.append({
            "experiment_id": _experiment_id(compound, "GSPT1"),
            "mention_id": f"B204:TableS1:{compound}:GSPT1",
            "compound": compound, "target": "GSPT1", "endpoint": "protein degradation",
            "assay": "GSPT1-HiBiT endpoint", "cell_line": "HEK293", "time": "24 h",
            "result_type": "dc50_gt_10_uM" if compound in GSPT1_GT10 else "not_determined",
            "value": ">10 uM" if compound in GSPT1_GT10 else "ND",
            "replicates": "at least 2 independent experiments", "source": "Table S1, PDF page 5",
            "model_eligible": compound in GSPT1_GT10,
        })
        rows.append({
            "experiment_id": _experiment_id(compound, "IKZF1"),
            "mention_id": f"B204:TableS1:{compound}:IKZF1",
            "compound": compound, "target": "IKZF1", "endpoint": "protein degradation",
            "assay": "IKZF1-HiBiT kinetic DC50", "cell_line": "Jurkat", "time": "24 h",
            "result_type": "dc50_gt_10_uM", "value": ">10 uM",
            "replicates": "4 technical replicates", "source": "Table S1, PDF page 5",
            "model_eligible": True,
        })
    figure_rows = [{
        "experiment_id": _experiment_id(compound, "IKZF1"),
        "mention_id": f"B204:FigureS5:{compound}:IKZF1",
        "compound": compound, "target": "IKZF1", "endpoint": "protein degradation",
        "assay": "IKZF1-HiBiT live kinetic degradation", "cell_line": "Jurkat",
        "time": "24 h", "concentration_range": "0.011-10 uM",
        "result_type": "low_degradation_boundary_not_absolute_zero",
        "source": "Figure S5B and S5E, PDF page 7", "model_eligible": True,
    } for compound in ("4", "21", "23", "24")]
    result = {
        "schema_version": 1,
        "paper_id": "B204",
        "identity": EXPECTED,
        "source": {
            "publisher_url": "https://pubs.acs.org/doi/suppl/10.1021/acsmedchemlett.4c00250/suppl_file/ml4c00250_si_001.pdf",
            "figshare_api": "https://api.figshare.com/v2/articles/27004095",
            "download_url": "https://ndownloader.figshare.com/files/49149912",
            "license": "CC BY-NC 4.0",
            "local_path": str(pdf),
        },
        "table_s1_records": rows,
        "figure_s5_records": figure_rows,
        "interpretation": {
            "dc50_gt_10_uM": "activity boundary above the tested 10 uM range; not absolute zero degradation",
            "not_determined": "not tested or not reported; not a negative experiment label",
        },
        "raw_extraction_untouched": True,
        "review_kind": "offline source audit; not expert gold",
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.pdf, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
