"""Prepare a deterministic, isolated shadow extraction batch.

The shadow batch is deliberately separate from the five-paper pilot and from
the full sentence workspace.  It selects only hash-verified local XML sources,
creates a fresh sentence workspace, and creates an unbounded independent
ledger.  No model request is made by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys


HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

import batch_budget  # noqa: E402
from corpus import read, save, sha  # noqa: E402
import sentence_workspace  # noqa: E402


PILOT_IDS = frozenset(sentence_workspace.PILOT_PAPERS)
DEFAULT_SEED = 20261103
DEFAULT_COUNT = 10


def _digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidates(source_manifest: Path):
    rows = read(source_manifest)
    if not isinstance(rows, dict) or not isinstance(rows.get("papers"), list):
        raise ValueError("source manifest must contain a papers array")
    usable = []
    for row in rows["papers"]:
        if not isinstance(row, dict):
            continue
        paper_id = row.get("paper_id")
        path_value = row.get("source_path") or row.get("path")
        path = Path(path_value) if path_value else None
        if not paper_id or paper_id in PILOT_IDS or row.get("availability") != "local":
            continue
        if path is None or not path.is_file() or path.suffix.lower() != ".xml":
            continue
        expected = row.get("source_sha256")
        if not expected or sha(path) != expected:
            raise ValueError(f"source hash mismatch or missing hash: {paper_id}")
        usable.append(row)
    usable.sort(key=lambda row: str(row["paper_id"]))
    if len({row["paper_id"] for row in usable}) != len(usable):
        raise ValueError("duplicate paper_id in usable source inventory")
    return usable


def select(source_manifest: Path, count: int, seed: int):
    if type(count) is not int or count < 1:
        raise ValueError("count must be positive")
    pool = candidates(source_manifest)
    if len(pool) < count:
        raise ValueError(f"only {len(pool)} eligible XML sources; requested {count}")
    picked = random.Random(seed).sample(pool, count)
    return sorted(picked, key=lambda row: str(row["paper_id"]))


def _paper_metadata(row):
    # sentence_workspace.prepare requires `path`; all other fields remain the
    # frozen inventory metadata used for provenance and request construction.
    metadata = dict(row)
    metadata["path"] = str(Path(row["source_path"]).resolve())
    metadata["source_sha256"] = row["source_sha256"]
    metadata["availability"] = "local"
    return metadata


def build(args):
    source_manifest = Path(args.source_manifest).resolve()
    out_root = Path(args.out_root).resolve()
    if out_root.exists() and any(out_root.iterdir()):
        raise ValueError(f"output directory is not empty: {out_root}")
    selected = select(source_manifest, args.count, args.seed)
    out_root.mkdir(parents=True, exist_ok=True)
    papers_path = out_root / "papers.json"
    save(papers_path, [_paper_metadata(row) for row in selected])

    workspace = out_root / "workspace"
    sentence_workspace.prepare(workspace, manifest_path=papers_path, phase="full")

    config_source = Path(args.config_source).resolve()
    config_path = out_root / "config.json"
    shutil.copyfile(config_source, config_path)
    ledger_path = out_root / "ledger.json"
    batch_budget.create(
        ledger_path,
        max_requests=None,
        max_reserved_tokens=None,
        authorization=(
            "User 2026-11-03 authorized long-term shadow extraction; "
            "independent ledger, no local request/token cap; five-paper v3 "
            "quality gate is frozen_candidate; stop on provider or content failure."
        ),
    )

    report = {
        "version": 1,
        "batch": "shadow",
        "created_by": "prepare_shadow_batch.py",
        "seed": args.seed,
        "requested_papers": args.count,
        "selected_papers": [
            {
                "paper_id": row["paper_id"],
                "doi": row.get("doi"),
                "source_path": str(Path(row["source_path"]).resolve()),
                "source_sha256": row["source_sha256"],
            }
            for row in selected
        ],
        "excluded_fixed_pilot": sorted(PILOT_IDS),
        "source_manifest_sha256": sha(source_manifest),
        "selection_sha256": _digest([row["paper_id"] for row in selected]),
        "workspace": str(workspace),
        "config": str(config_path),
        "ledger": str(ledger_path),
        "generation_requests_sent": 0,
        "input_policy": "local readable XML only; source hashes checked before preparation",
    }
    save(out_root / "selection_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--out-root", required=True, type=Path)
    parser.add_argument("--config-source", required=True, type=Path)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    print(json.dumps(build(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
