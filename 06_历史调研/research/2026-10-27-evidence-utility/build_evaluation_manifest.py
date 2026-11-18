"""Write a compact manifest for the completed RAG/LoRA evaluation artifacts."""
import argparse
from pathlib import Path

from common import sha, write


def files(paths):
    result = {}
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            result[str(p.resolve())] = sha(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.name not in {"manifest.json", ".run.lock"}:
                    result[str(f.resolve())] = sha(f)
    return result


def build(out, inputs, outputs):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "artifact": "rag_lora_evaluation_v1",
        "external_generation_requests": 0,
        "rag": {"expected": 285, "judged": 283, "historical_unknown": 1,
                "invalid_response": 1, "not_retried": True},
        "lora": {"questions": 57, "models": ["base", "positive_only", "domain_control", "balanced_negative"],
                 "seeds": [20261027], "free_generation_used": False},
        "inputs": files(inputs),
        "outputs": files(outputs),
    }
    write(out, manifest)
    return {"inputs": len(manifest["inputs"]), "outputs": len(manifest["outputs"]),
            "external_generation_requests": 0}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--input", action="append", dest="inputs", required=True)
    p.add_argument("--output", action="append", dest="outputs", required=True)
    import json
    print(json.dumps(build(**vars(p.parse_args())), ensure_ascii=False, indent=2))
