"""Training-free large-model prediction on the frozen degradation boundary task.

The task is identical to the conventional classifier task: predict whether
target protein degradation was observed from molecule, target, and E3 inputs.
Test labels and DOI identities never enter model requests.  Two balanced
few-shot arms differ only in the source of their negative demonstrations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from boundary_classifier import (
    SEEDS,
    build_structured_negatives,
    classification_metrics,
    prepare_split,
    sha256,
    write_json,
)


MODEL_ARMS = (
    "zero_shot",
    "structured_negative_fewshot",
    "recovered_negative_fewshot",
)
SYSTEM_PROMPT = """You are performing a fixed biological prediction task.
For each molecular-glue input, predict whether the experiment observed target
protein degradation. Label 1 means degradation was observed; label 0 means it
was not observed. Use chemical and biological reasoning, including the
molecule, target, and recruited E3. Return only one JSON object with a
`predictions` array. Each item must contain task_id, prediction (0 or 1),
confidence (0 to 1), and a short rationale. Do not omit any task."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def public_row(row: dict[str, Any], task_id: str | None = None) -> dict[str, Any]:
    result = {
        "molecule_smiles": row["canonical_smiles"],
        "target": row["target_normalized"],
        "e3_ligase": row["e3_normalized"],
    }
    if task_id is not None:
        result = {"task_id": task_id, **result}
    return result


def task_id(seed: int, row: dict[str, Any]) -> str:
    identity = {
        "seed": seed,
        "record_id": row["record_id"],
        "smiles": row["canonical_smiles"],
        "target": row["target_normalized"],
        "e3": row["e3_normalized"],
    }
    return f"P{seed}_{digest(identity)[:16]}"


def select_demonstrations(
    rows: list[dict[str, Any]], seed: int, per_class: int = 4
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    selected: list[dict[str, Any]] = []
    for label in (0, 1):
        candidates = sorted(
            [row for row in rows if int(row["label"]) == label],
            key=lambda row: str(row["record_id"]),
        )
        if len(candidates) < per_class:
            raise ValueError(f"fewer than {per_class} demonstrations for label {label}")
        indexes = rng.choice(len(candidates), size=per_class, replace=False)
        selected.extend(candidates[int(index)] for index in sorted(indexes))
    return selected


def prepare_bundle(
    mapping_dir: Path,
    mg2act_train: Path,
    provenance: Path,
) -> dict[str, Any]:
    mapping_report = json.loads((mapping_dir / "mapping_report.json").read_text(encoding="utf-8"))
    if not mapping_report.get("training_gate_passed"):
        raise ValueError("negative mapping quality gate did not pass")
    negatives = json.loads((mapping_dir / "primary_negative_units.json").read_text(encoding="utf-8"))
    positives = json.loads((mapping_dir / "positive_pool.json").read_text(encoding="utf-8"))
    structured = build_structured_negatives(mg2act_train, provenance)

    public_splits = []
    private_labels: dict[str, dict[str, Any]] = {}
    for seed in SEEDS:
        split = prepare_split(negatives, positives, structured, seed)
        tests = []
        for row in split["test"]:
            current_id = task_id(seed, row)
            tests.append(public_row(row, current_id))
            private_labels[current_id] = {
                "seed": seed,
                "record_id": row["record_id"],
                "doi": row["doi"],
                "label": int(row["label"]),
            }

        structured_demos = select_demonstrations(
            split["arms"]["structured_balanced"], seed
        )
        recovered_demos = select_demonstrations(
            split["arms"]["recovered_balanced"], seed
        )
        test_dois = set(split["test_dois"])
        for name, rows in {
            "structured_negative_fewshot": structured_demos,
            "recovered_negative_fewshot": recovered_demos,
        }.items():
            if {row["doi"] for row in rows} & test_dois:
                raise AssertionError(f"DOI leakage in {name}")
            if sum(int(row["label"]) == 0 for row in rows) != 4:
                raise AssertionError(f"negative demonstration imbalance in {name}")
            if sum(int(row["label"]) == 1 for row in rows) != 4:
                raise AssertionError(f"positive demonstration imbalance in {name}")

        def expose_demos(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{**public_row(row), "observed_degradation": int(row["label"])} for row in rows]

        public_splits.append({
            "seed": seed,
            "test": tests,
            "demonstrations": {
                "zero_shot": [],
                "structured_negative_fewshot": expose_demos(structured_demos),
                "recovered_negative_fewshot": expose_demos(recovered_demos),
            },
            "audit": {
                "test_count": len(tests),
                "test_doi_count": len(split["test_dois"]),
                "demonstrations_per_fewshot_arm": 8,
            },
        })
    return {
        "protocol": {
            "task": "binary observed target-protein degradation prediction",
            "inputs": ["molecule_smiles", "target", "e3_ligase"],
            "arms": list(MODEL_ARMS),
            "labels_in_test_prompts": False,
            "dois_in_prompts": False,
            "condition_policy": "excluded because positive records lack comparable condition coverage",
        },
        "splits": public_splits,
        "private_labels": private_labels,
    }


def build_user_prompt(arm: str, demonstrations: list[dict[str, Any]], tests: list[dict[str, Any]]) -> str:
    prompt: dict[str, Any] = {
        "task_definition": {
            "1": "target protein degradation was observed",
            "0": "target protein degradation was not observed",
        },
        "prediction_cases": tests,
    }
    if demonstrations:
        prompt["labeled_demonstrations"] = demonstrations
        prompt["instruction"] = (
            "Use the balanced labeled demonstrations as examples, then predict every unlabeled case."
        )
    else:
        prompt["instruction"] = (
            "Predict every case without labeled demonstrations, using your pretrained reasoning."
        )
    text = json.dumps(prompt, ensure_ascii=False, indent=2)
    if '"label"' in text or '"doi"' in text or '"source"' in text:
        raise AssertionError("private metadata leaked into prompt")
    return text


def parse_predictions(content: str, expected_ids: list[str]) -> list[dict[str, Any]]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    payload = json.loads(stripped)
    rows = payload.get("predictions")
    if not isinstance(rows, list):
        raise ValueError("response lacks predictions array")
    parsed = []
    seen = set()
    for row in rows:
        current_id = str(row.get("task_id", ""))
        if current_id not in expected_ids or current_id in seen:
            raise ValueError(f"unknown or duplicate task_id: {current_id}")
        prediction = int(row.get("prediction"))
        confidence = float(row.get("confidence"))
        if prediction not in (0, 1):
            raise ValueError(f"invalid prediction for {current_id}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"invalid confidence for {current_id}")
        parsed.append({
            "task_id": current_id,
            "prediction": prediction,
            "confidence": confidence,
            "rationale": str(row.get("rationale", "")).strip(),
        })
        seen.add(current_id)
    if seen != set(expected_ids):
        missing = sorted(set(expected_ids) - seen)
        raise ValueError(f"missing predictions: {missing}")
    return parsed


def load_api_key(env_path: Path, variable: str) -> str:
    for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key.strip() == variable:
            result = value.strip().strip('"').strip("'")
            if result:
                return result
    raise ValueError(f"{variable} missing from {env_path}")


def call_api(base_url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    host = urllib.request.urlparse(base_url).hostname if hasattr(urllib.request, "urlparse") else None
    # urllib.request has no urlparse attribute on older Python versions.
    if host is None:
        from urllib.parse import urlparse
        host = urlparse(base_url).hostname
    previous_no_proxy = os.environ.get("NO_PROXY")
    values = [item.strip() for item in (previous_no_proxy or "").split(",") if item.strip()]
    if host and host not in values:
        values.append(host)
    os.environ["NO_PROXY"] = ",".join(values)
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=canonical_bytes(payload),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    finally:
        if previous_no_proxy is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = previous_no_proxy


def request_specs(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    specs = []
    first_split = bundle["splits"][0]
    first_task = first_split["test"][0]
    specs.append({
        "request_id": f"smoke_{first_split['seed']}_zero_shot",
        "seed": first_split["seed"],
        "arm": "zero_shot",
        "tests": [first_task],
        "demonstrations": [],
    })
    for split in bundle["splits"]:
        for arm in MODEL_ARMS:
            tests = split["test"]
            if split["seed"] == first_split["seed"] and arm == "zero_shot":
                tests = tests[1:]
            specs.append({
                "request_id": f"batch_{split['seed']}_{arm}",
                "seed": split["seed"],
                "arm": arm,
                "tests": tests,
                "demonstrations": split["demonstrations"][arm],
            })
    return [spec for spec in specs if spec["tests"]]


def response_content(response: dict[str, Any]) -> str:
    return str(response["choices"][0]["message"]["content"])


def score_predictions(
    predictions: list[dict[str, Any]], labels: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    run_rows = []
    scored_rows = []
    for seed in SEEDS:
        for arm in MODEL_ARMS:
            rows = [row for row in predictions if row["seed"] == seed and row["arm"] == arm]
            expected = [item for item in labels.values() if item["seed"] == seed]
            if len(rows) != len(expected):
                raise ValueError(f"incomplete predictions for seed={seed}, arm={arm}")
            y = np.asarray([labels[row["task_id"]]["label"] for row in rows], dtype=int)
            probability = np.asarray([
                row["confidence"] if row["prediction"] == 1 else 1.0 - row["confidence"]
                for row in rows
            ], dtype=float)
            metrics = classification_metrics(y, probability)
            run_rows.append({"seed": seed, "arm": arm, "count": len(rows), **metrics})
            for row, label, score in zip(rows, y, probability):
                scored_rows.append({**row, "label": int(label), "probability_positive": float(score)})
    summaries = []
    metric_names = [
        "accuracy", "macro_f1", "balanced_accuracy", "auroc",
        "average_precision", "negative_false_positive_rate", "brier",
    ]
    for arm in MODEL_ARMS:
        rows = [row for row in run_rows if row["arm"] == arm]
        summary: dict[str, Any] = {"arm": arm, "runs": len(rows)}
        for metric in metric_names:
            values = np.asarray([row[metric] for row in rows], dtype=float)
            summary[f"{metric}_mean"] = float(values.mean())
            summary[f"{metric}_std"] = float(values.std(ddof=0))
        summaries.append(summary)
    return {"runs": run_rows, "summary": summaries, "scored_predictions": scored_rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping-dir", type=Path, required=True)
    parser.add_argument("--mg2act-train", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--traditional-report", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--api-key-env", default="deepseek_api_key")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    bundle = prepare_bundle(args.mapping_dir, args.mg2act_train, args.provenance)
    public_bundle = {key: value for key, value in bundle.items() if key != "private_labels"}
    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "prediction_tasks.json", public_bundle)
    write_json(args.out / "private_labels.json", bundle["private_labels"])
    if args.prepare_only:
        print(json.dumps(public_bundle["protocol"], ensure_ascii=False, indent=2))
        return

    specs = request_specs(bundle)
    if len(specs) > args.max_requests:
        raise ValueError(f"request plan {len(specs)} exceeds max_requests={args.max_requests}")
    key = load_api_key(args.env_file, args.api_key_env)
    request_dir = args.out / "requests"
    response_dir = args.out / "responses"
    request_dir.mkdir(exist_ok=True)
    response_dir.mkdir(exist_ok=True)
    all_predictions: list[dict[str, Any]] = []
    ledger = []
    for index, spec in enumerate(specs, start=1):
        request_path = request_dir / f"{spec['request_id']}.json"
        response_path = response_dir / f"{spec['request_id']}.json"
        user_prompt = build_user_prompt(spec["arm"], spec["demonstrations"], spec["tests"])
        payload = {
            "model": args.model,
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        write_json(request_path, payload)
        started = time.time()
        if response_path.exists():
            response = json.loads(response_path.read_text(encoding="utf-8"))
            reused = True
        else:
            try:
                response = call_api(args.base_url, key, payload, args.timeout)
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                failure = {
                    "request_id": spec["request_id"],
                    "http_status": error.code,
                    "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                }
                ledger.append(failure)
                write_json(args.out / "ledger.json", ledger)
                raise RuntimeError(f"HTTP {error.code} on {spec['request_id']}") from error
            response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
            reused = False
        expected_ids = [row["task_id"] for row in spec["tests"]]
        parsed = parse_predictions(response_content(response), expected_ids)
        for row in parsed:
            all_predictions.append({
                **row,
                "seed": spec["seed"],
                "arm": spec["arm"],
                "request_id": spec["request_id"],
            })
        entry = {
            "request_id": spec["request_id"],
            "sequence": index,
            "seed": spec["seed"],
            "arm": spec["arm"],
            "task_count": len(spec["tests"]),
            "request_sha256": sha256(request_path),
            "response_sha256": sha256(response_path),
            "returned_model": response.get("model"),
            "usage": response.get("usage"),
            "reused": reused,
            "elapsed_seconds": round(time.time() - started, 3),
            "status": "success",
        }
        ledger.append(entry)
        write_json(args.out / "ledger.json", ledger)

    scored = score_predictions(all_predictions, bundle["private_labels"])
    traditional = json.loads(args.traditional_report.read_text(encoding="utf-8"))
    total_usage: dict[str, int] = {}
    for row in ledger:
        for key_name, value in (row.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                total_usage[key_name] = total_usage.get(key_name, 0) + int(value)
    report = {
        "protocol": public_bundle["protocol"],
        "large_model": {
            "requested_model": args.model,
            "returned_models": sorted({str(row.get("returned_model")) for row in ledger}),
            "requests": len(ledger),
            "usage": total_usage,
            "summary": scored["summary"],
            "runs": scored["runs"],
        },
        "traditional_small_models": traditional["summary"],
        "coverage": {
            "test_predictions": len(scored["scored_predictions"]),
            "expected_predictions": sum(len(split["test"]) for split in bundle["splits"]) * len(MODEL_ARMS),
            "failures": 0,
        },
        "synthetic_labels": 0,
    }
    write_json(args.out / "predictions.json", scored["scored_predictions"])
    write_json(args.out / "report.json", report)
    manifest_inputs = [
        args.mapping_dir / "mapping_report.json",
        args.mapping_dir / "primary_negative_units.json",
        args.mapping_dir / "positive_pool.json",
        args.mg2act_train,
        args.provenance,
        args.traditional_report,
    ]
    manifest = {
        "inputs": {str(path.resolve()): sha256(path) for path in manifest_inputs},
        "code": {str(Path(__file__).resolve()): sha256(Path(__file__))},
        "outputs": {
            path.name: sha256(path)
            for path in sorted(args.out.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
        "external_generation_requests": len([row for row in ledger if not row.get("reused")]),
        "synthetic_labels": 0,
    }
    write_json(args.out / "manifest.json", manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
