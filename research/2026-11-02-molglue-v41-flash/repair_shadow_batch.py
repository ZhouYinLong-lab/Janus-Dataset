"""Create an isolated shadow repair workspace without rewriting the original.

Only discovery jobs with structural paragraph coverage problems and facts jobs
with saved contract failures are re-requested.  All other successful responses
are eligible for exact cross-workspace reuse from the original ledger.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import read, save, sha  # noqa: E402
from sentence_export import snapshot  # noqa: E402


DISCOVERY_PATCH = (
    "\n\nREPAIR CONTRACT RULES: Every supplied paragraph must receive exactly one "
    "status. Use has_candidates only when every span has consecutive sentence IDs "
    "from that same paragraph. If no valid in-paragraph negative span exists, use "
    "none_found or uncertain with a specific reason. Never attach a candidate from "
    "a neighboring paragraph. Binding, docking, occupancy, affinity, viability, "
    "mRNA and proliferation alone are not protein-degradation negatives.\n"
)
FACTS_PATCH = (
    "\n\nREPAIR CONTRACT RULES: Each JSON object key must occur exactly once; never "
    "repeat keys such as reason. Binding-site occupancy, docking fit or molecular "
    "simulation is not a protein-degradation endpoint unless the supplied text "
    "explicitly reports a degradation experiment.\n"
)


def _reset_runtime_dirs(workspace: Path):
    for name in ("candidate_state.json", "candidate_index.json"):
        path = workspace / name
        if path.exists():
            path.unlink()


def _remap_workspace_paths(workspace: Path):
    """Convert copied absolute document/index paths to workspace-relative paths."""
    manifest_path = workspace / "manifest.json"
    manifest = read(manifest_path)
    for paper in manifest.get("papers", []):
        pid = paper["paper_id"]
        document = f"documents/{pid}.json"
        index = f"sentence_indexes/{pid}.json"
        paper["document_path"] = document
        paper["sentence_index_path"] = index
        for jid in paper.get("job_ids", []):
            job_path = workspace / "jobs" / f"{jid}.json"
            job = read(job_path)
            job["document_path"] = document
            job["sentence_index_path"] = index
            save(job_path, job)
    save(manifest_path, manifest)
    for name in ("requests", "responses", "results", "groups", "condition_groups"):
        path = workspace / name
        if path.exists():
            shutil.rmtree(path)
    for pattern in ("*.lock", "*.lock.*"):
        for path in workspace.glob(pattern):
            path.unlink()


def _problem_jobs(source_workspace: Path):
    summary, records, audits, failures = snapshot(source_workspace)
    jobs = set()
    for row in audits:
        if row.get("destination") != "paragraph_coverage":
            continue
        if row.get("status") not in {"has_candidates", "none_found"}:
            if row.get("job_id"):
                jobs.add(row["job_id"])
    for failure in failures:
        if failure.get("status") == "invalid_response" and failure.get("job_id"):
            jobs.add(failure["job_id"])
    return sorted(jobs), {
        "source_summary": summary,
        "structural_audit_rows": sum(1 for row in audits
                                      if row.get("destination") == "paragraph_coverage"
                                      and row.get("status") not in {"has_candidates", "none_found"}),
        "contract_failures": sum(1 for row in failures if row.get("status") == "invalid_response"),
        "failures": failures,
    }


def build(source_workspace, out_workspace):
    source_workspace = Path(source_workspace).resolve()
    out_workspace = Path(out_workspace).resolve()
    if out_workspace.exists():
        raise ValueError(f"repair workspace already exists: {out_workspace}")
    selected_jobs, audit = _problem_jobs(source_workspace)
    if not selected_jobs:
        raise ValueError("No structural or contract failures require repair")

    shutil.copytree(source_workspace, out_workspace)
    _reset_runtime_dirs(out_workspace)
    _remap_workspace_paths(out_workspace)
    discovery = out_workspace / "discovery_v3.md"
    facts = out_workspace / "facts_v3.md"
    discovery.write_text(discovery.read_text(encoding="utf-8") + DISCOVERY_PATCH, encoding="utf-8")
    facts.write_text(facts.read_text(encoding="utf-8") + FACTS_PATCH, encoding="utf-8")

    manifest_path = out_workspace / "manifest.json"
    manifest = read(manifest_path)
    manifest["file_hashes"]["discovery_v3.md"] = sha(discovery)
    manifest["file_hashes"]["facts_v3.md"] = sha(facts)
    manifest["repair_parent_workspace"] = str(source_workspace)
    manifest["repair_selected_jobs"] = selected_jobs
    save(manifest_path, manifest)
    report = {
        "version": 1,
        "source_workspace": str(source_workspace),
        "source_manifest_sha256": sha(source_workspace / "manifest.json"),
        "repair_workspace": str(out_workspace),
        "repair_manifest_sha256": sha(manifest_path),
        "selected_jobs": selected_jobs,
        "selected_job_count": len(selected_jobs),
        "structural_audit_rows": audit["structural_audit_rows"],
        "contract_failures": audit["contract_failures"],
        "old_responses_preserved": True,
        "cross_workspace_reuse": True,
        "new_requests_before_run": 0,
        "prompt_repairs": ["paragraph_span_binding", "duplicate_json_key", "scope_routing"],
    }
    save(out_workspace.parent / "repair_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-workspace", required=True, type=Path)
    parser.add_argument("--out-workspace", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.source_workspace, args.out_workspace), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
