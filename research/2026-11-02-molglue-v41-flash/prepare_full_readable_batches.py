"""Prepare seven independent batches for the 70 readable XML papers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import save, sha  # noqa: E402
from sentence_workspace import prepare  # noqa: E402


CONTRACT_PATCH = """

FULL-READABLE BATCH CONTRACT:
- Return exactly the requested JSON object. Do not add wrapper fields such as
  type, schema, or metadata.
- Emit each JSON object key exactly once; never repeat a key.
- Binding, docking, occupancy, affinity, mRNA, proliferation, viability,
  cytotoxicity, or mechanism-only observations are not protein-degradation
  negatives.
- Candidate spans must use consecutive sentence IDs from the same paragraph;
  never borrow a neighboring paragraph.
"""


def load_readable(source_manifest: Path):
    papers = json.loads(source_manifest.read_text(encoding="utf-8"))
    selected = [p for p in papers if p.get("availability") == "local"
                and p.get("source_kind") == "xml" and p.get("path")]
    selected.sort(key=lambda p: str(p.get("paper_id")))
    return selected


def _patch_prompts(workspace: Path):
    manifest_path = workspace / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("discovery_v3.md", "facts_v3.md", "conditions_v3.md"):
        path = workspace / name
        path.write_text(path.read_text(encoding="utf-8") + CONTRACT_PATCH, encoding="utf-8")
        manifest["file_hashes"][name] = sha(path)
    save(manifest_path, manifest)


def build(source_manifest: Path, output_root: Path, config_path: Path, batch_size=10):
    source_manifest = Path(source_manifest).resolve()
    output_root = Path(output_root).resolve()
    if output_root.exists():
        raise ValueError(f"Output root already exists: {output_root}")
    papers = load_readable(source_manifest)
    if len(papers) != 70:
        raise ValueError(f"Expected 70 readable XML papers, found {len(papers)}")
    output_root.mkdir(parents=True)
    metadata_path = output_root / "readable_70_papers.json"
    metadata_path.write_text(json.dumps(papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batches = []
    for index in range(0, len(papers), batch_size):
        number = index // batch_size + 1
        selected = papers[index:index + batch_size]
        batch_root = output_root / f"batch_{number:02d}"
        workspace = batch_root / "workspace"
        batch_root.mkdir()
        ledger = {
            "version": 1,
            "max_requests": None,
            "max_reserved_tokens": None,
            "authorization": "User-authorized readable XML full extraction; stop on provider, duplicate, source, or content failure.",
            "created": time.time(),
            "attempts": [],
        }
        ledger_path = batch_root / "ledger.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config_path_out = batch_root / "config.json"
        config_path_out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prepare(workspace, papers=[p["paper_id"] for p in selected],
                manifest_path=metadata_path, phase="full")
        _patch_prompts(workspace)
        save(ledger_path, ledger)
        batches.append({
            "batch": number,
            "papers": [p["paper_id"] for p in selected],
            "workspace": str(workspace),
            "ledger": str(ledger_path),
            "config": str(config_path_out),
            "manifest_sha256": sha(workspace / "manifest.json"),
        })
    report = {"status": "prepared", "source_manifest": str(source_manifest),
              "source_manifest_sha256": sha(source_manifest), "papers": len(papers),
              "batch_size": batch_size, "batches": batches}
    save(output_root / "prepare_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.source_manifest, args.output_root, args.config),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
