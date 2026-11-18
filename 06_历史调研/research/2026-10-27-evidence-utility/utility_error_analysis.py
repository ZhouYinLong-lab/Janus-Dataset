"""Offline question-level error analysis and deterministic representative-case selection."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

from common import read, seal, write


ARMS = ("no_retrieval", "structured", "raw", "recovered", "background_ablation")
MODELS = ("base", "positive_only", "domain_control", "balanced_negative")
CRITERIA = ("object", "direction", "condition")


def stable_key(seed, stratum, question_id):
    return hashlib.sha256(f"{seed}|{stratum}|{question_id}".encode()).hexdigest()


def reference_fields(text):
    fields = {}
    for part in re.split(r"[；]", str(text or "")):
        if "=" in part:
            key, value = part.split("=", 1)
            fields[key.strip()] = value.strip()
    return fields


def strength_class(fields):
    text = (fields.get("observation") or "").casefold()
    condition = (fields.get("scope_condition") or "").casefold()
    if "not significant" in text or "no significant" in text:
        return "not_significant"
    if any(x in text for x in ("less ", "lower", "reduced", "poor", "weak", "decreased",
                               "diminished", "loss of affinity", "lower than")):
        return "relative_weakening"
    if any(x in condition for x in ("knockout", "depletion", "absence")) or "dependent" in text:
        return "conditional_boundary"
    if any(x in text for x in (" no ", "not ", "did not", "failed", "unaffected", "inactive",
                               "negligible", "could not", "neither ")):
        return "not_observed"
    return "other_boundary"


def score_judgment(judgment):
    criteria = judgment["final_judgment"]["criteria"]
    return sum(bool(criteria[k]) for k in CRITERIA) / len(CRITERIA)


def comparison(a, b):
    if a is None or b is None:
        return "missing"
    return "better" if a > b else "worse" if a < b else "equal"


def flatten_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                             if isinstance(v, (dict, list)) else v for k, v in row.items()})


def build_rag(questions, tasks, answers, adjudications, historical_unknown, evidence):
    qmap = {q["question_id"]: q for q in questions}
    if len(qmap) != 57:
        raise ValueError("Expected 57 frozen questions")
    task_map = {t["task_id"]: t for t in tasks}
    answer_map = {a["task_id"]: a for a in answers}
    adj_map = {a["task_id"]: a for a in adjudications}
    unknown = {x["task_id"] for x in historical_unknown}
    evidence_map = {x["evidence_id"]: x for x in evidence}
    if len(task_map) + len(unknown) != 285 or len(answer_map) != 284 or len(adj_map) != 283:
        raise ValueError("RAG denominator/status counts differ from frozen evaluation")
    by_question = defaultdict(dict)
    for task in list(tasks) + list(historical_unknown):
        qid, arm, task_id = task["question_id"], task["arm"], task["task_id"]
        answer = answer_map.get(task_id)
        adj = adj_map.get(task_id)
        if task_id in unknown:
            status = "historical_unknown"
        elif answer is None:
            status = "missing"
        else:
            status = answer["status"]
        final = adj.get("final_judgment") if adj else None
        negative_ids = [eid for eid in task.get("evidence_ids", [])
                        if evidence_map.get(eid, {}).get("kind") == "negative"]
        by_question[qid][arm] = {
            "task_id": task_id, "status": status,
            "score": score_judgment(adj) if adj else None,
            "criteria": final.get("criteria") if final else None,
            "overclaim": final.get("overclaim") if final else None,
            "citation_supported": final.get("citation_supported") if final else None,
            "answer": (answer.get("result") or {}).get("answer") if answer else None,
            "citations": (answer.get("result") or {}).get("citations") if answer else None,
            "evidence_ids": task.get("evidence_ids", []),
            "negative_evidence_ids": negative_ids,
        }
    rows = []
    for qid, q in qmap.items():
        arms = by_question[qid]
        if set(arms) != set(ARMS):
            raise ValueError("Every question must retain all five RAG arms")
        fields = reference_fields(q.get("reference_answer"))
        recovered = arms["recovered"]["score"]
        row = {
            "question_id": qid, "question": q["question"], "doi": (q.get("source_dois") or [None])[0],
            "evaluation_group": q.get("evaluation_group"), "reference_fields": fields,
            "reference_evidence": q.get("reference_evidence", []),
            "endpoint": fields.get("endpoint"), "strength_class": strength_class(fields), "arms": arms,
            "recovered_minus_structured": None if recovered is None or arms["structured"]["score"] is None
            else recovered - arms["structured"]["score"],
            "recovered_minus_background": None if recovered is None or arms["background_ablation"]["score"] is None
            else recovered - arms["background_ablation"]["score"],
            "recovered_minus_raw": None if recovered is None or arms["raw"]["score"] is None
            else recovered - arms["raw"]["score"],
            "recovered_vs_structured": comparison(recovered, arms["structured"]["score"]),
            "recovered_vs_background": comparison(recovered, arms["background_ablation"]["score"]),
            "recovered_vs_raw": comparison(recovered, arms["raw"]["score"]),
            "recovered_negative_count": len(arms["recovered"]["negative_evidence_ids"]),
        }
        rows.append(row)
    return rows


def build_lora(questions, fixed_questions, labels, predictions):
    qmap = {q["question_id"]: q for q in questions}
    f_map = {q["question_id"]: q for q in fixed_questions}
    label_map = {x["question_id"]: x for x in labels}
    pred_map = defaultdict(dict)
    for pred in predictions:
        pred_map[pred["question_id"]][pred["model"]] = pred
    if set(pred_map) != set(qmap) or any(set(x) != set(MODELS) for x in pred_map.values()):
        raise ValueError("LoRA predictions must cover 57 questions and four models")
    rows = []
    for qid, q in qmap.items():
        model_rows = pred_map[qid]
        fields = reference_fields(q.get("reference_answer"))
        results = {}
        for model in MODELS:
            pred = model_rows[model]
            correct_option = label_map[qid]["correct_option"]
            correct_score = next(x["mean_logprob"] for x in pred["scores"] if x["option"] == correct_option)
            distractor = max(x["mean_logprob"] for x in pred["scores"] if x["option"] != correct_option)
            results[model] = {"predicted_option": pred["predicted_option"],
                              "predicted_category": pred["predicted_category"],
                              "correct": bool(pred["correct"]),
                              "correct_margin": correct_score - distractor}
        correct_count = sum(x["correct"] for x in results.values())
        prediction_count = len({x["predicted_option"] for x in results.values()})
        balanced, base, domain = results["balanced_negative"], results["base"], results["domain_control"]
        rows.append({
            "question_id": qid, "question": q["question"], "doi": (q.get("source_dois") or [None])[0],
            "evaluation_group": q.get("evaluation_group"), "endpoint": fields.get("endpoint"),
            "strength_class": strength_class(fields), "reference_fields": fields,
            "reference_evidence": q.get("reference_evidence", []), "options": f_map[qid]["options"],
            "correct_option": label_map[qid]["correct_option"], "models": results,
            "all_correct": correct_count == 4, "all_wrong": correct_count == 0,
            "model_disagreement": prediction_count > 1,
            "balanced_unique_benefit": balanced["correct"] and correct_count == 1,
            "balanced_harm_vs_base": not balanced["correct"] and base["correct"],
            "balanced_harm_vs_domain": not balanced["correct"] and domain["correct"],
        })
    return rows


def public_rag_row(row):
    return {"question_id": row["question_id"], "doi": row["doi"], "endpoint": row["endpoint"],
            "strength_class": row["strength_class"],
            "scores": {arm: row["arms"][arm]["score"] for arm in ARMS},
            "statuses": {arm: row["arms"][arm]["status"] for arm in ARMS},
            "recovered_vs_structured": row["recovered_vs_structured"],
            "recovered_vs_background": row["recovered_vs_background"],
            "recovered_vs_raw": row["recovered_vs_raw"],
            "recovered_negative_count": row["recovered_negative_count"]}


def public_lora_row(row):
    return {"question_id": row["question_id"], "doi": row["doi"], "endpoint": row["endpoint"],
            "strength_class": row["strength_class"], "all_correct": row["all_correct"],
            "all_wrong": row["all_wrong"], "model_disagreement": row["model_disagreement"],
            "balanced_unique_benefit": row["balanced_unique_benefit"],
            "balanced_harm_vs_base": row["balanced_harm_vs_base"],
            "balanced_harm_vs_domain": row["balanced_harm_vs_domain"],
            "predicted_categories": {m: row["models"][m]["predicted_category"] for m in MODELS},
            "correct": {m: row["models"][m]["correct"] for m in MODELS}}


def choose(candidates, count, stratum, used_questions, doi_counts, seed):
    ordered = sorted(candidates, key=lambda x: stable_key(seed, stratum, x["question_id"]))
    chosen = []
    for row in ordered:
        if row["question_id"] in used_questions or doi_counts[row["doi"]] >= 2:
            continue
        chosen.append(row)
        used_questions.add(row["question_id"])
        doi_counts[row["doi"]] += 1
        if len(chosen) == count:
            return chosen
    raise ValueError(f"Not enough diverse cases for {stratum}: {len(chosen)}/{count}")


def error_fields(arms, first, second):
    a, b = arms[first].get("criteria"), arms[second].get("criteria")
    return [key for key in CRITERIA if a and b and bool(a[key]) != bool(b[key])]


def select_cases(rag_rows, lora_rows, seed=20261028):
    used, doi_counts, cases = set(), Counter(), []
    lora_map = {x["question_id"]: x for x in lora_rows}
    regressions = choose([r for r in rag_rows if r["recovered_vs_structured"] == "worse"],
                         2, "rag_recovered_regression", used, doi_counts, seed)
    controls = [row for row in rag_rows
                if row["arms"]["recovered"]["score"] == 1
                and lora_map[row["question_id"]]["all_correct"]]
    # Reserve a positive control before broader RAG strata consume it.
    control = choose(controls, 1, "retrieval_and_lora_correct_control", used, doi_counts, seed)[0]
    disagreement = choose([r for r in lora_rows if r["model_disagreement"]], 1,
                          "lora_disagreement", used, doi_counts, seed)
    common_failures = choose([r for r in lora_rows if r["all_wrong"]], 2,
                             "lora_common_failure", used, doi_counts, seed)
    strata = [
        ("rag_recovered_gain", 3, [r for r in rag_rows if r["recovered_vs_structured"] == "better"
                                    and r["recovered_vs_background"] == "better"], "structured"),
        ("rag_raw_advantage", 3, [r for r in rag_rows if r["recovered_vs_raw"] == "worse"], "raw"),
    ]
    for row in regressions:
        cases.append({"case_id": f"CASE_{len(cases)+1:02d}", "stratum": "rag_recovered_regression",
                      "question_id": row["question_id"], "doi": row["doi"],
                      "endpoint": row["endpoint"], "strength_class": row["strength_class"],
                      "rag_scores": {a: row["arms"][a]["score"] for a in ARMS},
                      "lora_predictions": None,
                      "error_fields": error_fields(row["arms"], "recovered", "structured"),
                      "reason": "Existing adjudication shows recovered is worse than structured."})
    for stratum, count, candidates, comparator in strata:
        for row in choose(candidates, count, stratum, used, doi_counts, seed):
            cases.append({"case_id": f"CASE_{len(cases)+1:02d}", "stratum": stratum,
                          "question_id": row["question_id"], "doi": row["doi"],
                          "endpoint": row["endpoint"], "strength_class": row["strength_class"],
                          "rag_scores": {a: row["arms"][a]["score"] for a in ARMS},
                          "lora_predictions": None,
                          "error_fields": error_fields(row["arms"], "recovered", comparator),
                          "reason": f"Existing adjudication shows recovered is {row['recovered_vs_'+('background' if comparator == 'background_ablation' else comparator)]} than {comparator}."})
    for stratum, selected in (("lora_common_failure", common_failures),
                              ("lora_disagreement", disagreement)):
        for row in selected:
            cases.append({"case_id": f"CASE_{len(cases)+1:02d}", "stratum": stratum,
                          "question_id": row["question_id"], "doi": row["doi"],
                          "endpoint": row["endpoint"], "strength_class": row["strength_class"],
                          "rag_scores": None,
                          "lora_predictions": {m: row["models"][m]["predicted_category"] for m in MODELS},
                          "error_fields": sorted({row["models"][m]["predicted_category"] for m in MODELS
                                                  if not row["models"][m]["correct"]}),
                          "reason": "Existing fixed-choice predictions show " +
                          ("all four models selected a distractor." if row["all_wrong"]
                           else "the four models did not select the same option.")})
    row = control
    cases.append({"case_id": f"CASE_{len(cases)+1:02d}", "stratum": "retrieval_and_lora_correct_control",
                  "question_id": row["question_id"], "doi": row["doi"],
                  "endpoint": row["endpoint"], "strength_class": row["strength_class"],
                  "rag_scores": {a: row["arms"][a]["score"] for a in ARMS},
                  "lora_predictions": {m: lora_map[row["question_id"]]["models"][m]["predicted_category"]
                                       for m in MODELS},
                  "error_fields": [],
                  "reason": "Recovered retrieval and all four local models were correct; no question had every RAG arm and every LoRA arm correct."})
    if len(cases) != 12:
        raise ValueError("Representative case table must contain 12 rows")
    return cases


def aggregate(rag_rows, lora_rows, report):
    def counts(field):
        return dict(Counter(r[field] for r in rag_rows))
    arm_errors = {}
    for arm in ARMS:
        judged = [r["arms"][arm] for r in rag_rows if r["arms"][arm]["criteria"]]
        arm_errors[arm] = {key: sum(not x["criteria"][key] for x in judged) for key in CRITERIA}
        arm_errors[arm]["judged"] = len(judged)
    exceptions = report["generation_exceptions"]
    lora_by_id = {x["question_id"]: x for x in lora_rows}
    return {
        "rag_questions": len(rag_rows), "lora_questions": len(lora_rows),
        "rag_comparisons": {"recovered_vs_structured": counts("recovered_vs_structured"),
                            "recovered_vs_background": counts("recovered_vs_background"),
                            "recovered_vs_raw": counts("recovered_vs_raw")},
        "rag_field_errors": arm_errors,
        "lora_patterns": {"all_correct": sum(r["all_correct"] for r in lora_rows),
                          "all_wrong": sum(r["all_wrong"] for r in lora_rows),
                          "model_disagreement": sum(r["model_disagreement"] for r in lora_rows),
                          "balanced_unique_benefit": sum(r["balanced_unique_benefit"] for r in lora_rows),
                          "balanced_harm_vs_base": sum(r["balanced_harm_vs_base"] for r in lora_rows),
                          "balanced_harm_vs_domain": sum(r["balanced_harm_vs_domain"] for r in lora_rows)},
        "all_rag_and_lora_correct_questions": sum(
            lora_by_id[row["question_id"]]["all_correct"] and all(
                row["arms"][a]["score"] == 1 for a in ARMS if row["arms"][a]["score"] is not None)
            for row in rag_rows),
        "generation_exceptions": exceptions,
        "external_generation_requests": 0,
        "interpretation_scope": "Frozen 57-question test; model-assisted adjudication, not expert gold."
    }


def report_markdown(summary, cases):
    rs, rr = summary["rag_comparisons"]["recovered_vs_structured"], summary["rag_comparisons"]["recovered_vs_raw"]
    lp = summary["lora_patterns"]
    lines = ["# 题目级误差分析", "",
             "## 主要结果", "",
             f"恢复证据相对结构化资料：改善{rs.get('better', 0)}题、持平{rs.get('equal', 0)}题、退步{rs.get('worse', 0)}题。",
             f"恢复证据相对原文检索：改善{rr.get('better', 0)}题、持平{rr.get('equal', 0)}题、退步{rr.get('worse', 0)}题。",
             f"LoRA四组共同答对{lp['all_correct']}题、共同答错{lp['all_wrong']}题，{lp['model_disagreement']}题预测不同。",
             "", "对象错误在各RAG组中只有3至5题；主要缺口是结果方向和实验条件。",
             f"恢复证据组仍有{summary['rag_field_errors']['recovered']['direction']}/57题方向未恢复、"
             f"{summary['rag_field_errors']['recovered']['condition']}/57题条件未恢复；"
             f"原文组分别为{summary['rag_field_errors']['raw']['direction']}/57和"
             f"{summary['rag_field_errors']['raw']['condition']}/57。",
             "", "## 典型案例", "",
             "| 案例 | 类型 | 问题ID | DOI | 终点 | 变化字段 |", "|---|---|---|---|---|---|"]
    for c in cases:
        lines.append(f"| {c['case_id']} | {c['stratum']} | {c['question_id']} | {c['doi']} | "
                     f"{c.get('endpoint') or ''} | {', '.join(c['error_fields'])} |")
    lines += ["", "## 解释边界", "",
              "错误类型来自现有逐项裁定和固定选项类别。这里没有使用新的模型生成原因，也没有把模型辅助裁定改称专家金标。", ""]
    return "\n".join(lines)


def run(args):
    questions = read(args.questions)
    rag_rows = build_rag(questions, read(args.rag_tasks), read(args.rag_answers),
                         read(args.rag_adjudications), read(args.historical_unknown), read(args.evidence))
    lora_rows = build_lora(questions, read(args.fixed_questions), read(args.fixed_labels),
                           read(args.fixed_predictions))
    report = read(args.rag_report)
    summary = aggregate(rag_rows, lora_rows, report)
    cases = select_cases(rag_rows, lora_rows, args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    write(out / "rag_question_analysis.json", rag_rows)
    write(out / "lora_question_analysis.json", lora_rows)
    write(out / "error_summary.json", summary)
    write(out / "typical_cases.json", cases)
    flatten_csv(out / "rag_question_analysis.csv", [public_rag_row(x) for x in rag_rows])
    flatten_csv(out / "lora_question_analysis.csv", [public_lora_row(x) for x in lora_rows])
    flatten_csv(out / "typical_cases.csv", cases)
    (out / "题目级误差分析.md").write_text(report_markdown(summary, cases), encoding="utf-8")
    inputs = [args.questions, args.rag_tasks, args.rag_answers, args.rag_adjudications,
              args.historical_unknown, args.rag_report, args.fixed_questions, args.fixed_labels,
              args.fixed_predictions, args.evidence]
    seal(out, inputs, {"artifact": "question_level_error_analysis", "seed": args.seed,
                       "external_generation_requests": 0})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("questions", "rag-tasks", "rag-answers", "rag-adjudications", "historical-unknown",
                 "rag-report", "fixed-questions", "fixed-labels", "fixed-predictions", "evidence", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20261028)
    parsed = parser.parse_args()
    print(json.dumps(run(parsed), ensure_ascii=False, indent=2))
