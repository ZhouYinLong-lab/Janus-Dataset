"""Validate checked-in large/small prediction summaries against local outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def close(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads((args.run_dir / "report.json").read_text(encoding="utf-8"))
    predictions = json.loads((args.run_dir / "predictions.json").read_text(encoding="utf-8"))
    tasks = json.loads((args.run_dir / "prediction_tasks.json").read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))

    assert report["coverage"] == {
        "test_predictions": 192,
        "expected_predictions": 192,
        "failures": 0,
    }
    assert report["large_model"]["requested_model"] == "deepseek-v4-pro"
    assert report["large_model"]["successful_requests"] == 10
    assert report["large_model"]["failed_requests"] == 1
    assert summary["protocol"]["total_scored_predictions"] == len(predictions) == 192
    assert summary["protocol"]["synthetic_labels"] == report["synthetic_labels"] == 0

    actual = {row["arm"]: row for row in report["large_model"]["summary"]}
    frozen = {row["arm"]: row for row in summary["large_model_results"]}
    for arm, row in frozen.items():
        assert close(row["accuracy"], actual[arm]["accuracy_mean"])
        assert close(row["macro_f1"], actual[arm]["macro_f1_mean"])
        assert close(row["auroc"], actual[arm]["auroc_mean"])
        assert close(
            row["negative_false_positive_rate"],
            actual[arm]["negative_false_positive_rate_mean"],
        )

    traditional_actual = {
        (row["arm"], row["model"]): row
        for row in report["traditional_small_models"]
    }
    for row in summary["traditional_recovered_balanced_results"]:
        measured = traditional_actual[("recovered_balanced", row["model"])]
        assert close(row["accuracy"], measured["accuracy_mean"])
        assert close(row["macro_f1"], measured["macro_f1_mean"])
        assert close(row["auroc"], measured["auroc_mean"])
        assert close(
            row["negative_false_positive_rate"],
            measured["negative_false_positive_rate_mean"],
        )

    for split in tasks["splits"]:
        ids = {row["task_id"] for row in split["test"]}
        assert len(ids) == len(split["test"])
        for row in split["test"]:
            assert not ({"label", "doi", "source"} & set(row))
        for arm, demonstrations in split["demonstrations"].items():
            if arm == "zero_shot":
                assert demonstrations == []
            else:
                labels = [row["observed_degradation"] for row in demonstrations]
                assert labels.count(0) == labels.count(1) == 4

    grouped: dict[tuple[int, str], set[str]] = {}
    for row in predictions:
        grouped.setdefault((row["seed"], row["arm"]), set()).add(row["task_id"])
    for seed in (20261029, 20261030, 20261031):
        reference = grouped[(seed, "zero_shot")]
        assert grouped[(seed, "structured_negative_fewshot")] == reference
        assert grouped[(seed, "recovered_negative_fewshot")] == reference

    for request_path in (args.run_dir / "requests").glob("nothink_*.json"):
        request = json.loads(request_path.read_text(encoding="utf-8"))
        assert request["thinking"] == {"type": "disabled"}
        user_payload = json.loads(request["messages"][1]["content"])
        for row in user_payload["prediction_cases"]:
            assert not ({"label", "doi", "source", "observed_degradation"} & set(row))

    print("prediction route validation passed: 192 scored predictions, no label leakage")


if __name__ == "__main__":
    main()
