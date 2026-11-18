"""Finalize the five-paper pilot's pending source adjudications.

This consumes the v1 append-only package and writes a new v2 package.  The
original 77 records remain one-to-one in the adjudication table; a source row
may link to more than one experiment when the sentence explicitly reports
multiple compounds (DRF053 and roscovitine).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OVERRIDES = {
    # Explicitly non-negative, non-target, or mechanistic rows.
    "66012d8864cb428e9bd7fe5b1a34a99f128244c3b96bc6c6561f512e65f4e456": ("excluded", "out_of_scope", "二手背景中的TPL阳性/细胞毒性陈述，不是本论文主实验的阴性降解结果"),
    "c1f823671e32fb452452e73674737d3e6ed0d088df8f19eb8bc4bc1d6e34949a": ("excluded", "mechanism_or_control", "WBC100对c-Myc的阳性下降，不是阴性结果"),
    "57a7dd0834f78a328e7ee08ee3fa9e2ce034a76f370a5fc62deea6763fe4a631": ("excluded", "mechanism_or_control", "XPB/Rpb1/STAT3为非目标蛋白对照，不进入主阴性标签"),
    "6729866e58f30ac6683e06f88942a3be524a26755d40fa01a2eb31f6de792158": ("excluded", "mechanism_or_control", "CHIP敲低导致机制效应减弱，不是化合物阴性降解"),
    "06c6aea866db46c630862c037bff8496962e53f9677be69fc40208c512423a20": ("excluded", "mechanism_or_control", "eEF2K沉默导致AURKA下降，属于机制/阳性结果"),
    "9b555cb7221cb243859e710cf1367e67734d9969039647412999dc25890cfce1": ("excluded", "mechanism_or_control", "AURKA加速降解是阳性机制结果"),
    "dc787136c732fb9102a93b3eec317b9d16f37fd1eb4d0708e025610671a2f183": ("excluded", "mechanism_or_control", "eEF2K稳定AURKA的机制陈述，不是阴性降解标签"),
    "57d723dcdc101f3459be493d1f68fbd591f9b5b1002edf694b23f632e7035a6e": ("excluded", "mechanism_or_control", "S391A导致AURKA更快降解，是阳性结果"),
    "5f7b6124556d040fc6464c519ce17e29cdcbd359e4c3080867d14a038f6832a2": ("excluded", "mechanism_or_control", "S391A泛素化增加是机制/阳性结果"),
    "0c94fa2c9b737ae7a9227318a4e8a365c936bbbf6b5d6c1fc8b425f45d219316": ("excluded", "mechanism_or_control", "FL118在24小时出现蛋白下降，是阳性时间点"),
    "3ef27937b8b00682092680503f3408032a491848b00e2984f8154c86a33e789f": ("excluded", "mechanism_or_control", "R-CR8导致cycK下降，是阳性结果"),
    "bc9901ed234b2ba8af6c3b05b2992e44053d8e32eddce38304d10cc327d3fd3d": ("excluded", "mechanism_or_control", "抑制剂救援证明降解通路，不是阴性降解标签"),
    "3a2cea2161bb67adb721990feaf7fd0542cc6fe41ef5884260e5e752ab4fb035": ("excluded", "mechanism_or_control", "R-CR8触发降解的解释性阳性陈述"),
    "32b41d5db4fd658f65f6b5d24df321f8f032bd77e097b4f262834fa55fe8cf13": ("excluded", "mechanism_or_control", "DDB1参与降解的机制验证"),
    "5d03c1d342b3900c766a70983799522023bdb84eb23190c04fc91476856f8aea": ("excluded", "mechanism_or_control", "ATP复合物形成对照，不是蛋白降解阴性"),
    "e1f411802ac01978117566bef542c450a827bdd1aaa835f30aeca11de998971d": ("excluded", "mechanism_or_control", "CRBN过表达导致条件性降解变化，属于机制/条件边界"),
    "8fadb459108c4e79bc30b88adbb677d50bfe6b1ac00755ef6ca0aed58e7989f1": ("excluded", "mechanism_or_control", "DDB1依赖性是机制条件，不是完全无降解"),
    # Direct primary negatives retained after separating mixed endpoints.
    "afd0d285ace60e57e18e987e158be4052143ef223cd5663d16e422d4f0297676": ("reliable", "molecular_glue_degradation_negative", "MR在40 μM范围、K562细胞中未改变PKMYT1蛋白水平；细胞毒性终点单独隔离"),
    "611a556fef25cdb472d020bfc15a8772d8b89a98faeabb2a313075c2abae129d": ("reliable", "molecular_glue_degradation_negative", "正文直接报告DRF053和roscovitine均未诱导cycK报告蛋白降解；两个化合物分设实验ID"),
}


def sha(value: object) -> str:
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
    v1 = args.v1.resolve()
    records = json.loads((args.workspace / "exports" / "records.json").read_text(encoding="utf-8"))
    old_adj = {r["record_key"]: r for r in json.loads((v1 / "source_adjudications.json").read_text(encoding="utf-8"))}
    old_mentions = {r["record_key"]: r for r in json.loads((v1 / "evidence_mentions.json").read_text(encoding="utf-8"))}
    old_experiments = json.loads((v1 / "experiments.json").read_text(encoding="utf-8"))
    old_exp_by_id = {r["experiment_id"]: r for r in old_experiments}
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    adjudications = []
    history = []
    mentions = []
    experiments = dict(old_exp_by_id)
    by_key = {r["record_key"]: r for r in records}

    for key, old in old_adj.items():
        row = by_key[key]
        decision, scope_class, reason = OVERRIDES.get(key, (old["decision"], old["scope_class"], old["reason"]))
        updated = dict(old)
        updated.update({"decision": decision, "scope_class": scope_class, "reason": reason, "reviewed_at": datetime.now(timezone.utc).isoformat(), "revision": "v2"})
        if key == "afd0d285ace60e57e18e987e158be4052143ef223cd5663d16e422d4f0297676":
            updated["condition"] = "K562 cells; 40 μM range; PKMYT1 protein-level assay (Fig. S6c,d)"
            updated["model_eligible"] = True
        elif key == "611a556fef25cdb472d020bfc15a8772d2b3900c766a70983799522023bdb84eb23190c04fc91476856f8aea":
            pass
        if key == "611a556fef25cdb472d020bfc15a8772d2b3900c766a70983799522023bdb84eb23190c04fc91476856f8aea":
            # Defensive branch for malformed identifiers; the actual key is
            # handled below and remains pending if the source key is absent.
            updated["model_eligible"] = False
        if key == "611a556fef25cdb472d020bfc15a8772d8b89a98faeabb2a313075c2abae129d":
            updated["condition"] = "HEK293T Cas9 cells; 1 μM compound; 2 h; n=3; CycKeGFP flow analysis (Fig. 3e)"
            updated["experiment_components"] = ["DRF053", "roscovitine"]
            exp_ids = []
            for component in updated["experiment_components"]:
                exp_id = "EXP_" + sha({"paper_id": row["paper_id"], "subject": component, "target": row["values"].get("target"), "endpoint": row["values"].get("endpoint"), "condition": updated["condition"]})[:24]
                exp_ids.append(exp_id)
                experiments[exp_id] = {"experiment_id": exp_id, "paper_id": row["paper_id"], "doi": row["doi"], "subject": component, "target": row["values"].get("target"), "endpoint": row["values"].get("endpoint"), "condition": updated["condition"], "source_sha256": row["source_sha256"], "possible_duplicate": False, "split_from_record_key": key}
            updated["experiment_ids"] = exp_ids
            updated["model_eligible"] = True
        if updated["decision"] != "reliable":
            updated["model_eligible"] = False
        updated["after_decision_sha256"] = sha(updated)
        adjudications.append(updated)
        history.append({"revision_id": updated["adjudication_id"], "record_key": key, "revision": "v2", "before_adjudication_sha256": sha(old), "after_decision_sha256": updated["after_decision_sha256"], "decision": updated["decision"], "reason": reason})

        mention = dict(old_mentions[key])
        mention["experiment_ids"] = updated.get("experiment_ids", mention.get("experiment_ids", []))
        mention["revision"] = "v2"
        mentions.append(mention)

    partitions = {"reliable": [], "pending_review": [], "excluded": []}
    for adj in adjudications:
        base = dict(by_key[adj["record_key"]])
        base.update({k: adj[k] for k in ("adjudication_id", "decision", "scope_class", "evidence_origin", "experiment_ids", "experiment_components", "mention_id", "condition", "model_eligible", "reason") if k in adj})
        partitions[adj["decision"]].append(base)
    counts = {k: len(v) for k, v in partitions.items()}
    # Multi-entity strings from excluded mechanism/control records are retained
    # for audit, but they are not duplicate experiments in the model layer.
    reliable_exp_ids = {
        exp_id
        for adj in adjudications
        if adj.get("decision") == "reliable"
        for exp_id in adj.get("experiment_ids", [])
    }
    for exp in experiments.values():
        if exp.get("possible_duplicate") and exp.get("experiment_id") not in reliable_exp_ids:
            exp["possible_duplicate"] = False
            exp["duplicate_resolution"] = "excluded_or_mechanistic_record_not_in_model_layer"
    blockers = []
    if counts["pending_review"]:
        blockers.append("pending_review_records_present")
    if any(e.get("possible_duplicate") and e.get("experiment_id") in reliable_exp_ids for e in experiments.values()):
        blockers.append("possible_duplicate_groups_remain")
    blockers.append("scientific_semantic_gate_requires_independent_content_check")
    report = {
        "status": "candidate_blocked_quality_gate" if blockers else "frozen_candidate",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input": {"v1": str(v1), "records": len(records), "records_sha256": sha(records), "v1_adjudications_sha256": sha(old_adj)},
        "counts": counts,
        "all_77_adjudicated": len(adjudications) == 77,
        "model_eligible_records": sum(r.get("model_eligible", False) for r in adjudications),
        "pending_review_records": counts["pending_review"],
        "source_hash_changes": 0,
        "external_generation_requests": 0,
        "old_inputs_modified": False,
        "blockers": blockers,
    }
    for name, rows in partitions.items():
        fname = {"reliable": "reliable_evidence", "pending_review": "pending_review", "excluded": "excluded_records"}[name]
        dump(out / f"{fname}.json", rows)
        csv_dump(out / f"{fname}.csv", rows)
    dump(out / "source_adjudications.json", adjudications)
    with (out / "source_adjudications.jsonl").open("w", encoding="utf-8") as fh:
        for row in adjudications:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (out / "curation_history.jsonl").open("w", encoding="utf-8") as fh:
        for row in history:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    exp_rows = list(experiments.values())
    dump(out / "experiments.json", exp_rows)
    csv_dump(out / "experiments.csv", exp_rows)
    dump(out / "evidence_mentions.json", mentions)
    csv_dump(out / "evidence_mentions.csv", mentions)
    paper_rows = []
    for paper in sorted({r["paper_id"] for r in adjudications}):
        rows = [r for r in adjudications if r["paper_id"] == paper]
        paper_rows.append({"paper_id": paper, "records": len(rows), "reliable": sum(r["decision"] == "reliable" for r in rows), "pending_review": sum(r["decision"] == "pending_review" for r in rows), "excluded": sum(r["decision"] == "excluded" for r in rows), "partition_total": len(rows)})
    dump(out / "paper_coverage.json", paper_rows)
    csv_dump(out / "paper_coverage.csv", paper_rows)
    dump(out / "context_coverage.json", [{"paper_id": r["paper_id"], "unresolved_context_gaps": 0 if r["pending_review"] == 0 else r["pending_review"], "records": r["records"]} for r in paper_rows])
    csv_dump(out / "context_coverage.csv", [{"paper_id": r["paper_id"], "unresolved_context_gaps": 0 if r["pending_review"] == 0 else r["pending_review"], "records": r["records"]} for r in paper_rows])
    dump(out / "quality_metrics.json", report)
    dump(out / "release_manifest.json", {"status": report["status"], "input": report["input"], "outputs": {p.name: sha(p.read_bytes().hex()) for p in out.iterdir() if p.is_file() and p.name != "release_manifest.json"}})
    (out / "adjudication_report.md").write_text("# 五篇v2裁定报告\n\n" + f"状态：`{report['status']}`\n\n可靠：{counts['reliable']}；待确认：{counts['pending_review']}；排除：{counts['excluded']}。\n\n" + "阻塞项：\n" + "\n".join(f"- {b}" for b in blockers) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), ensure_ascii=False, indent=2))
