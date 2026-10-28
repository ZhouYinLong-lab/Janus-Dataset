"""Offline fixed-score likelihood evaluation on the frozen MG2Act benchmark."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics

from benchmark import regression_metrics
from common import digest, read, seal, sha, verify, write
from fixed_choice_eval import option_scores_batch


MODEL_ARMS = {
    "base_structured": ("base", "structured"),
    "positive_only_structured": ("positive_only", "structured"),
    "domain_control_structured": ("domain_control", "structured"),
    "balanced_negative_structured": ("balanced_negative", "structured"),
    "base_recovered": ("base", "recovered"),
    "base_background_ablation": ("base", "background_ablation"),
}


def score_text(value):
    return json.dumps({"score": value}, separators=(",", ":"))


def prepare(benchmark, out):
    benchmark, out = Path(benchmark), Path(out)
    verify(benchmark)
    train = [x for x in read(benchmark / "official_train.json") if x["split"] == "train"]
    candidates = sorted({float(x["score"]) for x in train})
    if len(train) != 907 or len(candidates) != 16:
        raise ValueError("Expected 907 official train rows and 16 train-derived score values")
    tasks = read(benchmark / "tasks.json")
    by_key = {(t["question_id"], t["arm"]): t for t in tasks}
    labels = read(benchmark / "labels.json")
    overall = [x["score"] for x in train]
    target_values = defaultdict(list)
    for row in train:
        target_values[row["features"]["PrimaryTarget"]].append(row["score"])
    baselines = {"train_mean": statistics.mean(overall), "train_median": statistics.median(overall),
                 "target_train_mean": {k: statistics.mean(v) for k, v in target_values.items()}}
    rows = []
    for label in labels:
        for output_arm, (model_arm, context_arm) in MODEL_ARMS.items():
            source = by_key[(label["question_id"], context_arm)]
            rows.append({"task_id": digest([label["question_id"], output_arm, candidates]),
                         "question_id": label["question_id"], "output_arm": output_arm,
                         "model_arm": model_arm, "context_arm": context_arm,
                         "messages": source["messages"], "evidence_ids": source["evidence_ids"],
                         "candidate_scores": candidates})
    out.mkdir(parents=True, exist_ok=False)
    write(out / "tasks.json", rows)
    write(out / "labels.json", labels)
    write(out / "candidate_scores.json", candidates)
    write(out / "baselines.json", baselines)
    write(out / "summary.json", {"test_rows": len(labels), "tasks": len(rows),
                                  "candidate_scores": len(candidates),
                                  "candidate_source": "official train split only",
                                  "external_generation_requests": 0})
    seal(out, [benchmark / "manifest.json"], {"artifact": "mg2act_local_score_grid",
                                               "external_generation_requests": 0})
    return {"test_rows": len(labels), "tasks": len(rows), "candidate_scores": candidates}


def model_files(path):
    path = Path(path)
    wanted = []
    for name in ("config.json", "model.safetensors", "adapter_config.json", "adapter_model.safetensors"):
        p = path / name
        if p.is_file():
            wanted.append(p)
    if not wanted:
        raise ValueError("No frozen model files found: " + str(path))
    return {str(p.resolve()): sha(p) for p in wanted}


def prefix_for(task):
    return "\n\n".join(m["content"] for m in task["messages"]) + "\nAnswer:"


def run(eval_dir, base_model, positive_adapter, domain_adapter, balanced_adapter, out):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    eval_dir, out = Path(eval_dir), Path(out)
    verify(eval_dir)
    specs = {"base": None, "positive_only": Path(positive_adapter),
             "domain_control": Path(domain_adapter), "balanced_negative": Path(balanced_adapter)}
    base_model = Path(base_model)
    frozen = {"base": model_files(base_model)}
    frozen.update({name: model_files(path) for name, path in specs.items() if path})
    identity = digest([sha(eval_dir / "manifest.json"), frozen, MODEL_ARMS])
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state = read(state_path) if state_path.exists() else {"identity": identity, "tasks": {}}
    if state["identity"] != identity:
        raise ValueError("MG2Act local evaluation identity changed")
    tasks = read(eval_dir / "tasks.json")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(base_model, local_files_only=True, trust_remote_code=False)
    for model_arm, adapter in specs.items():
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = AutoModelForCausalLM.from_pretrained(base_model, local_files_only=True,
                                                     trust_remote_code=False, dtype=dtype)
        if adapter:
            model = PeftModel.from_pretrained(model, adapter, local_files_only=True)
        model.to(device).eval()
        for task in (x for x in tasks if x["model_arm"] == model_arm):
            if task["task_id"] in state["tasks"]:
                continue
            prefix = prefix_for(task)
            prefix_tokens = tokenizer(prefix, add_special_tokens=False)["input_ids"]
            limit = int(getattr(model.config, "max_position_embeddings", 32768))
            if len(prefix_tokens) + 16 >= limit:
                state["tasks"][task["task_id"]] = {"status": "failed", "reason": "context_too_long",
                                                    "question_id": task["question_id"],
                                                    "output_arm": task["output_arm"]}
            else:
                options = [{"category": str(value), "text": score_text(value)}
                           for value in task["candidate_scores"]]
                scores = option_scores_batch(model, tokenizer, prefix, options, device)
                best = max(scores, key=lambda x: x["mean_logprob"])
                state["tasks"][task["task_id"]] = {
                    "status": "complete", "question_id": task["question_id"],
                    "output_arm": task["output_arm"], "model_arm": model_arm,
                    "context_arm": task["context_arm"], "prediction": float(best["category"]),
                    "candidate_scores": scores, "prefix_tokens": len(prefix_tokens),
                    "evidence_count": len(task["evidence_ids"]),
                }
            write(state_path, state)
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    predictions = list(state["tasks"].values())
    write(out / "predictions.json", predictions)
    report = report_results(eval_dir, predictions)
    write(out / "report.json", report)
    inputs = [eval_dir / "manifest.json"] + [Path(p) for files in frozen.values() for p in files]
    seal(out, inputs, {"artifact": "mg2act_local_predictions", "external_generation_requests": 0})
    return report


def cluster_delta(rows_a, rows_b, seed=20261027, draws=2000):
    paired = []
    bmap = {x["question_id"]: x for x in rows_b}
    for a in rows_a:
        b = bmap.get(a["question_id"])
        if a.get("prediction") is not None and b and b.get("prediction") is not None:
            paired.append((a["target"], abs(a["prediction"] - a["Score"]) -
                           abs(b["prediction"] - b["Score"])))
    groups = defaultdict(list)
    for target, delta in paired:
        groups[target].append(delta)
    names = sorted(groups)
    observed = sum(d for _, d in paired) / len(paired) if paired else None
    if not names:
        return {"paired": 0, "delta_mae": None, "ci95": None}
    rng, samples = random.Random(seed), []
    for _ in range(draws):
        chosen = [rng.choice(names) for _ in names]
        values = [d for name in chosen for d in groups[name]]
        samples.append(sum(values) / len(values))
    samples.sort()
    return {"paired": len(paired), "clusters": len(names), "delta_mae": observed,
            "ci95": [samples[int(.025 * draws)], samples[min(draws - 1, int(.975 * draws))]],
            "interpretation": "negative favors first arm"}


def report_results(eval_dir, predictions):
    labels = {x["question_id"]: x for x in read(Path(eval_dir) / "labels.json")}
    by_arm = defaultdict(dict)
    for p in predictions:
        if p["question_id"] not in labels or p["question_id"] in by_arm[p["output_arm"]]:
            raise ValueError("Duplicate or unknown MG2Act prediction")
        by_arm[p["output_arm"]][p["question_id"]] = p.get("prediction") if p["status"] == "complete" else None
    rows_by_arm, metrics = {}, {}
    for arm in MODEL_ARMS:
        values = by_arm.get(arm, {})
        rows = [dict(label, prediction=values.get(qid)) for qid, label in labels.items()]
        rows_by_arm[arm] = rows
        metrics[arm] = {"full_test": regression_metrics(rows),
                        "fine_test": regression_metrics([x for x in rows if x["fine_test"]])}
    comparisons = {}
    for first, second in (("balanced_negative_structured", "positive_only_structured"),
                          ("balanced_negative_structured", "domain_control_structured"),
                          ("balanced_negative_structured", "base_structured"),
                          ("base_recovered", "base_structured"),
                          ("base_recovered", "base_background_ablation")):
        comparisons[first + "_minus_" + second] = cluster_delta(rows_by_arm[first], rows_by_arm[second])
    baseline_metrics = {}
    baseline_path = Path(eval_dir) / "baselines.json"
    if baseline_path.exists():
        baseline = read(baseline_path)
        for name in ("train_mean", "train_median", "target_train_mean"):
            rows = []
            for label in labels.values():
                prediction = (baseline[name].get(label["target"], baseline["train_mean"])
                              if name == "target_train_mean" else baseline[name])
                rows.append(dict(label, prediction=prediction))
            baseline_metrics[name] = {"full_test": regression_metrics(rows),
                                      "fine_test": regression_metrics([x for x in rows if x["fine_test"]])}
    return {"models": metrics, "baselines": baseline_metrics, "comparisons": comparisons,
            "single_seed": True, "scoring": "train-derived fixed-score mean conditional log-likelihood",
            "external_generation_requests": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--benchmark", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    r = sub.add_parser("run")
    for name in ("eval-dir", "base-model", "positive-adapter", "domain-adapter", "balanced-adapter", "out"):
        r.add_argument("--" + name, required=True, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(prepare(**args) if command == "prepare" else run(**args), ensure_ascii=False, indent=2))
