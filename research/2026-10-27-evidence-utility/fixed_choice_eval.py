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
    """Legacy development options retained for reproducibility only."""
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


def visible_length(text):
    return len(re.sub(r"\s+", "", str(text)))


def normalize_insufficient_option(options):
    """Make the experiment-status distractor comparable in length without adding facts."""
    result = [dict(option) for option in options]
    correct = next(o for o in result if o.get("category") == "correct")
    insufficient = next(o for o in result if o.get("category") == "insufficient")
    text = str(correct.get("text") or "").strip()
    marker = "结果为："
    if marker in text:
        prefix, observation = text.split(marker, 1)
        insufficient["text"] = (prefix + marker + "论文未报告是否“" + observation.rstrip("。") +
                                "”，故结果无法判断。")
    else:
        insufficient["text"] = "论文未报告是否“" + text.rstrip("。") + "”，故结果无法判断。"
    insufficient["changed_field"] = "experiment_status"
    return result


def validate_authored_options(authored, questions, evidence_by_question):
    """Validate a blinded, human/model-authored hard-choice packet before inference."""
    expected = {q["question_id"]: q for q in questions}
    rows = {r.get("question_id"): r for r in authored}
    if None in rows or len(rows) != len(authored) or set(rows) != set(expected):
        raise ValueError("Authored options must cover each frozen question exactly once")
    positions, issues = Counter(), []
    records, labels = [], []
    for qid in expected:
        q, row = expected[qid], rows[qid]
        options = normalize_insufficient_option(row.get("options") or [])
        categories = [o.get("category") for o in options]
        if len(options) != 4 or Counter(categories) != Counter(CATEGORIES):
            issues.append({"question_id": qid, "code": "category_contract"})
            continue
        correct = categories.index("correct")
        if row.get("correct_option") != correct:
            issues.append({"question_id": qid, "code": "correct_position_mismatch"})
        positions[correct] += 1
        texts = [str(o.get("text") or "").strip() for o in options]
        lengths = [visible_length(x) for x in texts]
        ratio = max(lengths) / min(lengths) if min(lengths) else math.inf
        if ratio > 1.35:
            issues.append({"question_id": qid, "code": "option_length_ratio", "value": ratio})
        reference = re.sub(r"\s+", " ", str(q.get("reference_answer") or "")).strip().casefold()
        correct_text = re.sub(r"\s+", " ", texts[correct]).strip().casefold()
        if not correct_text or correct_text == reference or reference in correct_text:
            issues.append({"question_id": qid, "code": "reference_copy"})
        if len(set(texts)) != 4:
            issues.append({"question_id": qid, "code": "duplicate_option_text"})
        for option in options:
            if option.get("category") != "correct" and not option.get("changed_field"):
                issues.append({"question_id": qid, "code": "missing_changed_field",
                               "category": option.get("category")})
        evidence = evidence_by_question[qid]
        allowed = {e["evidence_id"] for e in evidence}
        used = set(row.get("evidence_ids_used") or [])
        if not used or not used <= allowed:
            issues.append({"question_id": qid, "code": "evidence_identity"})
        records.append({"question_id": qid, "question": q["question"], "evidence": evidence,
                        "options": [{"category": o["category"], "text": texts[i]}
                                    for i, o in enumerate(options)],
                        "messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": json.dumps({
                                         "question": q["question"], "evidence": evidence
                                     }, ensure_ascii=False)}]})
        labels.append({"question_id": qid, "correct_option": correct,
                       "correct_category": "correct", "evaluation_group": q.get("evaluation_group"),
                       "source_dois": q.get("source_dois", [])})
    if sorted(positions.values()) != [14, 14, 14, 15]:
        issues.append({"question_id": None, "code": "answer_position_balance", "value": dict(positions)})
    return records, labels, issues, dict(positions)


def keyword_baseline(records, labels):
    label_map = {x["question_id"]: x for x in labels}
    predictions = []
    for rec in records:
        context = terms(rec["question"] + " " + json.dumps(rec["evidence"], ensure_ascii=False))
        scores = [len(context & terms(opt["text"])) for opt in rec["options"]]
        predictions.append({"question_id": rec["question_id"],
                            "option": max(range(len(scores)), key=lambda i: (scores[i], -i))})
    return sum(x["option"] == label_map[x["question_id"]]["correct_option"]
               for x in predictions) / len(predictions)


def prepare(questions, trial, out, seed=20261027, authored_options=None,
            review_a=None, review_b=None, adjudications=None):
    questions, trial, out = Path(questions), Path(trial), Path(out)
    qs = read(questions)
    if len(qs) != 57 or any(q.get("split") != "test" for q in qs):
        raise ValueError("Fixed-choice evaluation requires the frozen 57-question test set")
    tasks = {t["question_id"]: t for t in read(trial / "tasks.json") if t["arm"] == "recovered"}
    if len(tasks) != len(qs):
        raise ValueError("Recovered context must cover all 57 questions")
    evidence_by_question = {}
    for q in qs:
        task = tasks[q["question_id"]]
        user_payload = json.loads(task["messages"][-1]["content"])
        reference = [{"evidence_id": f'reference:{q["question_id"]}:{i}', "text": text,
                      "doi": (q.get("source_dois") or [None])[0], "kind": "frozen_reference_excerpt"}
                     for i, text in enumerate(q.get("reference_evidence") or [])]
        if not reference:
            raise ValueError("Every fixed-choice question requires frozen direct evidence")
        evidence_by_question[q["question_id"]] = reference + user_payload.get("evidence", [])
    authored_path = Path(authored_options) if authored_options else None
    if authored_path:
        records, labels, issues, positions = validate_authored_options(
            read(authored_path), qs, evidence_by_question)
    else:
        records, labels, issues, positions = [], [], [], Counter()
        for i, q in enumerate(qs):
            options = make_options(q, evidence_by_question[q["question_id"]], i, seed)
            correct = next(j for j, o in enumerate(options) if o["category"] == "correct")
            positions[correct] += 1
            labels.append({"question_id": q["question_id"], "correct_option": correct,
                           "correct_category": "correct", "evaluation_group": q.get("evaluation_group"),
                           "source_dois": q.get("source_dois", [])})
            records.append({"question_id": q["question_id"], "question": q["question"],
                            "evidence": evidence_by_question[q["question_id"]], "options": options,
                            "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": json.dumps({
                                             "question": q["question"],
                                             "evidence": evidence_by_question[q["question_id"]]
                                         }, ensure_ascii=False)}]})
    keyword = keyword_baseline(records, labels) if records and not issues else None
    gate = {"status": "pass" if not issues and keyword < .70 else "blocked",
            "questions": len(records), "structural_issues": issues,
            "answer_position_counts": dict(positions), "keyword_accuracy": keyword,
            "requirements": {"questions": 57, "maximum_length_ratio": 1.35,
                             "maximum_keyword_accuracy_exclusive": .70,
                             "answer_position_counts_sorted": [14, 14, 14, 15]}}
    out = fresh(out)
    write(out / "fixed_choice_questions.json", records)
    write(out / "fixed_choice_labels.json", labels)
    write(out / "quality_gate.json", gate)
    review_paths = [Path(x) for x in (review_a, review_b, adjudications) if x]
    if review_paths:
        if len(review_paths) != 3:
            raise ValueError("Reviewer A, Reviewer B and adjudications must be supplied together")
        expected_ids = {q["question_id"] for q in qs}
        for path in review_paths:
            rows = read(path)
            ids = [x.get("question_id") for x in rows]
            if len(ids) != 57 or len(set(ids)) != 57 or set(ids) != expected_ids:
                raise ValueError("Review/adjudication coverage must be exactly the frozen 57 questions")
        write(out / "review_provenance.json", {
            "review_a_sha256": sha(review_paths[0]), "review_b_sha256": sha(review_paths[1]),
            "adjudications_sha256": sha(review_paths[2]),
            "coverage": 57, "provenance": "two independent Luna model-assisted reviews plus model-assisted adjudication; not expert gold"
        })
    write(out / "config.json", {"seed": seed, "questions": len(records),
                                 "models": ["base", "positive_only", "domain_control", "balanced_negative"],
                                 "scoring": "mean conditional log-likelihood over option tokens"})
    inputs = [questions, trial / "manifest.json"] + ([authored_path] if authored_path else []) + review_paths
    seal(out, inputs, {"artifact": "fixed_choice_evaluation", "api_requests": 0,
                       "quality_gate": gate["status"]})
    return {"questions": len(records), "options": len(records) * 4, "api_requests": 0,
            "quality_gate": gate["status"], "keyword_accuracy": keyword}


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
    gate_path = eval_dir / "quality_gate.json"
    if gate_path.exists() and read(gate_path).get("status") != "pass":
        raise ValueError("Fixed-choice quality gate has not passed")
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
        if len(rows) != len(labels) or len({p["question_id"] for p in rows}) != len(labels):
            raise ValueError("Every model must cover the complete fixed-choice denominator")
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
        margins = []
        for p in rows:
            if p.get("scores"):
                correct_option = label_map[p["question_id"]]["correct_option"]
                correct_score = next(x["mean_logprob"] for x in p["scores"] if x["option"] == correct_option)
                distractor = max(x["mean_logprob"] for x in p["scores"] if x["option"] != correct_option)
                margins.append(correct_score - distractor)
        result["models"][model] = {
            "accuracy": correct / len(rows) if rows else None,
            "macro_f1_correct_vs_incorrect": binary_f1,
            "overclaim_rate": sum(p["predicted_category"] == "overclaim" for p in rows) / len(rows) if rows else None,
            "predicted_category_counts": dict(pred),
            "distractor_selection_rates": {c: pred[c] / len(rows) for c in CATEGORIES if c != "correct"},
            "mean_correct_minus_best_distractor_logprob": sum(margins) / len(margins) if margins else None,
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
                result["balanced_negative_deltas"][other]["doi_cluster_bootstrap"] = paired_accuracy_bootstrap(
                    [p for p in predictions if p["model"] == "balanced_negative"],
                    [p for p in predictions if p["model"] == other], label_map)
    accuracies = [x["accuracy"] for x in result["models"].values()]
    result["quality_gate"] = {
        "status": "blocked_non_discriminative" if accuracies and min(accuracies) >= .95 else "pass",
        "all_models_at_least_95_percent": bool(accuracies and min(accuracies) >= .95),
        "keyword_below_70_percent": keyword_accuracy is not None and keyword_accuracy < .70,
    }
    return result


def paired_accuracy_bootstrap(first, second, label_map, seed=20261027, draws=2000):
    second_map = {x["question_id"]: x for x in second}
    groups = defaultdict(list)
    for row in first:
        other = second_map[row["question_id"]]
        group = label_map[row["question_id"]].get("evaluation_group")
        groups[group].append(int(row["correct"]) - int(other["correct"]))
    names = sorted(groups, key=str)
    observed_values = [v for name in names for v in groups[name]]
    observed = sum(observed_values) / len(observed_values)
    rng, samples = random.Random(seed), []
    for _ in range(draws):
        selected = [rng.choice(names) for _ in names]
        values = [v for name in selected for v in groups[name]]
        samples.append(sum(values) / len(values))
    samples.sort()
    return {"groups": len(names), "delta_accuracy": observed,
            "ci95": [samples[int(.025 * draws)], samples[min(draws - 1, int(.975 * draws))]]}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--questions", required=True, type=Path)
    a.add_argument("--trial", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    a.add_argument("--authored-options", type=Path)
    a.add_argument("--review-a", type=Path)
    a.add_argument("--review-b", type=Path)
    a.add_argument("--adjudications", type=Path)
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
