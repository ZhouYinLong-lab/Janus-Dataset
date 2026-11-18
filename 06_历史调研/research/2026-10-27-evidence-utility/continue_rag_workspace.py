"""Create a budget-expanded continuation workspace containing only pending tasks."""
import argparse
import json
from pathlib import Path

from common import fresh, read, seal, write


def continue_workspace(src, out, max_requests=237, max_reserved_tokens=2400000, exclude_task=None):
    src, out = Path(src), Path(out)
    state = read(src / "state.json")
    tasks = read(src / "tasks.json")
    entries = state.get("tasks", {})
    excluded = set(exclude_task or [])
    pending = [t for t in tasks if t["task_id"] not in excluded and
               entries.get(t["task_id"], {}).get("status") != "complete"]
    if not pending:
        raise ValueError("No pending tasks to continue")
    dest = fresh(out)
    cfg = read(src / "config.json")
    cfg["max_requests"] = max_requests
    cfg["max_reserved_tokens"] = max_reserved_tokens
    write(dest / "tasks.json", pending)
    write(dest / "config.json", cfg)
    write(dest / "questions.json", read(src / "questions.json"))
    write(dest / "retrieval_audit.json", read(src / "retrieval_audit.json"))
    write(dest / "continuation_source.json", {
        "source_workspace": str(src.resolve()),
        "source_manifest": str((src / "manifest.json").resolve()),
        "source_state": str((src / "state.json").resolve()),
        "source_complete": len(tasks) - len(pending),
        "pending_tasks": len(pending),
        "excluded_tasks": sorted(excluded),
        "generation_requests": 0,
    })
    seal(dest, [src / "manifest.json", src / "state.json"], {
        "artifact": "rag_continuation",
        "source_workspace": str(src.resolve()),
        "max_requests": max_requests,
        "max_reserved_tokens": max_reserved_tokens,
        "generation_requests": 0,
    })
    return {"source_tasks": len(tasks), "source_complete": len(tasks) - len(pending),
            "pending_tasks": len(pending), "max_requests": max_requests,
            "max_reserved_tokens": max_reserved_tokens}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--max-requests", type=int, default=237)
    p.add_argument("--max-reserved-tokens", type=int, default=2400000)
    p.add_argument("--exclude-task", action="append")
    print(json.dumps(continue_workspace(**vars(p.parse_args())), ensure_ascii=False, indent=2))
