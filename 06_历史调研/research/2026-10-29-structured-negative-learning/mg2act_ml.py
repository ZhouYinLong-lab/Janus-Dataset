"""Conventional MG2Act regression baselines on the official frozen split.

The feature builder is fitted on the 907-row training split. Hyperparameters
are selected only by the 125-row validation split. The 127-row test labels are
opened only after the selected configurations are fixed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import rdFingerprintGenerator
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


SEEDS = (20261029, 20261030, 20261031)
AA = "ACDEFGHIKLMNPQRSTVWY"
EXPECTED_COUNTS = {"train": 907, "val": 125, "test": 127}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def seq_features(sequence: str) -> np.ndarray:
    sequence = str(sequence or "").upper()
    length = max(len(sequence), 1)
    composition = [sequence.count(aa) / length for aa in AA]
    return np.asarray(composition + [math.log1p(len(sequence))], dtype=np.float32)


class FeatureBuilder:
    """Fit train-only categorical vocabulary and build deterministic features."""

    def __init__(self, fp_size: int = 1024) -> None:
        self.fp_size = fp_size
        self.fp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=fp_size)
        self.categories = OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32)
        self.invalid_smiles: list[str] = []

    @staticmethod
    def _categorical(df: pd.DataFrame) -> np.ndarray:
        return df[["PrimaryTarget", "RecruitingProtein"]].fillna("unknown").astype(str).to_numpy()

    def fit(self, train: pd.DataFrame) -> "FeatureBuilder":
        self.categories.fit(self._categorical(train))
        return self

    def _morgan(self, smiles: str) -> np.ndarray:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            self.invalid_smiles.append(str(smiles))
            return np.zeros(self.fp_size, dtype=np.float32)
        bitvect = self.fp.GetFingerprint(mol)
        array = np.zeros(self.fp_size, dtype=np.int8)
        DataStructs.ConvertToNumpyArray(bitvect, array)
        return array.astype(np.float32)

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        mol = np.vstack([self._morgan(value) for value in df["Molecule_SMILES"]])
        target = np.vstack([seq_features(value) for value in df["Target_seq"]])
        e3 = np.vstack([seq_features(value) for value in df["E3_seq"]])
        categorical = self.categories.transform(self._categorical(df))
        return np.hstack([mol, target, e3, categorical]).astype(np.float32)


def metrics(y: np.ndarray, prediction: np.ndarray, target: pd.Series) -> dict[str, float]:
    pred = np.clip(np.asarray(prediction, dtype=float), 0.0, 1.0)
    frame = pd.DataFrame({"y": y, "prediction": pred, "target": target.astype(str).to_numpy()})
    target_mae = frame.groupby("target", sort=True).apply(
        lambda group: mean_absolute_error(group["y"], group["prediction"]),
        include_groups=False,
    )
    return {
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(mean_squared_error(y, pred) ** 0.5),
        "r2": float(r2_score(y, pred)),
        "target_macro_mae": float(target_mae.mean()),
    }


def build_model(name: str, params: dict[str, Any], seed: int):
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=float(params["alpha"])))
    if name == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=300,
            max_features=params["max_features"],
            min_samples_leaf=int(params["min_samples_leaf"]),
            random_state=seed,
            n_jobs=-1,
        )
    if name == "mlp":
        hidden = tuple(int(value) for value in params["hidden_layer_sizes"])
        regressor = MLPRegressor(
            hidden_layer_sizes=hidden,
            alpha=float(params["alpha"]),
            learning_rate_init=1e-3,
            max_iter=350,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=25,
            random_state=seed,
        )
        return make_pipeline(StandardScaler(), regressor)
    raise ValueError(f"unknown model: {name}")


def grids() -> dict[str, list[dict[str, Any]]]:
    return {
        "ridge": [{"alpha": alpha} for alpha in (0.1, 1.0, 10.0, 100.0)],
        "extra_trees": [
            {"max_features": max_features, "min_samples_leaf": leaf}
            for max_features in ("sqrt", 0.25)
            for leaf in (1, 3)
        ],
        "mlp": [
            {"hidden_layer_sizes": hidden, "alpha": alpha}
            for hidden in ((64,), (128, 32))
            for alpha in (1e-4, 1e-3)
        ],
    }


def select_on_validation(
    model_name: str,
    candidates: list[dict[str, Any]],
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit: list[dict[str, Any]] = []
    model_seeds = (SEEDS[0],) if model_name == "ridge" else SEEDS
    for params in candidates:
        seed_scores = []
        for seed in model_seeds:
            model = build_model(model_name, params, seed)
            model.fit(x_train, y_train)
            prediction = np.clip(model.predict(x_val), 0.0, 1.0)
            seed_scores.append(float(mean_absolute_error(y_val, prediction)))
        audit.append(
            {
                "params": params,
                "validation_mae_by_seed": seed_scores,
                "validation_mae_mean": float(np.mean(seed_scores)),
            }
        )
    audit.sort(key=lambda row: (row["validation_mae_mean"], json.dumps(row["params"], sort_keys=True)))
    return audit[0]["params"], audit


def read_fine_ids(path: Path) -> set[str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["id"]) for row in rows if row.get("fine_test")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--fine-labels", type=Path, required=True)
    parser.add_argument("--llm-summary", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paths = {split: args.data_dir / f"{split}.csv" for split in EXPECTED_COUNTS}
    for path in [*paths.values(), args.fine_labels]:
        if not path.exists():
            raise FileNotFoundError(path)

    frames = {split: pd.read_csv(path) for split, path in paths.items()}
    actual_counts = {split: len(frame) for split, frame in frames.items()}
    if actual_counts != EXPECTED_COUNTS:
        raise ValueError(f"official split identity changed: {actual_counts}")
    required = {
        "id", "Molecule_SMILES", "PrimaryTarget", "Target_seq",
        "RecruitingProtein", "E3_seq", "Score",
    }
    for split, frame in frames.items():
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{split} missing columns: {missing}")

    builder = FeatureBuilder().fit(frames["train"])
    x_train = builder.transform(frames["train"])
    x_val = builder.transform(frames["val"])
    x_test = builder.transform(frames["test"])
    if builder.invalid_smiles:
        raise ValueError(f"invalid SMILES found: {len(builder.invalid_smiles)}")
    y_train = frames["train"]["Score"].to_numpy(dtype=float)
    y_val = frames["val"]["Score"].to_numpy(dtype=float)

    # Test labels are deliberately read only after feature fitting and all model
    # selection inputs are fixed to train/validation arrays.
    y_test = frames["test"]["Score"].to_numpy(dtype=float)
    fine_ids = read_fine_ids(args.fine_labels)
    fine_mask = frames["test"]["id"].astype(str).isin(fine_ids).to_numpy()
    if int(fine_mask.sum()) != 73:
        raise ValueError(f"fine-test identity changed: {int(fine_mask.sum())}")

    prediction_rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "protocol": {
            "split_counts": actual_counts,
            "fine_test_count": int(fine_mask.sum()),
            "feature_dimension": int(x_train.shape[1]),
            "morgan_radius": 2,
            "morgan_bits": builder.fp_size,
            "seeds": list(SEEDS),
            "selection": "minimum mean validation MAE; test labels excluded",
        },
        "baselines": {},
        "models": {},
    }

    for baseline_name, value in {
        "train_mean": float(y_train.mean()),
        "train_median": float(np.median(y_train)),
    }.items():
        pred = np.full(len(y_test), value, dtype=float)
        report["baselines"][baseline_name] = {
            "constant": value,
            "test": metrics(y_test, pred, frames["test"]["PrimaryTarget"]),
            "fine_test": metrics(
                y_test[fine_mask], pred[fine_mask], frames["test"].loc[fine_mask, "PrimaryTarget"]
            ),
        }
        for row_id, score, estimate in zip(frames["test"]["id"], y_test, pred):
            prediction_rows.append(
                {"model": baseline_name, "seed": "", "id": row_id, "label": score, "prediction": estimate}
            )

    for model_name, candidates in grids().items():
        selected, selection_audit = select_on_validation(
            model_name, candidates, x_train, y_train, x_val, y_val
        )
        model_seeds = (SEEDS[0],) if model_name == "ridge" else SEEDS
        runs = []
        for seed in model_seeds:
            model = build_model(model_name, selected, seed)
            model.fit(x_train, y_train)
            prediction = np.clip(model.predict(x_test), 0.0, 1.0)
            run = {
                "seed": seed,
                "test": metrics(y_test, prediction, frames["test"]["PrimaryTarget"]),
                "fine_test": metrics(
                    y_test[fine_mask], prediction[fine_mask], frames["test"].loc[fine_mask, "PrimaryTarget"]
                ),
            }
            runs.append(run)
            for row_id, score, estimate in zip(frames["test"]["id"], y_test, prediction):
                prediction_rows.append(
                    {"model": model_name, "seed": seed, "id": row_id, "label": score, "prediction": estimate}
                )
        report["models"][model_name] = {
            "selected_params": selected,
            "validation_selection": selection_audit,
            "runs": runs,
            "test_mean": {
                key: float(np.mean([run["test"][key] for run in runs]))
                for key in runs[0]["test"]
            },
            "test_std": {
                key: float(np.std([run["test"][key] for run in runs], ddof=0))
                for key in runs[0]["test"]
            },
            "fine_test_mean": {
                key: float(np.mean([run["fine_test"][key] for run in runs]))
                for key in runs[0]["fine_test"]
            },
        }

    if args.llm_summary and args.llm_summary.exists():
        old = json.loads(args.llm_summary.read_text(encoding="utf-8"))
        report["prior_training_free_llm"] = {
            "full_test": old["model_metrics"]["full_test"],
            "fine_test": old["model_metrics"]["fine_test"],
            "prediction_behavior": "constant_prediction",
            "constant": 0.666666667,
            "source_sha256": sha256(args.llm_summary),
        }

    args.out.mkdir(parents=True, exist_ok=True)
    predictions_path = args.out / "predictions.csv"
    pd.DataFrame(prediction_rows).to_csv(predictions_path, index=False)
    report_path = args.out / "report.json"
    write_json(report_path, report)
    manifest = {
        "inputs": {str(path.resolve()): sha256(path) for path in [*paths.values(), args.fine_labels]},
        "code": {str(Path(__file__).resolve()): sha256(Path(__file__))},
        "runtime": {
            "rdkit": rdBase.rdkitVersion,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "outputs": {
            "report.json": sha256(report_path),
            "predictions.csv": sha256(predictions_path),
        },
        "external_generation_requests": 0,
    }
    write_json(args.out / "manifest.json", manifest)
    print(json.dumps({
        "out": str(args.out),
        "test_mae": {
            "train_mean": report["baselines"]["train_mean"]["test"]["mae"],
            **{name: row["test_mean"]["mae"] for name, row in report["models"].items()},
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

