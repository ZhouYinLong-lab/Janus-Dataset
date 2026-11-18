"""Freeze the current MolGlueDB source inventory for the v4.1 extraction run.

This script deliberately keeps the historical inventory untouched.  It copies the
193 identity records and readable source files into a versioned local workspace,
records hashes, and records the unresolved difference between the paper's stated
241-publication scope and the export-linked 193 sources.  It never invents paper
identities.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "research" / "2026-10-25-api-extraction"
DEFAULT_INPUT = EXTRACT / "local" / "molgluedb_inventory_fetch_20261027"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "local" / "inventory_241"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clone_sources(papers: list[dict], destination: Path) -> tuple[list[dict], list[dict]]:
    source_dir = destination / "local" / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_records: list[dict] = []
    missing: list[dict] = []
    for paper in papers:
        cloned = []
        for src in paper.get("sources", []):
            old = Path(src["path"]) if src.get("path") else None
            if not old or not old.is_file():
                missing.append({"paper_id": paper["paper_id"], "source_id": paper["source_id"],
                                "path": str(old) if old else None, "reason": "source_file_missing"})
                continue
            digest = sha256(old)
            if src.get("source_sha256") and digest != src["source_sha256"]:
                raise RuntimeError(f"source hash changed: {paper['paper_id']} {old}")
            target = source_dir / f"{paper['source_id']}_{digest}.{src.get('source_kind') or old.suffix.lstrip('.') or 'bin'}"
            if not target.exists():
                shutil.copy2(old, target)
            if sha256(target) != digest:
                raise RuntimeError(f"copy hash mismatch: {target}")
            item = dict(src)
            item["path"] = str(target.resolve())
            item["source_sha256"] = digest
            item["origin"] = "frozen_prior_inventory"
            cloned.append(item)
            source_records.append({"paper_id": paper["paper_id"], "source_id": paper["source_id"],
                                   "doi": paper.get("doi"), "path": str(target.resolve()),
                                   "source_kind": item.get("source_kind"), "source_sha256": digest,
                                   "access_basis": item.get("access_basis"), "parse_status": item.get("parse_status")})
        preference = {"xml": 0, "html": 1, "htm": 1, "pdf": 2}
        cloned.sort(key=lambda x: (preference.get(x.get("source_kind"), 9), x.get("path") or ""))
        paper["sources"] = cloned
        preferred = cloned[0] if cloned else None
        paper["path"] = preferred.get("path") if preferred else None
        paper["source_sha256"] = preferred.get("source_sha256") if preferred else None
        paper["source_kind"] = preferred.get("source_kind") if preferred else None
        paper["source_format"] = preferred.get("source_kind") if preferred else None
        paper["availability"] = "local" if preferred else "input_gap"
        paper["fulltext_status"] = "ready_for_extraction" if preferred and preferred.get("parse_status") == "readable" else (
            "fulltext_missing" if not preferred else "input_gap")
        paper["extraction_status"] = "ready_for_extraction" if paper["fulltext_status"] == "ready_for_extraction" else "not_started"
    return source_records, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    input_papers_path = input_dir / "papers.json"
    input_summary_path = input_dir / "source_inventory.json"
    papers = read_json(input_papers_path)
    summary = read_json(input_summary_path)
    if len(papers) != 193:
        raise SystemExit(f"expected 193 frozen source records, found {len(papers)}")
    input_freeze = {
        "frozen_utc": now(),
        "source_inventory_dir": str(input_dir),
        "papers_sha256": sha256(input_papers_path),
        "source_inventory_sha256": sha256(input_summary_path),
        "papers_count": len(papers),
        "reported_scope": 241,
    }
    write_json(output_dir / "input_freeze.json", input_freeze)

    source_records, missing = clone_sources(papers, output_dir)
    write_json(output_dir / "papers.json", papers)
    write_csv(output_dir / "source_inventory.csv", source_records)
    inventory_summary = {
        "schema_version": 1,
        "created_utc": now(),
        "source_count": len(papers),
        "doi_sources": sum(bool(p.get("doi")) for p in papers),
        "url_only_sources": sum(not bool(p.get("doi")) for p in papers),
        "with_local_source": sum(bool(p.get("path")) for p in papers),
        "availability_counts": {
            "local": sum(p.get("availability") == "local" for p in papers),
            "input_gap": sum(p.get("availability") != "local" for p in papers),
        },
        "reported_scope": 241,
        "unresolved_identity_count": 241 - len(papers),
        "fetch_policy": {"preference": ["xml", "html", "pdf"], "automatic_retries": 0},
    }
    write_json(output_dir / "source_inventory.json", inventory_summary)

    # The public article and its PMC mirror report the 241-publication scope,
    # but expose no machine-readable 241-item bibliography.  Keep the gap
    # explicit instead of creating synthetic paper rows.
    identity_attempt = {
        "attempted_utc": now(),
        "reported_target_count": 241,
        "confirmed_current_export_sources": len(papers),
        "current_doi_sources": sum(bool(p.get("doi")) for p in papers),
        "unresolved_count": 241 - len(papers),
        "status": "unresolved",
        "sources_checked": [
            {"kind": "MolGlueDB_article", "url": "https://academic.oup.com/nar/article/54/D1/D1510/8239508",
             "finding": "reports 241 publications and the collection window, but no full itemized bibliography"},
            {"kind": "PMC_article", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12807675/",
             "finding": "public mirror and supplementary-file link; the page does not expose a 241-item source list"},
            {"kind": "MolGlueDB_export", "path": str(summary.get("export_path")),
             "finding": "export-linked source association contains the current 193 records"},
        ],
        "decision": "do_not_fabricate_unresolved_identities",
        "unresolved_records": [],
    }
    write_json(output_dir / "identity_recovery_attempt.json", identity_attempt)
    write_json(output_dir / "unresolved_scope.json", {
        "reported_scope": 241,
        "confirmed_records": len(papers),
        "unresolved_count": 241 - len(papers),
        "identity_status": "unresolved",
        "records": [],
        "reason": "public materials did not provide itemized identities",
    })

    manifest = {
        "schema_version": 1,
        "created_utc": now(),
        "reported_scope": 241,
        "confirmed_identity_count": len(papers),
        "unresolved_identity_count": 241 - len(papers),
        "source_count": len(source_records),
        "readable_source_count": sum(r.get("parse_status") == "readable" for r in source_records),
        "missing_source_file_count": len(missing),
        "input_freeze_sha256": sha256(output_dir / "input_freeze.json"),
        "papers_sha256": sha256(output_dir / "papers.json"),
        "source_inventory_sha256": sha256(output_dir / "source_inventory.csv"),
    }
    write_json(output_dir / "inventory_manifest.json", manifest)
    write_json(output_dir / "source_failures.json", missing)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
