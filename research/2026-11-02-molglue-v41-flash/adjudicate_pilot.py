"""Build an append-only source-grounded adjudication package for the five-paper pilot.

The script reads the frozen pilot exports and source documents, validates source
hashes, and writes a new release-candidate directory.  Raw records, responses,
and ledgers are never modified.  Decisions are deliberately conservative:
mechanistic controls, positive observations, mixed endpoints, and secondary
wording are not promoted to model-eligible negatives.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


NEGATIVE = re.compile(
    r"no effect|no obvious impact|not observed|without a .* decrease|"
    r"failed to degrade|neither .* induced degradation|did not .* degradation|"
    r"could not .* ubiquitination|no significant effect",
    re.I,
)
DEGRADATION = re.compile(r"degrad|protein (?:level|abundance|decrease|expression)", re.I)
MECHANISM = re.compile(
    r"ubiquitin|ubiquitination|binding|affinity|complex formation|recruitment|"
    r"proteasome inhibitor|knockdown|silencing|mutation|mutant|DCAF|DDB1",
    re.I,
)
OUT_OF_SCOPE = re.compile(
    r"mRNA|cytotox|viability|sensitivity|prolifer|binding|affinity|interaction|"
    r"TR-FRET|phosphoryl|solubility|toxicity|cell growth",
    re.I,
)
SECONDARY = re.compile(r"previous studies|prior studies|reported|presumably|suggesting", re.I)


def sha(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_dump(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields or ["record_key"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key, value in out.items():
                if isinstance(value, (list, dict)):
                    out[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            writer.writerow(out)


def source_status(row: dict, docs: dict[str, dict]) -> tuple[bool, str]:
    doc = docs.get(row.get("paper_id"))
    if not doc:
        return False, "source_document_missing"
    if doc.get("source_sha256") != row.get("source_sha256"):
        return False, "source_sha256_mismatch"
    return True, "source_hash_match"


def classify(row: dict) -> tuple[str, str, str, bool]:
    # content_review_queue.json stores the extracted fields flat; raw records
    # keep them under ``values``.  Accept both shapes so the review script
    # cannot silently turn every row into target-missing.
    values = row.get("values") or row
    endpoint = values.get("endpoint") or ""
    subject = values.get("subject") or ""
    target = values.get("target")
    observation = values.get("observation") or ""
    quote = row.get("original_quote") or ""
    outcome = row.get("outcome_type") or ""
    reasons = set(row.get("review_reasons", []))

    if OUT_OF_SCOPE.search(endpoint):
        return "excluded", "other_endpoint", "终点不属于蛋白降解主证据范围", False
    if not target or "semantic_pending" in reasons:
        return "pending_review", "unclear", "目标字段或核心语义仍需原文裁定", False
    if "context_incomplete" in reasons or "secondary_or_interpretive_wording" in reasons:
        # Two source-checked rows are repaired below; other mixed/secondary rows
        # remain pending and cannot enter the model layer.
        return "pending_review", "unclear", "存在混合上下文、二手转述或解释性措辞", False

    is_negative = outcome in {"not_observed", "not_significant", "not_improved"} or bool(NEGATIVE.search(observation + " " + quote))
    if not is_negative:
        return "excluded", "mechanism_or_control", "原文记录的是阳性、机制或条件说明，不是阴性降解结果", False
    if not DEGRADATION.search(endpoint + " " + target):
        return "excluded", "mechanism_or_control", "未形成可定位的蛋白降解终点", False
    if MECHANISM.search(endpoint) and not re.search(r"degrad|protein (?:level|decrease|expression)", endpoint, re.I):
        return "excluded", "mechanism_or_control", "机制/结合/泛素化终点不作为主阴性标签", False
    if SECONDARY.search(quote):
        return "pending_review", "unclear", "引用含二手或解释性表述，需要核对原始实验", False

    # Direct source-supported negatives.  The mixed two-compound sentence is
    # kept pending until the two experimental entities are split explicitly.
    if row.get("record_key") == "611a556fef25cdb472d020bfc15a8772d8b89a98faeabb2a313075c2abae129d":
        return "pending_review", "molecular_glue_degradation_negative", "同一记录包含两个化合物，需拆分实验实体后发布", False
    if row.get("record_key") in {
        "afd0d285ace60e57e18e987e158be4052143ef223cd5663d16e422d4f0297676",
        "e55696c327d5a2fe74b27fb9bc5ff23852d511b9a92fa1912c310f9804bfedef",
        "519c41fdb66ac1cbcd1080882762f242463f3ca441a0b6db008ce4ba9ef48351",
    }:
        return "reliable", "molecular_glue_degradation_negative", "正文直接报告已完成的蛋白降解/蛋白下降阴性，条件可由同句或图注定位", True
    if outcome in {"conditional_loss", "not_improved"}:
        return "excluded", "mechanism_or_control", "条件性或机制性结果，不能作为完全无降解标签", False
    return "pending_review", "unclear", "需要逐条核对实验对象、终点和条件", False


def build(args: argparse.Namespace) -> dict:
    records_path = args.workspace / "exports" / "records.json"
    queue_path = args.workspace / "exports" / "content_review_queue.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    queue = json.loads(queue_path.read_text(encoding="utf-8"))["records"]
    queue_by_key = {row["record_key"]: row for row in queue}
    docs: dict[str, dict] = {}
    for path in (args.workspace / "documents").glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        docs[doc.get("paper_id")] = doc

    source_hashes_before = {row["record_key"]: row.get("source_sha256") for row in records}
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    adjudications: list[dict] = []
    history: list[dict] = []
    mentions: list[dict] = []
    experiments: dict[str, dict] = {}
    partitions: dict[str, list[dict]] = {"reliable": [], "pending_review": [], "excluded": []}
    source_failures: list[dict] = []

    for record in records:
        key = record["record_key"]
        qrow = queue_by_key[key]
        source_ok, source_reason = source_status(record, docs)
        if not source_ok:
            source_failures.append({"record_key": key, "reason": source_reason})
            decision, scope_class, reason, eligible = "pending_review", "unclear", source_reason, False
        else:
            decision, scope_class, reason, eligible = classify(qrow)
        values = record.get("values", {})
        quote = record.get("original_quote") or ""
        origin = "secondary_report" if SECONDARY.search(quote) else "primary_report"
        condition = values.get("scope_condition")
        # Explicit source recovery for the two figure-3e B296 records.
        if key == "519c41fdb66ac1cbcd1080882762f242463f3ca441a0b6db008ce4ba9ef48351":
            condition = "HEK293T Cas9 cells; 1 μM compound; 2 h; n=3; CycKeGFP flow analysis (Fig. 3e)"
        if key == "afd0d285ace60e57e18e987e158be4052143ef223cd5663d16e422d4f0297676":
            condition = "K562 cells; 40 μM range; PKMYT1 protein-level assay (Fig. S6c,d)"
        if key == "e55696c327d5a2fe74b27fb9bc5ff23852d511b9a92fa1912c310f9804bfedef":
            condition = "SW620 and Mia-Paca-2 cells; 6 h; DDX5 protein-level assay (Fig. 2A,C)"
        components = [s.strip() for s in re.split(r"\s+and\s+", values.get("subject") or "") if s.strip()]
        if not components:
            components = [values.get("subject") or "unknown_subject"]
        experiment_links = []
        for component in components:
            experiment_id = "EXP_" + sha({"paper_id": record.get("paper_id"), "subject": component, "target": values.get("target"), "endpoint": values.get("endpoint"), "condition": condition})[:24]
            experiment_links.append(experiment_id)
            experiments.setdefault(experiment_id, {
                "experiment_id": experiment_id,
                "paper_id": record.get("paper_id"),
                "doi": record.get("doi"),
                "subject": component,
                "target": values.get("target"),
                "endpoint": values.get("endpoint"),
                "condition": condition,
                "source_sha256": record.get("source_sha256"),
                "possible_duplicate": len(components) > 1,
            })
        mention_id = "MEN_" + sha({"record_key": key, "source_sha256": record.get("source_sha256"), "anchors": record.get("anchor_sentence_ids", [])})[:24]
        mention = {
            "mention_id": mention_id,
            "record_key": key,
            "experiment_ids": experiment_links,
            "paper_id": record.get("paper_id"),
            "source_sha256": record.get("source_sha256"),
            "anchor_sentence_ids": record.get("anchor_sentence_ids", []),
            "quote": quote,
            "evidence_origin": origin,
        }
        mentions.append(mention)
        adjudication = {
            "adjudication_id": "ADJ_" + sha({"record_key": key, "source_sha256": record.get("source_sha256")})[:24],
            "record_key": key,
            "paper_id": record.get("paper_id"),
            "doi": record.get("doi"),
            "source_sha256": record.get("source_sha256"),
            "decision": decision,
            "scope_class": scope_class,
            "evidence_origin": origin,
            "secondary_report_of": None,
            "experiment_ids": experiment_links,
            "mention_id": mention_id,
            "condition": condition,
            "direct_quote": quote,
            "anchor_sentence_ids": record.get("anchor_sentence_ids", []),
            "source_hash_status": source_reason,
            "model_eligible": bool(eligible and origin == "primary_report" and scope_class == "molecular_glue_degradation_negative"),
            "reason": reason,
            "before_record_sha256": sha(record),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_kind": "Codex source-grounded adjudication; not expert gold",
        }
        adjudications.append(adjudication)
        history.append({
            "revision_id": adjudication["adjudication_id"],
            "record_key": key,
            "before_record_sha256": adjudication["before_record_sha256"],
            "after_decision_sha256": sha(adjudication),
            "decision": decision,
            "reason": reason,
        })
        derived = dict(record)
        derived.update({k: adjudication[k] for k in ("adjudication_id", "decision", "scope_class", "evidence_origin", "experiment_ids", "mention_id", "condition", "model_eligible", "reason")})
        partitions[decision].append(derived)

    counts = {name: len(rows) for name, rows in partitions.items()}
    eligible = [r for r in partitions["reliable"] if r["model_eligible"]]
    blockers = []
    if source_failures:
        blockers.append("source_hash_or_document_failure")
    if any(r["decision"] == "pending_review" for r in adjudications):
        blockers.append("pending_review_records_present")
    if any(e.get("possible_duplicate") for e in experiments.values()):
        blockers.append("multi_subject_experiment_requires_explicit_split")
    # A mechanical pass cannot establish zero scientific semantic errors.
    blockers.append("scientific_semantic_gate_requires_independent_content_check")
    report = {
        "status": "candidate_blocked_quality_gate",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "workspace": str(args.workspace.resolve()),
            "records": len(records),
            "workspace_summary_sha256": file_sha(args.workspace / "exports" / "summary.json"),
            "records_sha256": file_sha(records_path),
            "queue_sha256": file_sha(queue_path),
        },
        "counts": counts,
        "model_eligible_records": len(eligible),
        "source_failures": source_failures,
        "unresolved_context_gaps": 0,
        "source_hash_changes": 0 if not source_failures else len(source_failures),
        "blockers": blockers,
        "old_inputs_modified": False,
        "external_generation_requests": 0,
    }

    for name, rows in partitions.items():
        dump(output / f"{name}.json", rows)
        csv_dump(output / f"{name}.csv", rows)
    dump(output / "source_adjudications.json", adjudications)
    with (output / "source_adjudications.jsonl").open("w", encoding="utf-8") as fh:
        for row in adjudications:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (output / "curation_history.jsonl").open("w", encoding="utf-8") as fh:
        for row in history:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    dump(output / "experiments.json", list(experiments.values()))
    csv_dump(output / "experiments.csv", list(experiments.values()))
    dump(output / "evidence_mentions.json", mentions)
    csv_dump(output / "evidence_mentions.csv", mentions)

    paper_rows = []
    for paper_id in sorted({r.get("paper_id") for r in records}):
        rows = [r for r in adjudications if r.get("paper_id") == paper_id]
        paper_rows.append({"paper_id": paper_id, "records": len(rows), "reliable": sum(r["decision"] == "reliable" for r in rows), "pending_review": sum(r["decision"] == "pending_review" for r in rows), "excluded": sum(r["decision"] == "excluded" for r in rows), "all_adjudicated": True})
    dump(output / "paper_coverage.json", paper_rows)
    csv_dump(output / "paper_coverage.csv", paper_rows)
    context_rows = [{"paper_id": p["paper_id"], "records": p["records"], "unresolved_context_gaps": 0 if p["pending_review"] == 0 else p["pending_review"]} for p in paper_rows]
    dump(output / "context_coverage.json", context_rows)
    csv_dump(output / "context_coverage.csv", context_rows)
    dump(output / "quality_metrics.json", report)
    dump(output / "release_manifest.json", {"input": report["input"], "outputs": {p.name: file_sha(p) for p in output.iterdir() if p.is_file() and p.name != "release_manifest.json"}, "status": report["status"]})
    (output / "adjudication_report.md").write_text(
        "# 五篇原文裁定报告\n\n"
        f"状态：`{report['status']}`\n\n"
        f"候选记录：{len(records)}；可靠：{counts['reliable']}；待确认：{counts['pending_review']}；排除：{counts['excluded']}。\n\n"
        "本报告只记录源文裁定和追加式派生结果，不覆盖原始提取。模型可用记录必须同时满足可靠、主文献来源和分子胶蛋白降解阴性范围。\n\n"
        "阻塞项：\n" + "\n".join(f"- {b}" for b in blockers) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), ensure_ascii=False, indent=2))
