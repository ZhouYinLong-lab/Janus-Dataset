"""Adopt downloaded source files that were not linked after a prior checkpoint."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from corpus import read, save
from source_formats import parse_document

NAME = re.compile(r"(src_[0-9a-f]+)_([0-9a-f]{64})\.(xml|pdf|html)$", re.I)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def adopt(inventory):
    folder = Path(inventory).resolve()
    papers = read(folder / "papers.json")
    by_source = {p["source_id"]: p for p in papers}
    linked = {Path(s["path"]).name for p in papers for s in (p.get("sources") or [])
              if s.get("path")}
    adopted, rejected = [], []
    for path in sorted((folder / "local" / "sources").glob("*")):
        if not path.is_file() or path.name in linked:
            continue
        match = NAME.fullmatch(path.name)
        if not match or match.group(1) not in by_source:
            continue
        paper = by_source[match.group(1)]
        actual = digest(path)
        if actual != match.group(2):
            rejected.append({"paper_id": paper["paper_id"], "file": str(path),
                             "reason": "filename_hash_mismatch", "actual": actual})
            continue
        attempt = next((a for a in reversed(paper.get("fetch_attempts", []))
                        if a.get("sha256") == actual), {})
        kind = match.group(3).lower()
        try:
            document = parse_document(path, paper["paper_id"])
            parse_status = document["status"]
            coverage = document.get("coverage", "")
        except Exception as exc:
            parse_status = "parse_error"
            coverage = ""
            document = None
            rejected.append({"paper_id": paper["paper_id"], "file": str(path),
                             "reason": f"{type(exc).__name__}: {exc}"})
        source = {
            "path": str(path.resolve()), "source_sha256": actual,
            "source_kind": kind, "origin": "orphan_checkpoint_recovery",
            "url": attempt.get("final_url") or attempt.get("url"),
            "availability": "local" if parse_status in {"readable", "readable_partial"}
                            else "input_gap",
            "access_basis": "Previously recorded OpenAlex OA download; adopted offline",
            "content_type": attempt.get("content_type"),
            "retrieved_utc": attempt.get("started_utc"),
            "parse_status": parse_status, "coverage": coverage,
        }
        paper.setdefault("sources", []).append(source)
        if document and parse_status in {"readable", "readable_partial"}:
            preference = {"xml": 0, "html": 1, "pdf": 2}
            if (not paper.get("path") or
                    preference.get(kind, 99) < preference.get(paper.get("source_kind"), 99)):
                paper.update(path=str(path.resolve()), source_sha256=actual,
                             source_kind=kind, source_format=kind, availability="local",
                             availability_reason="orphan_checkpoint_recovered")
            adopted.append({"paper_id": paper["paper_id"], "doi": paper.get("doi"),
                            "path": str(path.resolve()), "status": parse_status,
                            "units": len(document.get("units", []))})
        else:
            rejected.append({"paper_id": paper["paper_id"], "file": str(path),
                             "reason": "downloaded_but_not_parseable", "parse_status": parse_status})
    summary = {"adopted": adopted, "rejected": rejected,
               "adopted_count": len(adopted), "rejected_count": len(rejected)}
    save(folder / "papers.json", papers)
    save(folder / "orphan_recovery_report.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(adopt(args.inventory), ensure_ascii=False, indent=2))
