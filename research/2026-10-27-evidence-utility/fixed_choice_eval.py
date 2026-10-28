"""Evidence-conditioned fixed-choice evaluation for the base model and LoRA adapters."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import re

from common import digest, fresh, read, seal, sha, write


CATEGORIES = ("correct", "overclaim", "wrong_endpoint", "insufficient")
SYSTEM = (
    "根据给出的论文问题和证据判断候选结论。只使用提供的证据；不要补写未报告的条件；"
    "区分蛋白降解、mRNA、结合和细胞活性；未测试不等于无效。"
)


def terms(text):
    return set(re.findall(r"[\wα-ω]+", str(text).casefold()))


def make_options(question, evidence, index, seed=20261027):
    ref = question.get("reference_answer") or ""
    base = [
        ("correct", "原文支持的结论：" + ref),
        ("overclaim", "结论：该处理完全没有任何作用，并且在所有实验条件下都无活性。"),
        ("wrong_endpoint", "结论：该对象在另一个实验终点的结果可以直接替代题目所问的对象和终点。"),
        ("insufficient", "结论：论文没有做这个实验，因此无法判断结果。"),
    ]
    rng = random.Random(seed + index * 7919)
    rng.shuffle(base)
    return [{"category": c, "text": t} for c, t in base]


def prepare(questions, trial, out, seed=20261027):
    questions, trial, out = Path(questions), Path(trial), Path(out)
    qs = read(questions)
    if len(qs) != 57 or any(q.get("split") != "test" for q in qs):
        raise ValueError("Fixed-choice evaluation requires the frozen 57-question test set")
    tasks = {t["question_id"]: t for t in read(trial / "tasks.json") if t["arm"] == "recovered"}
    if len(tasks) != len(qs):
        raise ValueError("Recovered context must cover all 57 questions")
    records, labels = [], []
    for i, q in enumerate(qs):
        task = tasks[q["question_id"]]
        user_payload = json.loads(task["messages"][-1]["content"])
        options = make_options(q, user_payload.get("evidence", []), i, seed)
        correct = next(i for i, o in enumerate(options) if o["category"] == "correct")
        # Labels are kept separate and never passed to model scoring.
        labels.append({"question_id": q["question_id"], "correct_option": correct,
                       "correct_category": "correct", "evaluation_group": q.get("evaluation_group"),
                       "source_dois": q.get("source_dois", [])})
        records.append({"question_id": q["question_id"], "question": q["question"],
                        "evidence": user_payload.get("evidence", []), "options": options,
                        "messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": json.dumps({
                                         "question": q["question"], "evidence": user_payload.get("evidence", [])
                                     }, ensure_ascii=False)}]})
    out = fresh(out)
    write(out / "fixed_choice_questions.json", records)
    write(out / "fixed_choice_labels.json", labels)
    write(out / "config.json", {"seed": seed, "questions": len(records),
                                 "models": ["base", "positive_only", "domain_control", "balanced_negative"],
                                 "scoring": "mean conditional log-likelihood over option tokens"})
    seal(out, [questions, trial / "manifest.json"], {"artifact": "fixed_choice_evaluation", "api_requests": 0})
    return {"questions": len(records), "options": len(records) * 4, "api_requests": 0}


def option_score(model, tokenizer, prefix, option, device):
    p = tokenizer(prefix, return_tensors="pt", add_special_tokens=False)
    o = tokenizer(option, return_tensors="pt", add_special_tokens=False)
    input_ids = __import__("torch").cat([p["input_ids"], o["input_ids"]], dim=1).to(device)
    with __import__("torch").inference_mode():
        logits = model(input_ids=input_ids).logits[:, :-1, :]
        # Avoid materializing a second vocab-sized tensor; log p = selected logit - logsumexp.
        denom = __import__("torch").logsumexp(logits, dim=-1)
    start = p["input_ids"].shape[1] - 1
    target = input_ids[:, start + 1:]
    selected = logits[:, start:start + target.shape[1], :].gather(2, target.unsqueeze(-1)).squeeze(-1)
    values = selected - denom[:, start:start + target.shape[1]]
    return float(values.mean().item()), int(target.shape[1])


def option_scores_batch(model, tokenizer, prefix, options, device):
    """Score options using one cached prefix forward per question."""
    import torch
    prefix_ids = tokenizer(prefix, return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)
    with torch.inference_mode():
        prefix_out = model(input_ids=prefix_ids, use_cache=True)
    past = prefix_out.past_key_values
    first_logits = prefix_out.logits[:, -1, :]
    scores = []
    for i, option in enumerate(options):
        ids = tokenizer(option["text"], return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)
        if ids.shape[1] == 0:
            raise ValueError("Option tokenization produced no tokens")
        with torch.inference_mode():
            first_logp = first_logits.log_softmax(dim=-1).gather(1, ids[:, :1]).squeeze(1)
            if ids.shape[1] > 1:
                out = model(input_ids=ids, past_key_values=past, use_cache=False)
                rest_logits = out.logits[:, :-1, :]
                rest_logp = rest_logits.log_softmax(dim=-1).gather(2, ids[:, 1:].unsqueeze(-1)).squeeze(-1)
                values = torch.cat([first_logp.unsqueeze(1), rest_logp], dim=1)
            else:
                values = first_logp.unsqueeze(1)
        scores.append({"option": i, "category": option["category"],
                       "mean_logprob": float(values.mean().item()), "tokens": int(values.shape[1])})
    return scores


def run(eval_dir, base_model, adapters, out=None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    eval_dir = Path(eval_dir)
    records, labels = read(eval_dir / "fixed_choice_questions.json"), read(eval_dir / "fixed_choice_labels.json")
    label_map = {x["question_id"]: x for x in labels}
    specs = {"base": {"model_path": str(Path(base_model).resolve()), "adapter_path": None}}
    for name, path in adapters.items():
        specs[name] = {"model_path": str(Path(base_model).resolve()), "adapter_path": str(Path(path).resolve())}
    device = "cuda" if torch.cuda.is_available() else "cpu"
    predictions = []
    for name, spec in specs.items():
        tokenizer = AutoTokenizer.from_pretrained(spec["model_path"], local_files_only=True, trust_remote_code=False)
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = AutoModelForCausalLM.from_pretrained(spec["model_path"], local_files_only=True,
                                                     trust_remote_code=False, dtype=dtype)
        if spec["adapter_path"]:
            model = PeftModel.from_pretrained(model, spec["adapter_path"], local_files_only=True)
        model.to(device).eval()
        for rec in records:
            prefix = SYSTEM + "\n\n" + json.dumps({"question": rec["question"],
                "evidence": rec["evidence"]}, ensure_ascii=False) + "\n候选结论："
            scores = option_scores_batch(model, tokenizer, prefix, rec["options"], device)
            best = max(scores, key=lambda x: x["mean_logprob"])
            predictions.append({"model": name, "question_id": rec["question_id"],
                                "scores": scores, "predicted_option": best["option"],
                                "predicted_category": best["category"],
                                "correct_option": label_map[rec["question_id"]]["correct_option"],
                                "correct": best["option"] == label_map[rec["question_id"]]["correct_option"]})
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    target = Path(out) if out else eval_dir
    write(target / "fixed_choice_predictions.json", predictions)
    report = score_report(predictions, labels, records)
    write(target / "lora_fixed_choice_report.json", report)
    return report


def score_report(predictions, labels, records=None):
    label_map = {x["question_id"]: x for x in labels}
    models = sorted({p["model"] for p in predictions})
    result = {"questions": len(labels), "models": {}, "single_seed": True,
              "objective": "evidence-conditioned fixed-choice likelihood; no free generation"}
    for model in models:
        rows = [p for p in predictions if p["model"] == model]
        correct = sum(p["correct"] for p in rows)
        tp = Counter()
        pred = Counter(p["predicted_category"] for p in rows)
        for p in rows:
            if p["correct"]:
                tp["correct"] += 1
        groups = defaultdict(list)
        for p in rows:
            groups[label_map[p["question_id"]].get("evaluation_group")].append(p)
        binary_f1 = (2 * correct / (2 * correct + (len(rows) - correct) + (len(rows) - correct))
                     if rows else None)
        result["models"][model] = {
            "accuracy": correct / len(rows) if rows else None,
            "macro_f1_correct_vs_incorrect": binary_f1,
            "overclaim_rate": sum(p["predicted_category"] == "overclaim" for p in rows) / len(rows) if rows else None,
            "predicted_category_counts": dict(pred),
            "source_group_accuracy": {g: sum(p["correct"] for p in rs) / len(rs) for g, rs in groups.items()},
        }
    # Transparent non-model baselines.
    majority = Counter(x["correct_option"] for x in labels).most_common(1)[0][0]
    keyword_accuracy = None
    if records:
        rec_map = {r["question_id"]: r for r in records}
        keyword_preds = []
        for label in labels:
            rec = rec_map[label["question_id"]]
            context = terms(rec["question"] + " " + json.dumps(rec["evidence"], ensure_ascii=False))
            scores = [len(context & terms(opt["text"])) for opt in rec["options"]]
            keyword_preds.append(max(range(len(scores)), key=lambda i: (scores[i], -i)))
        keyword_accuracy = sum(p == label["correct_option"] for p, label in zip(keyword_preds, labels)) / len(labels)
    result["baselines"] = {
        "majority_option": majority,
        "majority_accuracy": sum(x["correct_option"] == majority for x in labels) / len(labels),
        "keyword_accuracy": keyword_accuracy,
        "keyword_method": "question+evidence token overlap with option text",
    }
    if "balanced_negative" in result["models"]:
        for other in ("base", "positive_only", "domain_control"):
            if other in result["models"]:
                result.setdefault("balanced_negative_deltas", {})[other] = {
                    "accuracy_delta": result["models"]["balanced_negative"]["accuracy"] - result["models"][other]["accuracy"],
                    "overclaim_rate_delta": result["models"]["balanced_negative"]["overclaim_rate"] - result["models"][other]["overclaim_rate"],
                }
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--questions", required=True, type=Path)
    a.add_argument("--trial", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    b = sub.add_parser("run")
    b.add_argument("--eval-dir", required=True, type=Path)
    b.add_argument("--base-model", required=True, type=Path)
    b.add_argument("--positive-adapter", required=True, type=Path)
    b.add_argument("--domain-adapter", required=True, type=Path)
    b.add_argument("--balanced-adapter", required=True, type=Path)
    b.add_argument("--out", type=Path)
    args = vars(p.parse_args())
    if args.pop("command") == "prepare":
        print(json.dumps(prepare(**args), ensure_ascii=False, indent=2))
    else:
        adapters = {"positive_only": args.pop("positive_adapter"),
                    "domain_control": args.pop("domain_adapter"),
                    "balanced_negative": args.pop("balanced_adapter")}
        print(json.dumps(run(adapters=adapters, **args), ensure_ascii=False, indent=2))
