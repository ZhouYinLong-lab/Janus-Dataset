"""Small, CPU-only sanity check for the positive-unlabeled setting.

This is not a reimplementation of Song et al.'s PUlasso algorithm. It tests
the narrower logic behind the paper: if observed unlabeled examples are
mistakenly treated as negatives, probability estimates become biased; a
positive-unlabeled correction can improve calibration when its assumptions
hold.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))


def one_run(seed: int, n: int = 6000, d: int = 24, label_rate: float = 0.35) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, d))
    weights = np.zeros(d)
    weights[[0, 2, 5, 9, 14]] = [1.4, -1.1, 0.9, 0.8, -0.7]
    true_probability = sigmoid(x @ weights - 0.35)
    y = rng.binomial(1, true_probability)

    # Only a random subset of true positives is observed as labeled positive.
    # All remaining examples are observed as unlabeled, including hidden positives.
    observed_positive = (y == 1) & (rng.random(n) < label_rate)
    z = observed_positive.astype(int)

    x_train, x_test, z_train, z_test, y_train, y_test = train_test_split(
        x, z, y, test_size=0.35, random_state=seed, stratify=z
    )

    model = LogisticRegression(max_iter=1000, solver="lbfgs", random_state=seed)
    model.fit(x_train, z_train)
    p_z = model.predict_proba(x_test)[:, 1]

    # Elkan-Noto-style correction: estimate P(Z=1 | Y=1) from known positives.
    positive_train_scores = model.predict_proba(x_train[z_train == 1])[:, 1]
    c_hat = float(np.mean(positive_train_scores))
    p_pu_raw = p_z / max(c_hat, 1e-6)
    p_pu = np.clip(p_pu_raw, 0.0, 1.0)

    return {
        "seed": seed,
        "true_prevalence": float(np.mean(y_test)),
        "observed_positive_rate": float(np.mean(z_train)),
        "c_hat": c_hat,
        "naive_auc": roc_auc_score(y_test, p_z),
        # Ranking is invariant to dividing by a positive constant; use the
        # unclipped score here to avoid artificial ties at probability 1.
        "pu_auc": roc_auc_score(y_test, p_pu_raw),
        "naive_ap": average_precision_score(y_test, p_z),
        "pu_ap": average_precision_score(y_test, p_pu_raw),
        "naive_brier": brier_score_loss(y_test, p_z),
        "pu_brier": brier_score_loss(y_test, p_pu),
        "naive_logloss": log_loss(y_test, np.clip(p_z, 1e-6, 1 - 1e-6)),
        "pu_logloss": log_loss(y_test, np.clip(p_pu, 1e-6, 1 - 1e-6)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="reproduction/results/synthetic_pu")
    parser.add_argument("--seeds", type=int, default=20)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [one_run(seed) for seed in range(20260921, 20260921 + args.seeds)]
    result = pd.DataFrame(rows)
    result.to_csv(out_dir / "per_seed_metrics.csv", index=False)

    metrics = [
        "naive_auc", "pu_auc", "naive_ap", "pu_ap",
        "naive_brier", "pu_brier", "naive_logloss", "pu_logloss",
    ]
    summary = pd.DataFrame({"metric": metrics})
    summary["mean"] = [result[m].mean() for m in metrics]
    summary["sd"] = [result[m].std(ddof=1) for m in metrics]
    summary.to_csv(out_dir / "summary_metrics.csv", index=False)

    payload = {
        "n_runs": args.seeds,
        "interpretation": (
            "The correction is evaluated against latent true labels in a synthetic "
            "random-positive-selection setting; it is a sanity check, not a full "
            "reproduction of the paper's PUlasso algorithm."
        ),
        "mean_metrics": {m: float(result[m].mean()) for m in metrics},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
