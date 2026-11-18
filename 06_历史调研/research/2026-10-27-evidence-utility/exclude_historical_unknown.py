"""Clone a frozen RAG workspace while explicitly excluding prior unknown tasks."""
import argparse
from pathlib import Path

from common import fresh, read, seal, write


def clone(src, out, task):
    src, out = Path(src), Path(out)
    tasks = read(src / "tasks.json")
    excluded = set(task)
    kept = [t for t in tasks if t["task_id"] not in excluded]
    removed = [t for t in tasks if t["task_id"] in excluded]
    if not removed:
        raise ValueError("No requested historical unknown task found")
    dest = fresh(out)
    write(dest / "tasks.json", kept)
    for name in ("config.json", "questions.json", "retrieval_audit.json"):
        write(dest / name, read(src / name))
    write(dest / "excluded_historical_unknown.json", removed)
    seal(dest, [src / "manifest.json"], {
        "artifact": "rag_trial_without_historical_unknown",
        "source_workspace": str(src.resolve()),
        "excluded_task_ids": sorted(excluded),
        "generation_requests": 0,
    })
    return {"source_tasks": len(tasks), "tasks": len(kept), "excluded": len(removed)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--task", action="append", required=True)
    import json
    print(json.dumps(clone(**vars(p.parse_args())), ensure_ascii=False, indent=2))
