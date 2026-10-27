"""Offline task-package export and idempotent Codex-worker result intake.

This module deliberately does not send requests or modify ``candidate_state``.
It creates a provenance-bound handoff layer around the existing sentence_v3
workspace so a local Codex worker can process assigned tasks and the main
runtime can import results only after source/task identity checks.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import time

from corpus import read, save, sha
from sentence_workspace import verify

SCHEMA_VERSION = 1
PIPELINE = "molgluedb_sentence_v3"
STAGES = ("discovery", "facts", "conditions")


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def _paper_map(manifest):
    return {p["paper_id"]: p for p in manifest.get("papers", [])}


def _job_task_ids(workspace, job_id, state):
    """Return the stages already materialized in the frozen runtime state."""
    ids = [job_id + ":discovery"]
    tasks = state.get("tasks", {}) if isinstance(state, dict) else {}
    for tid, entry in tasks.items():
        if entry.get("job_id") == job_id and entry.get("stage") in {"facts", "conditions"}:
            ids.append(tid)
    return sorted(set(ids))


def export_task_package(workspace, out, paper_ids=None):
    """Export a provenance-bound, local-path task package without generation.

    The package contains job metadata and references to frozen documents and
    sentence indexes; it does not duplicate restricted full text.  Every task
    records the source hash and workspace manifest hash used for assignment.
    """
    workspace = Path(workspace).resolve()
    out = Path(out).resolve()
    manifest = verify(workspace)
    if manifest.get("pipeline") != PIPELINE:
        raise ValueError("Expected sentence_v3 workspace")
    selected = set(paper_ids) if paper_ids is not None else None
    papers = [p for p in manifest.get("papers", [])
              if selected is None or p.get("paper_id") in selected]
    if selected is not None and {p.get("paper_id") for p in papers} != selected:
        missing = sorted(selected - {p.get("paper_id") for p in papers})
        raise ValueError("Unknown paper IDs: " + ",".join(missing))
    state_path = workspace / "candidate_state.json"
    state = read(state_path) if state_path.is_file() else {}
    manifest_hash = sha(workspace / "manifest.json")
    out.mkdir(parents=True, exist_ok=True)
    task_dir = out / "tasks"
    task_dir.mkdir(exist_ok=True)
    package_papers, task_rows = [], []
    selected_ids = {p["paper_id"] for p in papers}
    for paper in papers:
        row = {k: paper.get(k) for k in
               ("paper_id", "doi", "title", "source_path", "source_sha256",
                "source_kind", "document_path", "sentence_index_path",
                "sentence_count", "sentence_gaps")}
        row["job_ids"] = []
        for job_id in paper.get("job_ids", []):
            job = read(workspace / "jobs" / f"{job_id}.json")
            row["job_ids"].append(job_id)
            for task_id in _job_task_ids(workspace, job_id, state):
                stage = task_id.split(":", 1)[1].split(":", 1)[0]
                task = {
                    "task_id": task_id,
                    "job_id": job_id,
                    "paper_id": paper["paper_id"],
                    "doi": paper.get("doi"),
                    "stage": stage,
                    "group": task_id.rsplit(":", 1)[-1] if stage in {"facts", "conditions"} else None,
                    "source_sha256": paper.get("source_sha256"),
                    "workspace_manifest_sha256": manifest_hash,
                    "workspace": str(workspace),
                    "job_path": str((workspace / "jobs" / f"{job_id}.json").resolve()),
                    "document_path": paper.get("document_path"),
                    "sentence_index_path": paper.get("sentence_index_path"),
                    "job_sha256": sha(workspace / "jobs" / f"{job_id}.json"),
                    "task_hash": None,
                }
                task["task_hash"] = _digest(task)
                save(task_dir / f"{_safe_name(task_id)}.json", task)
                task_rows.append(task)
        package_papers.append(row)
    package = {
        "schema_version": SCHEMA_VERSION,
        "pipeline": PIPELINE,
        "created_utc": time.time(),
        "workspace": str(workspace),
        "workspace_manifest_sha256": manifest_hash,
        "paper_ids": sorted(selected_ids),
        "papers": package_papers,
        "tasks": [{k: t[k] for k in ("task_id", "job_id", "paper_id", "stage",
                                      "source_sha256", "task_hash")}
                   for t in task_rows],
        "api_requests_sent": 0,
        "generation_method": "Codex subagent",
    }
    package["package_sha256"] = _digest(package)
    save(out / "task_package.json", package)
    return {"package": str(out / "task_package.json"), "papers": len(package_papers),
            "tasks": len(task_rows), "workspace_manifest_sha256": manifest_hash,
            "api_requests_sent": 0}


def _load_package(package_path):
    package = read(package_path)
    expected = package.get("package_sha256")
    actual_doc = dict(package)
    actual_doc.pop("package_sha256", None)
    if expected != _digest(actual_doc):
        raise ValueError("Task package hash mismatch")
    return package


def import_results(workspace, package_path, incoming, out):
    """Import Codex-worker results into an independent, idempotent index.

    ``incoming`` may be a directory of JSON files or one JSON list/object. A
    result must identify task, paper, stage and source hash. Existing main
    runtime state is never touched; the normalized artifacts are ready for a
    subsequent validator bridge.
    """
    workspace = Path(workspace).resolve()
    package = _load_package(Path(package_path))
    out = Path(out).resolve()
    result_dir = out / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    index_path = out / "codex_import_index.json"
    index = read(index_path) if index_path.is_file() else {
        "schema_version": SCHEMA_VERSION, "package_sha256": package["package_sha256"],
        "tasks": {}, "events": []}
    if index.get("package_sha256") != package["package_sha256"]:
        raise ValueError("Import package changed")
    tasks = {row["task_id"]: row for row in package.get("tasks", [])}
    incoming_path = Path(incoming)
    if incoming_path.is_dir():
        inputs = sorted(incoming_path.glob("*.json"))
    else:
        value = read(incoming_path)
        inputs = value if isinstance(value, list) else [value]
    imported, duplicates, conflicts, rejected = 0, 0, 0, 0
    errors = []
    for source in inputs:
        row = read(source) if isinstance(source, Path) else source
        try:
            if not isinstance(row, dict):
                raise ValueError("result_not_object")
            task_id = row.get("task_id")
            expected = tasks.get(task_id)
            if expected is None:
                raise ValueError("unknown_task_id")
            for field in ("paper_id", "stage", "source_sha256"):
                if row.get(field) != expected.get(field):
                    raise ValueError("identity_mismatch:" + field)
            if row.get("stage") not in STAGES:
                raise ValueError("invalid_stage")
            result = row.get("result")
            if not isinstance(result, dict):
                raise ValueError("missing_result_object")
            result_hash = row.get("result_sha256") or _digest(result)
            if result_hash != _digest(result):
                raise ValueError("result_hash_mismatch")
            raw = row.get("raw_output")
            raw_hash = row.get("raw_output_sha256")
            if raw_hash and raw_hash != _digest(raw):
                raise ValueError("raw_output_hash_mismatch")
            prior = index["tasks"].get(task_id)
            if prior:
                if prior.get("result_sha256") == result_hash:
                    duplicates += 1
                    continue
                conflicts += 1
                raise ValueError("task_has_different_existing_result")
            normalized = deepcopy(row)
            normalized.update(result_sha256=result_hash,
                              raw_output_sha256=raw_hash or _digest(raw),
                              imported_utc=time.time(),
                              generation_method=row.get("generation_method", "Codex subagent"),
                              workspace_manifest_sha256=package["workspace_manifest_sha256"])
            target = result_dir / f"{_safe_name(task_id)}_{result_hash[:12]}.json"
            save(target, normalized)
            index["tasks"][task_id] = {
                "task_id": task_id, "paper_id": row["paper_id"],
                "stage": row["stage"], "source_sha256": row["source_sha256"],
                "result_path": str(target.relative_to(out)).replace("\\", "/"),
                "result_sha256": result_hash, "raw_output_sha256": normalized["raw_output_sha256"],
                "status": "imported"}
            imported += 1
        except (TypeError, ValueError, KeyError) as exc:
            rejected += 1
            errors.append({"source": str(source), "error": str(exc)})
    index["events"].append({"time": time.time(), "imported": imported,
                             "duplicates": duplicates, "conflicts": conflicts,
                             "rejected": rejected})
    save(index_path, index)
    return {"imported": imported, "duplicates": duplicates, "conflicts": conflicts,
            "rejected": rejected, "errors": errors, "tasks_total": len(tasks),
            "tasks_imported": len(index["tasks"]), "api_requests_sent": 0,
            "index": str(index_path)}


def status(out):
    """Return resumable import status without changing any files."""
    index = read(Path(out) / "codex_import_index.json")
    counts = Counter(row.get("status", "unknown") for row in index.get("tasks", {}).values())
    return {"tasks_imported": len(index.get("tasks", {})), "task_status": dict(counts),
            "events": len(index.get("events", [])), "api_requests_sent": 0}

