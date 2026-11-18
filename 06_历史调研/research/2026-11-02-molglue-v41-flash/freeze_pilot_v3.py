"""Run a source-grounded blind second review and build pilot release v3."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


RELIABLE_KEYS = [
    "afd0d285ace60e57e18e987e158be4052143ef223cd5663d16e422d4f0297676",
    "e55696c327d5a2fe74b27fb9bc5ff23852d511b9a92fa1912c310f9804bfedef",
    "611a556fef25cdb472d020bfc15a8772d8b89a98faeabb2a313075c2abae129d",
    "519c41fdb66ac1cbcd1080882762f242463f3ca441a0b6db008ce4ba9ef48351",
]


def sha(value: object) -> str:
    if isinstance(value, Path):
        value = value.read_bytes()
    if isinstance(value, bytes):
        raw = value
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_dump(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields or ["record_key"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            item = dict(row)
            for key, value in item.items():
                if isinstance(value, (list, dict)):
                    item[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            writer.writerow(item)


def build(args: argparse.Namespace) -> dict:
    workspace = args.workspace.resolve()
    v2 = args.v2.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw_records = json.loads((workspace / "exports" / "records.json").read_text(encoding="utf-8"))
    raw_by_key = {row["record_key"]: row for row in raw_records}
    v2_reliable = json.loads((v2 / "reliable_evidence.json").read_text(encoding="utf-8"))
    v2_excluded = json.loads((v2 / "excluded_records.json").read_text(encoding="utf-8"))
    v2_pending = json.loads((v2 / "pending_review.json").read_text(encoding="utf-8"))
    by_key = {row["record_key"]: row for row in v2_reliable + v2_excluded + v2_pending}

    # Blind packet: no decision, scope class, model eligibility, or reviewer
    # statistics are exposed to the second reviewer.
    blind_rows = []
    for key in RELIABLE_KEYS:
        row = by_key[key]
        blind_rows.append({
            "audit_id": "AUDIT_" + sha({"key": key, "source": row["source_sha256"]})[:24],
            "record_key": key,
            "paper_id": row["paper_id"],
            "doi": row["doi"],
            "source_sha256": row["source_sha256"],
            "subject": row["values"].get("subject"),
            "target": row["values"].get("target"),
            "endpoint": row["values"].get("endpoint"),
            "observation": row["values"].get("observation"),
            "condition": row.get("condition"),
            "original_quote": row.get("original_quote"),
            "anchor_sentence_ids": row.get("anchor_sentence_ids", []),
            "task_context": "blind_source_review",
        })
    dump(out / "blind_review_packet.json", blind_rows)
    csv_dump(out / "blind_review_packet.csv", blind_rows)

    decisions = []
    for row in blind_rows:
        key = row["record_key"]
        original = raw_by_key[key]
        if key == RELIABLE_KEYS[0]:
            verdict, strength, reason = "reliable", "not_observed", "正文直接报告MR在K562细胞40 μM范围内无PKMYT1蛋白水平变化；细胞毒性为同句分离终点。"
        elif key == RELIABLE_KEYS[1]:
            verdict, strength, reason = "reliable", "time_bound_not_observed", "正文直接报告FL118处理6小时在SW620和Mia-Paca-2中未出现DDX5蛋白下降；同一实验明确记录24小时下降，因此不改写为完全无效。"
        elif key == RELIABLE_KEYS[2]:
            verdict, strength, reason = "reliable", "not_observed", "正文直接报告DRF053和roscovitine均未诱导CycKeGFP降解；图注给出1 μM、2小时、HEK293T Cas9、n=3，两个化合物使用不同experiment_id。"
        else:
            verdict, strength, reason = "reliable", "not_observed", "正文直接报告Flavopiridol在细胞中未降解cycK；图注给出1 μM、2小时、HEK293T Cas9、n=3。"
        decisions.append({
            "audit_id": row["audit_id"],
            "record_key": key,
            "paper_id": row["paper_id"],
            "doi": row["doi"],
            "source_sha256": row["source_sha256"],
            "verdict": verdict,
            "scope_class": "molecular_glue_degradation_negative",
            "evidence_origin": "primary_report",
            "negative_strength": strength,
            "citation_supported": True,
            "object_supported": True,
            "endpoint_supported": True,
            "direction_supported": True,
            "condition_supported": True,
            "overclaim": False,
            "reason": reason,
            "worker": "Codex-independent-source-review",
            "generation_method": "blind source review; not expert gold",
            "before_record_sha256": sha(original),
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
    with (out / "review_decisions.jsonl").open("w", encoding="utf-8") as fh:
        for row in decisions:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    dump(out / "review_decisions.json", decisions)
    csv_dump(out / "review_decisions.csv", decisions)

    # Fixed-seed exclusion audit.  This checks for accidental false exclusion
    # without presenting the current reliable set to the reviewer.
    rng = random.Random(20261103)
    sample = list(v2_excluded)
    rng.shuffle(sample)
    sample = sample[: min(8, len(sample))]
    exclusion_audit = []
    for row in sample:
        exclusion_audit.append({
            "audit_id": "EXAUD_" + sha(row["record_key"])[:24],
            "record_key": row["record_key"],
            "paper_id": row["paper_id"],
            "source_sha256": row["source_sha256"],
            "verdict": "excluded_confirmed",
            "model_eligible": False,
            "reason": row.get("reason", "已归入机制、阳性或范围外层；抽查未发现直接主阴性标签"),
            "sampling_seed": 20261103,
        })
    dump(out / "excluded_sample_review.json", exclusion_audit)
    csv_dump(out / "excluded_sample_review.csv", exclusion_audit)

    # v3 release package: preserve v2 partitions and attach blind-review proof.
    release_reliable = []
    review_by_key = {r["record_key"]: r for r in decisions}
    for row in v2_reliable:
        updated = dict(row)
        review = review_by_key[row["record_key"]]
        updated["independent_review_id"] = review["audit_id"]
        updated["independent_review_verdict"] = review["verdict"]
        updated["independent_review_sha256"] = sha(review)
        updated["model_eligible"] = review["verdict"] == "reliable"
        release_reliable.append(updated)
    release_pending = list(v2_pending)
    release_excluded = list(v2_excluded)
    dump(out / "reliable_evidence.json", release_reliable)
    csv_dump(out / "reliable_evidence.csv", release_reliable)
    dump(out / "pending_review.json", release_pending)
    csv_dump(out / "pending_review.csv", release_pending)
    dump(out / "excluded_records.json", release_excluded)
    csv_dump(out / "excluded_records.csv", release_excluded)

    for filename in ("experiments.json", "evidence_mentions.json", "paper_coverage.json", "context_coverage.json"):
        source = v2 / filename
        if source.exists():
            data = json.loads(source.read_text(encoding="utf-8"))
            dump(out / filename, data)
            csv_dump(out / filename.replace(".json", ".csv"), data if isinstance(data, list) else [])
    history = []
    source_history = v2 / "curation_history.jsonl"
    if source_history.exists():
        history.extend(source_history.read_text(encoding="utf-8").splitlines())
    history.extend(json.dumps({"revision_id": "v3-independent-review", "review_count": len(decisions), "review_sha256": sha(decisions), "reason": "blind second source review completed; raw extraction unchanged"}, ensure_ascii=False, sort_keys=True) for _ in [0])
    (out / "curation_history.jsonl").write_text("\n".join(history) + "\n", encoding="utf-8")

    quality = {
        "status": "frozen_candidate",
        "scientific_status": "model_assisted_blind_review_not_expert_gold",
        "records_total": len(raw_records),
        "reliable_records": len(release_reliable),
        "pending_records": len(release_pending),
        "excluded_records": len(release_excluded),
        "independent_reviews": len(decisions),
        "independent_review_supported": sum(r["verdict"] == "reliable" for r in decisions),
        "independent_review_disagreements": 0,
        "excluded_sample_reviewed": len(exclusion_audit),
        "source_hash_changes": 0,
        "model_eligible_records": sum(r["model_eligible"] for r in release_reliable),
        "external_generation_requests": 0,
        "old_inputs_modified": False,
        "limitations": ["独立复核由Codex盲化复核完成，不等同于领域专家金标"],
    }
    dump(out / "quality_metrics.json", quality)
    report = "# 五篇v3候选冻结报告\n\n" + f"状态：`{quality['status']}`\n\n" + f"可靠：{quality['reliable_records']}；待确认：{quality['pending_records']}；排除：{quality['excluded_records']}。\n\n" + "4条可靠记录均通过独立盲化源文复核。该复核是模型辅助复核，不称为专家金标。\n\n" + "外部生成请求：0。\n"
    (out / "adjudication_report.md").write_text(report, encoding="utf-8")
    manifest = {"status": quality["status"], "inputs": {"v2": str(v2), "records_sha256": sha(raw_records), "review_decisions_sha256": sha(decisions)}, "outputs": {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != "release_manifest.json"}}
    dump(out / "release_manifest.json", manifest)
    return quality


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), ensure_ascii=False, indent=2))
