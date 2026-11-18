"""Merge resumable RAG workspaces into one auditable scoring workspace."""
import argparse
import shutil
from pathlib import Path

from common import fresh, read, seal, sha, write


def merge(base, runs, out):
    base, out = Path(base), Path(out)
    runs = [Path(x) for x in runs]
    tasks = read(base / "tasks.json")
    by_task = {}
    for run in runs:
        state_path = run / "state.json"
        if not state_path.exists():
            continue
        state = read(state_path)
        for tid, entry in state.get("tasks", {}).items():
            if tid in by_task and by_task[tid].get("status") == "complete" and entry.get("status") == "complete":
                continue
            by_task[tid] = dict(entry, _run=str(run.resolve()))
    dest = fresh(out)
    write(dest / "tasks.json", tasks)
    for name in ("config.json", "questions.json", "retrieval_audit.json"):
        write(dest / name, read(base / name))
    merged = {}
    complete = 0
    for task in tasks:
        tid = task["task_id"]
        entry = by_task.get(tid)
        if not entry:
            continue
        run = Path(entry.pop("_run"))
        if entry.get("response_path"):
            src = run / entry["response_path"]
            if src.exists():
                rel = "responses/" + tid + ".json"
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                entry["response_path"] = rel
                entry["response_sha256"] = sha(target)
        merged[tid] = entry
        if entry.get("status") == "complete":
            complete += 1
    state = {
        "identity": "merged-scoring-workspace",
        "ledger": None,
        "allowed_models": [read(base / "config.json")["model"]],
        "tasks": merged,
        "stop_reason": None if complete == len(tasks) else "partial_merged_runs",
    }
    write(dest / "state.json", state)
    write(dest / "merge_report.json", {
        "source_runs": [str(x.resolve()) for x in runs],
        "tasks": len(tasks), "complete": complete,
        "incomplete": len(tasks) - complete,
        "generation_requests": 0,
    })
    seal(dest, [base / "manifest.json"] + [r / "state.json" for r in runs if (r / "state.json").exists()], {
        "artifact": "merged_rag_scoring_workspace", "complete": complete,
        "generation_requests": 0,
    })
    return {"tasks": len(tasks), "complete": complete, "incomplete": len(tasks) - complete}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--run", dest="runs", action="append", required=True)
    p.add_argument("--out", required=True, type=Path)
    import json
    print(json.dumps(merge(**vars(p.parse_args())), ensure_ascii=False, indent=2))
