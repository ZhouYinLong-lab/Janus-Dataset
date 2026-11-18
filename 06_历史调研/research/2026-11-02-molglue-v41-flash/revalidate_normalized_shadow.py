"""Revalidate a normalized saved response in an isolated workspace.

This is strictly offline.  It copies the frozen shadow workspace, rewrites
only the cloned response envelope, and runs the normal recovery path against
the frozen ledger.  The original workspace and response remain untouched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))
from corpus import read, save, sha  # noqa: E402
from offline_shadow_closeout import _normalize_content  # noqa: E402
from candidate_runtime import _digest  # noqa: E402


def _rebase_paths(workspace: Path):
    manifest_path = workspace / "manifest.json"
    manifest = read(manifest_path)
    for paper in manifest.get("papers", []):
        pid = paper["paper_id"]
        document = str((workspace / "documents" / f"{pid}.json").resolve())
        index = str((workspace / "sentence_indexes" / f"{pid}.json").resolve())
        paper["document_path"] = document
        paper["sentence_index_path"] = index
        for jid in paper.get("job_ids", []):
            job_path = workspace / "jobs" / f"{jid}.json"
            job = read(job_path)
            job["document_path"] = document
            job["sentence_index_path"] = index
            save(job_path, job)
            manifest["file_hashes"][f"jobs/{jid}.json"] = sha(job_path)
    save(manifest_path, manifest)


def run(source_workspace: Path, output_workspace: Path, config: Path, ledger: Path):
    source_workspace = Path(source_workspace).resolve()
    output_workspace = Path(output_workspace).resolve()
    if output_workspace.exists():
        raise ValueError(f"Output workspace already exists: {output_workspace}")
    shutil.copytree(source_workspace, output_workspace)
    _rebase_paths(output_workspace)
    state = read(output_workspace / "candidate_state.json")
    normalized = []
    for task_id, entry in state.get("tasks", {}).items():
        if entry.get("status") != "invalid_response" or not entry.get("response_path"):
            continue
        path = output_workspace / entry["response_path"]
        envelope = read(path)
        content = envelope["choices"][0]["message"]["content"]
        payload, repairs = _normalize_content(content)
        envelope["choices"][0]["message"]["content"] = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"))
        save(path, envelope)
        entry["response_sha256"] = sha(path)
        entry["offline_normalization"] = repairs
        normalized.append({"task_id": task_id, "response_sha256": entry["response_sha256"],
                           "repairs": repairs})
    manifest = read(output_workspace / "manifest.json")
    cfg = read(config)
    state["identity"] = _digest({
        "manifest": sha(output_workspace / "manifest.json"),
        "config": {k: v for k, v in cfg.items()
                   if k not in {"max_requests", "max_reserved_tokens"}},
        "budget_path": str(Path(ledger).resolve()),
        "network_route": "environment",
    })
    state["budget_path"] = str(Path(ledger).resolve())
    save(output_workspace / "candidate_state.json", state)
    command = [sys.executable, str(HERE.parent / "2026-10-25-api-extraction" / "batch_candidate.py"),
               "run", "--workspace", str(output_workspace), "--config", str(config),
               "--ledger", str(ledger), "--phase", "pilot"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    report = {
        "source_workspace": str(source_workspace),
        "output_workspace": str(output_workspace),
        "normalized": normalized,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "raw_source_preserved": True,
    }
    save(output_workspace.parent / "normalized_revalidation_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-workspace", required=True, type=Path)
    parser.add_argument("--output-workspace", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.source_workspace, args.output_workspace, args.config, args.ledger),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
