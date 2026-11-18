"""Build a downstream bundle from frozen v1 negatives and existing reviewed material.

This is deliberately offline.  The 24 pending positive candidates in frozen v1 are
not admitted; positives/background/structured rows come from the prior reviewed
bundle and are retained with their original provenance.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from common import digest, doi, fresh, read, seal, sha, write


def render_negative(r):
    facts = r.get("facts", {})
    observations = facts.get("observations") or []
    values = observations[0].get("values", {}) if observations else {}
    if not values:
        values = (r.get("observation") or {}).get("values", {})
    conditions = r.get("conditions") or {}
    outcome_type = (observations[0].get("outcome_type") if observations else
                    (r.get("observation") or {}).get("outcome_type"))
    return json.dumps({
        "values": values,
        "outcome_type": outcome_type,
        "conditions": conditions,
        "original_quote": (r.get("discovery") or {}).get("quote"),
    }, ensure_ascii=False)


def build(old_bundle, release, out, questions=None, seed=20261027):
    old_bundle, release, out = map(Path, (old_bundle, release, out))
    old_rows = read(old_bundle / "evidence.json")
    old_raw = read(old_bundle / "raw.json")
    frozen = read(release / "reliable_evidence.json")
    eligibility = {x["evidence_id"]: x for x in read(release / "model_eligibility.json")}
    split_doc = read(release / "splits.json")
    paper_splits_by_id = dict(split_doc["papers"])
    # Preserve the prior evaluation split for the existing question set.  The
    # frozen-v1 paper split is used only when a DOI was not already assigned in
    # the reviewed downstream material.
    old_splits_by_doi = {doi(r.get("doi")): r.get("split") for r in old_rows if r.get("doi") and r.get("split")}

    def normalized_split(value):
        return "val" if value == "validation" else value

    def split_for(row):
        d = doi(row.get("doi"))
        if d in old_splits_by_doi:
            return normalized_split(old_splits_by_doi[d])
        return normalized_split(paper_splits_by_id.get(row.get("paper_id"), row.get("split", "train")))

    # Existing reviewed positives/background/structured are the only positive pool.
    keep_old = [r for r in old_rows if r.get("kind") in {"positive", "background", "structured"}]
    if not keep_old:
        raise ValueError("Existing reviewed positive/background/structured pool is empty")
    if any(r.get("kind") == "positive" and r.get("review_status") not in {None, "reliable"}
           for r in keep_old):
        raise ValueError("Existing positive pool contains unreviewed rows")

    negatives = []
    for r in frozen:
        eid = r.get("record_id") or r.get("evidence_id")
        e = eligibility.get(eid)
        if not e or e.get("rag") is not True:
            continue
        quote = ((r.get("discovery") or {}).get("quote") or
                 ((r.get("evidence_spans") or [{}])[0].get("quote")))
        if not quote:
            raise ValueError(f"Frozen negative missing quote: {eid}")
        split = split_for(r)
        obs = ((r.get("facts") or {}).get("observations") or [{}])[0]
        if not obs:
            obs = r.get("observation") or {}
        values = obs.get("values", {})
        outcome_type = obs.get("outcome_type")
        field_evidence = obs.get("evidence", {})
        if not values:
            values = (r.get("observation") or {}).get("values", {})
            outcome_type = (r.get("observation") or {}).get("outcome_type")
            field_evidence = (r.get("observation") or {}).get("evidence", {})
        if not isinstance(field_evidence, list):
            field_evidence = r.get("evidence_spans") or []
        negatives.append({
            "record_key": eid,
            "evidence_id": "frozen-v1:" + eid,
            "paper_id": r.get("paper_id"),
            "doi": r.get("doi"),
            "source_sha256": r.get("source_sha256"),
            "source_path": r.get("source_path"),
            "values": values,
            "outcome_type": outcome_type,
            "conditions": r.get("conditions"),
            "original_quote": quote,
            "quote": quote,
            "field_evidence": field_evidence,
            "content_decision": "reliable",
            "review_kind": "frozen_v1_dual_review_adjudicated",
            "scope_class": r.get("scope_class"),
            "evidence_origin": r.get("evidence_origin"),
            "experiment_id": r.get("experiment_id"),
            "split": split,
            "group_id": digest(["doi", doi(r.get("doi"))]),
            "training_allowed": e.get("training") is True,
            "rag_allowed": True,
            "kind": "negative",
            "text": render_negative(r),
            "source_release": str(release.resolve()),
        })

    # Normalize old rows without changing their source content.  Frozen v1 split
    # assignments take precedence for papers present in v1; other old papers retain
    # their reviewed split.  Group IDs are DOI-level to prevent paper leakage.
    rows = []
    for r in keep_old:
        row = dict(r)
        row["split"] = split_for(row)
        row["group_id"] = digest(["doi", doi(row.get("doi"))]) if row.get("doi") else digest([row.get("source_sha256")])
        row["rag_allowed"] = True
        row["source_bundle"] = str(old_bundle.resolve())
        rows.append(row)
    rows.extend(negatives)

    ids = [r.get("evidence_id") for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evidence IDs after merge")
    if not {"positive", "negative", "background"} <= {r.get("kind") for r in rows}:
        raise ValueError("Bundle lacks one of positive/negative/background kinds")
    for r in rows:
        if r.get("kind") == "negative" and not (r.get("source_sha256") and r.get("original_quote")):
            raise ValueError("Negative missing source identity or quote")

    raw = []
    for r in old_raw:
        row = dict(r)
        row["split"] = split_for(row) if row.get("doi") else row.get("split", "retrieval_only")
        row["group_id"] = digest(["doi", doi(row.get("doi"))]) if row.get("doi") else row.get("group_id")
        raw.append(row)

    out = fresh(out)
    write(out / "evidence.json", rows)
    write(out / "raw.json", raw)
    write(out / "admission_issues.json", [])
    summary = {
        "admitted": len(rows),
        "old_reviewed_nonnegative": len(keep_old),
        "frozen_v1_negative": len(negatives),
        "pending_positive_candidates_excluded": len(read(release / "positive_evidence.json")),
        "kind_counts": dict(Counter(r.get("kind") for r in rows)),
        "split_counts": dict(Counter(r.get("split") for r in rows)),
        "training_allowed_counts": dict(Counter(r.get("kind") for r in rows if r.get("training_allowed"))),
        "rag_rows": sum(r.get("rag_allowed") is True for r in rows),
        "source_groups": len({r.get("group_id") for r in rows}),
        "seed": seed,
        "generation_requests": 0,
        "expert_gold": False,
        "positive_policy": "Existing reviewed positive rows only; frozen v1 pending candidates excluded.",
        "negative_policy": "Frozen v1 reliable primary molecular-glue degradation negatives with rag eligibility.",
    }
    write(out / "summary.json", summary)
    inputs = [old_bundle / "evidence.json", old_bundle / "raw.json",
              release / "reliable_evidence.json", release / "model_eligibility.json",
              release / "splits.json", release / "positive_evidence.json"]
    if questions:
        inputs.append(Path(questions))
    seal(out, inputs, {"artifact": "frozen_v1_downstream_bundle", "version": 1,
                       "external_generation_requests": 0})
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--old-bundle", required=True, type=Path)
    p.add_argument("--release", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--questions", type=Path)
    print(json.dumps(build(**vars(p.parse_args())), ensure_ascii=False, indent=2))
