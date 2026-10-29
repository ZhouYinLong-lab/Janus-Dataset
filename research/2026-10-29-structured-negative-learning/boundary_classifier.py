"""Balanced structured prediction using recovered narrative negatives.

Three equal-sized training arms are compared on the same DOI-held-out test set:
positive-biased, structured-negative balanced, and recovered-negative balanced.
The experiment uses no generated labels and excludes condition fields because
the structured positive pool lacks comparable condition coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


SEEDS = (20261029, 20261030, 20261031)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def entity_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["canonical_smiles"]),
        str(row["target_normalized"]),
        str(row["e3_normalized"]),
    )


def as_training_row(row: dict[str, Any], label: int, source: str) -> dict[str, Any]:
    e3 = row.get("e3_normalized") or str(row.get("e3", "")).lower()
    return {
        "record_id": row.get("mapping_id") or row.get("positive_id") or row.get("structured_id"),
        "doi": str(row["doi"]),
        "canonical_smiles": str(row["canonical_smiles"]),
        "target_normalized": str(row["target_normalized"]),
        "e3_normalized": str(e3),
        "label": int(label),
        "source": source,
    }


class FeatureBuilder:
    def __init__(self, fp_size: int = 1024):
        self.fp_size = fp_size
        self.generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=fp_size)
        self.categories = OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32)

    @staticmethod
    def categorical(rows: list[dict[str, Any]]) -> np.ndarray:
        return np.asarray(
            [[row["target_normalized"], row["e3_normalized"]] for row in rows],
            dtype=object,
        )

    def fit(self, rows: list[dict[str, Any]]) -> "FeatureBuilder":
        self.categories.fit(self.categorical(rows))
        return self

    def fingerprint(self, smiles: str) -> np.ndarray:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"invalid SMILES: {smiles}")
        bitvect = self.generator.GetFingerprint(mol)
        array = np.zeros(self.fp_size, dtype=np.int8)
        DataStructs.ConvertToNumpyArray(bitvect, array)
        return array.astype(np.float32)

    def transform(self, rows: list[dict[str, Any]]) -> np.ndarray:
        fingerprints = np.vstack([self.fingerprint(row["canonical_smiles"]) for row in rows])
        categories = self.categories.transform(self.categorical(rows))
        return np.hstack([fingerprints, categories]).astype(np.float32)


def build_structured_negatives(train_csv: Path, provenance_csv: Path) -> list[dict[str, Any]]:
    train = pd.read_csv(train_csv)
    provenance = pd.read_csv(provenance_csv)
    zero = train[train["Score"] == 0].copy()
    provenance = provenance[
        (provenance["benchmark_split"] == "train")
        & provenance["source_doi"].notna()
        & provenance["mapping_status"].astype(str).str.startswith("verified_")
    ].copy()
    provenance = provenance.sort_values(
        ["benchmark_id", "source_name_exact", "source_doi"],
        ascending=[True, False, True],
    ).drop_duplicates("benchmark_id")
    merged = zero.merge(
        provenance[["benchmark_id", "source_doi"]],
        left_on="id",
        right_on="benchmark_id",
        how="inner",
        validate="one_to_one",
    )
    rows = []
    for _, row in merged.iterrows():
        mol = Chem.MolFromSmiles(str(row["Molecule_SMILES"]))
        if mol is None:
            continue
        target = " ".join(str(row["PrimaryTarget"]).lower().split())
        e3 = " ".join(str(row["RecruitingProtein"]).lower().split())
        key = (str(row["source_doi"]), Chem.MolToSmiles(mol, canonical=True), target, e3)
        rows.append({
            "structured_id": "SN_" + hashlib.sha256("\x1f".join(key).encode()).hexdigest()[:20],
            "doi": key[0],
            "canonical_smiles": key[1],
            "target_normalized": target,
            "e3_normalized": e3,
            "score": 0.0,
        })
    unique = {entity_key(row): row for row in rows}
    return sorted(unique.values(), key=lambda row: row["structured_id"])


def select_test_dois(
    recovered: list[dict[str, Any]],
    positives: list[dict[str, Any]],
    seed: int,
) -> tuple[list[str], int]:
    positive_dois = {row["doi"] for row in positives}
    eligible = sorted({row["doi"] for row in recovered} & positive_dois)
    if len(eligible) < 5:
        raise ValueError("fewer than five DOI groups have both classes")
    rng = np.random.default_rng(seed)
    for attempt in range(500):
        shuffled = list(rng.permutation(eligible))
        count = max(2, int(round(len(eligible) * 0.22)))
        selected = sorted(shuffled[:count])
        negative_count = sum(row["doi"] in selected for row in recovered)
        positive_count = sum(row["doi"] in selected for row in positives)
        if negative_count >= 8 and positive_count >= 8:
            return selected, attempt
    raise ValueError("could not build a DOI-held-out test set with both classes")


def sample_rows(rows: list[dict[str, Any]], count: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    if len(rows) < count:
        raise ValueError(f"requested {count} rows from pool of {len(rows)}")
    indices = rng.choice(len(rows), size=count, replace=False)
    return [rows[int(index)] for index in sorted(indices)]


def prepare_split(
    recovered_raw: list[dict[str, Any]],
    positives_raw: list[dict[str, Any]],
    structured_raw: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    recovered = [as_training_row(row, 0, "recovered_negative") for row in recovered_raw]
    positives = [as_training_row(row, 1, "structured_positive") for row in positives_raw]
    structured = [as_training_row(row, 0, "structured_negative") for row in structured_raw]
    # Direct entity conflicts are unsuitable as positive controls.
    negative_keys = {entity_key(row) for row in recovered}
    positives = [row for row in positives if entity_key(row) not in negative_keys]
    test_dois, attempts = select_test_dois(recovered, positives, seed)
    test_negative_pool = [row for row in recovered if row["doi"] in test_dois]
    test_positive_pool = [row for row in positives if row["doi"] in test_dois]
    test_count = min(len(test_negative_pool), len(test_positive_pool), 12)
    if test_count < 8:
        raise ValueError("held-out test class has fewer than eight records")
    rng = np.random.default_rng(seed)
    test_negative = sample_rows(test_negative_pool, test_count, rng)
    test_positive = sample_rows(test_positive_pool, test_count, rng)
    test = test_negative + test_positive
    test_keys = {entity_key(row) for row in test}

    recovered_train = [
        row for row in recovered if row["doi"] not in test_dois and entity_key(row) not in test_keys
    ]
    positive_train = [
        row for row in positives if row["doi"] not in test_dois and entity_key(row) not in test_keys
    ]
    structured_train = [
        row for row in structured if row["doi"] not in test_dois and entity_key(row) not in test_keys
    ]
    n = min(len(recovered_train), len(structured_train), int(len(positive_train) / 1.5), 40)
    n -= n % 2
    if n < 24:
        raise ValueError(f"training pool too small after DOI isolation: n={n}")
    common_positive = sample_rows(positive_train, n, rng)
    extra_positive_pool = [row for row in positive_train if row not in common_positive]
    extra_positive = sample_rows(extra_positive_pool, n // 2, rng)
    structured_n = sample_rows(structured_train, n, rng)
    recovered_n = sample_rows(recovered_train, n, rng)
    arms = {
        "positive_biased": common_positive + extra_positive + structured_n[: n // 2],
        "structured_balanced": common_positive + structured_n,
        "recovered_balanced": common_positive + recovered_n,
    }
    totals = {name: len(rows) for name, rows in arms.items()}
    if len(set(totals.values())) != 1:
        raise AssertionError(f"unequal training arms: {totals}")
    test_doi_set = set(test_dois)
    test_entity_set = {entity_key(row) for row in test}
    for name, rows in arms.items():
        if {row["doi"] for row in rows} & test_doi_set:
            raise AssertionError(f"DOI leakage in {name}")
        if {entity_key(row) for row in rows} & test_entity_set:
            raise AssertionError(f"entity leakage in {name}")
    if sum(row["label"] == 0 for row in test) != sum(row["label"] == 1 for row in test):
        raise AssertionError("test classes are not balanced")
    return {
        "seed": seed,
        "test_dois": test_dois,
        "selection_attempt": attempts,
        "n_per_balanced_class": n,
        "test": test,
        "arms": arms,
        "pool_counts": {
            "recovered_train": len(recovered_train),
            "structured_train": len(structured_train),
            "positive_train": len(positive_train),
            "test_per_class": test_count,
        },
    }


def build_model(name: str, seed: int):
    if name == "logistic_regression":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=2000, random_state=seed),
        )
    if name == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=400,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        )
    if name == "mlp":
        return make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(64,), alpha=1e-3, max_iter=500,
                random_state=seed,
            ),
        )
    raise ValueError(name)


def classification_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    probability = np.clip(np.asarray(probability, dtype=float), 0.0, 1.0)
    prediction = (probability >= 0.5).astype(int)
    negative = y == 0
    return {
        "accuracy": float(accuracy_score(y, prediction)),
        "macro_f1": float(f1_score(y, prediction, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
        "auroc": float(roc_auc_score(y, probability)),
        "average_precision": float(average_precision_score(y, probability)),
        "negative_false_positive_rate": float(prediction[negative].mean()),
        "brier": float(brier_score_loss(y, probability)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping-dir", type=Path, required=True)
    parser.add_argument("--mg2act-train", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report_path = args.mapping_dir / "mapping_report.json"
    mapping_report = json.loads(report_path.read_text(encoding="utf-8"))
    if not mapping_report.get("training_gate_passed"):
        raise ValueError("negative mapping quality gate did not pass")
    negative_path = args.mapping_dir / "primary_negative_units.json"
    positive_path = args.mapping_dir / "positive_pool.json"
    negatives = json.loads(negative_path.read_text(encoding="utf-8"))
    positives = json.loads(positive_path.read_text(encoding="utf-8"))
    structured = build_structured_negatives(args.mg2act_train, args.provenance)
    if len(structured) < 50:
        raise ValueError(f"insufficient structured negatives: {len(structured)}")

    run_rows = []
    prediction_rows = []
    split_audit = []
    for seed in SEEDS:
        split = prepare_split(negatives, positives, structured, seed)
        split_audit.append({
            "seed": seed,
            "test_dois": split["test_dois"],
            "selection_attempt": split["selection_attempt"],
            "n_per_balanced_class": split["n_per_balanced_class"],
            "pool_counts": split["pool_counts"],
            "training_arm_sizes": {name: len(rows) for name, rows in split["arms"].items()},
        })
        y_test = np.asarray([row["label"] for row in split["test"]], dtype=int)
        for arm_name, training_rows in split["arms"].items():
            builder = FeatureBuilder().fit(training_rows)
            x_train = builder.transform(training_rows)
            x_test = builder.transform(split["test"])
            y_train = np.asarray([row["label"] for row in training_rows], dtype=int)
            for model_name in ("logistic_regression", "extra_trees", "mlp"):
                model = build_model(model_name, seed)
                model.fit(x_train, y_train)
                probability = model.predict_proba(x_test)[:, 1]
                measured = classification_metrics(y_test, probability)
                run_rows.append({
                    "seed": seed,
                    "arm": arm_name,
                    "model": model_name,
                    "feature_dimension": int(x_train.shape[1]),
                    **measured,
                })
                for row, score in zip(split["test"], probability):
                    prediction_rows.append({
                        "seed": seed,
                        "arm": arm_name,
                        "model": model_name,
                        "record_id": row["record_id"],
                        "doi": row["doi"],
                        "label": row["label"],
                        "probability": float(score),
                    })

    runs = pd.DataFrame(run_rows)
    metric_columns = [
        "accuracy", "macro_f1", "balanced_accuracy", "auroc",
        "average_precision", "negative_false_positive_rate", "brier",
    ]
    summary_rows = []
    for (arm, model), group in runs.groupby(["arm", "model"], sort=True):
        row: dict[str, Any] = {"arm": arm, "model": model, "runs": len(group)}
        for metric in metric_columns:
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_std"] = float(group[metric].std(ddof=0))
        summary_rows.append(row)
    indexed = {(row["arm"], row["model"]): row for row in summary_rows}
    comparisons = []
    for model in ("logistic_regression", "extra_trees", "mlp"):
        recovered = indexed[("recovered_balanced", model)]
        structured_row = indexed[("structured_balanced", model)]
        positive = indexed[("positive_biased", model)]
        comparisons.append({
            "model": model,
            "recovered_minus_structured": {
                metric: recovered[f"{metric}_mean"] - structured_row[f"{metric}_mean"]
                for metric in metric_columns
            },
            "recovered_minus_positive_biased": {
                metric: recovered[f"{metric}_mean"] - positive[f"{metric}_mean"]
                for metric in metric_columns
            },
        })
    report = {
        "protocol": {
            "seeds": list(SEEDS),
            "primary_negative_units": len(negatives),
            "structured_negative_pool": len(structured),
            "structured_positive_pool": len(positives),
            "test_policy": "balanced DOI-held-out recovered negatives and structured positives",
            "feature_policy": "Morgan fingerprint plus target and E3 identity; conditions retained but excluded",
            "training_arms_equal_size": True,
        },
        "splits": split_audit,
        "summary": summary_rows,
        "comparisons": comparisons,
        "external_generation_requests": 0,
        "synthetic_labels": 0,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(run_rows).to_csv(args.out / "runs.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(args.out / "predictions.csv", index=False)
    write_json(args.out / "report.json", report)
    manifest = {
        "inputs": {
            str(path.resolve()): sha256(path)
            for path in [report_path, negative_path, positive_path, args.mg2act_train, args.provenance]
        },
        "code": {str(Path(__file__).resolve()): sha256(Path(__file__))},
        "outputs": {
            path.name: sha256(path)
            for path in sorted(args.out.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
        "runtime": {"rdkit": rdBase.rdkitVersion, "pandas": pd.__version__},
        "external_generation_requests": 0,
        "synthetic_labels": 0,
    }
    write_json(args.out / "manifest.json", manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

