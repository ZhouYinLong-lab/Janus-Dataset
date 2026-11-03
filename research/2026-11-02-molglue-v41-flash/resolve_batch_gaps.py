"""Record offline resolutions for a completed readable-XML batch.

The decisions are append-only audit data.  Raw responses and workspace state
are never edited.  Ambiguous evidence remains pending and model-ineligible.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import read, save, sha  # noqa: E402
from sentence_export import snapshot  # noqa: E402


PARAGRAPH_DECISIONS = {
    "B201:ae941ea2a06ebb06": ("resolved_no_candidate", "introduction_and_background_only"),
    "B201:501d2215761531f3": ("resolved_no_candidate", "introduction_and_background_only"),
    "B203:5083cbfa59eef7c4": ("resolved_candidate_rejected", "mechanism_and_positive_comparison_only"),
    "B207:95054b88744d19ff": ("resolved_no_candidate", "positive_activity_and_design_discussion_only"),
    "B207:78a440ddc078c924": ("resolved_no_candidate", "design_and_positive_activity_plan_only"),
    "B209:25441c47783fdba7": ("resolved_candidate_rejected", "docking_and_ternary_complex_mechanism"),
    "B209:bc201fcc98c07d77": ("resolved_candidate_rejected", "positive_degradation_and_rescue_mechanism"),
    "B211:09196ac9ced70314": ("resolved_candidate_rejected", "methods_description_without_result"),
    "B214:34bd524995d5f143": ("resolved_candidate_rejected", "structural_mechanism_only"),
    "B223:25867be276490e75": ("resolved_candidate_rejected", "positive_degrader_mechanism"),
    "B223:be2c72ab7792c38c": ("resolved_candidate_rejected", "positive_degradation_and_ups_mechanism"),
}

CONTEXT_DECISIONS = {
    ("B203", "C:2f90872d46e74250f754a7c93048e1ed992c52cd6dd0b4802a3d9cee560b559a"):
        ("resolved_not_required", "degradation_rescue_assay_is_mechanism_control_not_main_negative"),
    ("B204", "C:a93a4df69eebc0153e9754c4f7fb6658437c2e32fd38baec9adca9022d4488f3"):
        ("pending_context", "negative_off_targets_refer_to_missing_supplementary_table_and_figure"),
    ("B211", "C:89f56b875db039fc8696055e510f5f6dfb0cc13f9a370d5f4cd477dfa715b32a"):
        ("resolved_not_required", "positive_brd4_result_does_not_enter_negative_evidence"),
    ("B212", "C:f40423cadf8ad24aeec34e3b7db2f89ebbeb06cd83a585c4240062086cb8e992"):
        ("resolved_context_in_anchor", "two_hour_condition_is_in_the_candidate_sentence; record_remains_pending"),
}


def resolve(workspace: Path, out: Path):
    workspace = Path(workspace).resolve()
    _summary, _records, audits, _failures = snapshot(workspace)
    rows = []
    seen = set()
    for audit in audits:
        if audit.get("destination") == "paragraph_coverage" and audit.get("status") not in {"has_candidates", "none_found"}:
            pid = audit["paragraph_id"]
            if pid not in PARAGRAPH_DECISIONS:
                raise ValueError(f"unclassified_paragraph:{pid}")
            status, reason = PARAGRAPH_DECISIONS[pid]
            seen.add(pid)
            rows.append({"kind": "paragraph", "paper_id": audit["paper_id"],
                         "paragraph_id": pid, "original_status": audit.get("status"),
                         "terminal_status": status, "reason": reason,
                         "source_sha256": audit.get("source_sha256"),
                         "model_eligible": False})
        elif audit.get("destination") == "optional_conditions_gap":
            key = (audit.get("paper_id"), audit.get("candidate_id"))
            if key not in CONTEXT_DECISIONS:
                raise ValueError(f"unclassified_context:{key}")
            status, reason = CONTEXT_DECISIONS[key]
            seen.add(("context", *key))
            rows.append({"kind": "context", "paper_id": key[0], "candidate_id": key[1],
                         "original_status": audit.get("status"),
                         "terminal_status": status, "reason": reason,
                         "model_eligible": False})
    expected_paragraphs = set(PARAGRAPH_DECISIONS)
    if seen & expected_paragraphs != expected_paragraphs:
        raise ValueError("paragraph_resolution_incomplete")
    expected_context = {("context", *key) for key in CONTEXT_DECISIONS}
    if (seen & expected_context) != expected_context:
        raise ValueError("context_resolution_incomplete")
    result = {"schema_version": 1, "workspace": str(workspace),
              "workspace_manifest_sha256": sha(workspace / "manifest.json"),
              "rows": rows, "raw_workspace_untouched": True,
              "model_assisted_review": "offline source audit; not expert gold"}
    save(Path(out), result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(resolve(args.workspace, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
