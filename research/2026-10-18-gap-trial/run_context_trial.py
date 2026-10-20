"""Bounded, source-linked GH1 assay-context comparison; run from any directory."""

from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score, balanced_accuracy_score, brier_score_loss,
    log_loss, roc_auc_score,
)
from sklearn.model_selection import GroupKFold

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ROOT / "research" / "sources" / "gh1-2014"
PILOT = ROOT / "research" / "pilots" / "gh1-nims"
SEEDS = [17, 29, 43, 71, 101]
AA = "ACDEFGHIKLMNPQRSTVWY"
SUBSTRATES = ["xylobiose", "cellobiose", "lactose"]
ARMS = ["no_context", "true_context", "shuffled_train_context", "context_substrate_only"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(HERE / name, index=False, encoding="utf-8-sig")


def read_sequences() -> dict[str, str]:
    sequences, accession, pieces = {}, None, []
    for line in (PILOT / "gh1_nims_core96_ncbi_sequences.fasta").read_text().splitlines():
        if line.startswith(">"):
            if accession:
                sequences[accession] = "".join(pieces)
            accession, pieces = line[1:].split()[0], []
        else:
            pieces.append(line.strip().upper())
    if accession:
        sequences[accession] = "".join(pieces)
    crosswalk = pd.read_csv(PILOT / "gh1_nims_core96_ncbi_crosswalk.csv").set_index("ncbi_accession")
    for key, sequence in sequences.items():
        row = crosswalk.loc[key]
        assert row["ncbi_version_record"] == key, f"Accession version mismatch: {key}"
        assert hashlib.sha256(sequence.encode()).hexdigest().upper() == row["ncbi_sequence_sha256"]
        assert set(sequence) <= set(AA + "X"), f"Unexpected sequence characters: {key}"
    return sequences


def read_observations(sequences: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    annotation = openpyxl.load_workbook(SOURCES / "cb500244v_si_004.xlsx", read_only=True, data_only=True)
    expressed = {r[0] for r in annotation.active.iter_rows(min_row=7, values_only=True)
                 if r[0] is not None and r[3] == 1}
    annotation.close()
    workbook = openpyxl.load_workbook(SOURCES / "cb500244v_si_003.xlsx", read_only=True, data_only=True)
    rows, protein = [], None
    for position, row in enumerate(workbook.active.iter_rows(min_row=7, values_only=True), 7):
        if row[0] is not None:
            protein = row[0]
        if protein not in expressed or row[1] not in (5, 8) or row[2] not in (40, 60, 80, 90):
            continue
        accession = protein.split("_", 1)[0]
        for column, substrate in enumerate(SUBSTRATES, 3):
            raw = row[column]
            if isinstance(raw, str) and raw.strip() == "<0.1":
                label, interpretation = 0, "explicit_below_background"
            elif isinstance(raw, (int, float)) and raw > 0.1:
                label, interpretation = 1, "numeric_above_background"
            else:
                label, interpretation = None, "boundary_or_unresolved"
            rows.append(dict(protein_id=protein, accession=accession, substrate=substrate,
                             pH=int(row[1]), temperature_C=int(row[2]), raw_value=str(raw),
                             target=label, interpretation=interpretation,
                             source_file="cb500244v_si_003.xlsx", source_sheet=workbook.active.title,
                             source_cell=f"{chr(65 + column)}{position}",
                             source_doi="10.1021/cb500244v.s003",
                             sequence_available=accession in sequences))
    workbook.close()
    frame = pd.DataFrame(rows)
    keys = ["protein_id", "substrate", "pH", "temperature_C"]
    frame["duplicate_key"] = frame.duplicated(keys, keep=False)
    frame["exclusion_reason"] = [
        ";".join(reason for reason, flag in (
            ("duplicate_condition_key", r.duplicate_key),
            ("boundary_or_unresolved", pd.isna(r.target)),
            ("no_version_verified_sequence", not r.sequence_available),
        ) if flag)
        for r in frame.itertuples()
    ]
    usable = frame[frame.exclusion_reason == ""].copy().reset_index(drop=True)
    usable["target"] = usable.target.astype(int)
    usable["observation_id"] = [f"GH1CTX{i:04d}" for i in range(1, len(usable) + 1)]
    usable["sequence_group"] = [hashlib.sha256(sequences[a].encode()).hexdigest() for a in usable.accession]
    assert not usable.duplicated(keys).any()
    return frame, usable


def features(data: pd.DataFrame, sequences: dict[str, str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cache = {}
    for accession in data.accession.unique():
        seq = sequences[accession]
        counts = Counter(seq)
        cache[accession] = [counts[a] / len(seq) for a in AA + "X"] + [len(seq)]
    composition = np.array([cache[a] for a in data.accession])
    substrate = np.array([[int(s == name) for name in SUBSTRATES] for s in data.substrate])
    condition = data[["pH", "temperature_C"]].to_numpy(dtype=float)
    return np.column_stack([composition, substrate]), condition, substrate


def metrics(target: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return dict(brier=brier_score_loss(target, prediction), roc_auc=roc_auc_score(target, prediction),
                average_precision=average_precision_score(target, prediction),
                balanced_accuracy=balanced_accuracy_score(target, prediction >= 0.5),
                log_loss=log_loss(target, prediction, labels=[0, 1]))


def main() -> None:
    sequences = read_sequences()
    all_rows, data = read_observations(sequences)
    save_csv(all_rows, "source_cell_audit.csv")
    save_csv(data, "model_observations.csv")
    base, context, substrate = features(data, sequences)
    target, groups = data.target.to_numpy(), data.sequence_group.to_numpy()
    pair = data.groupby(["protein_id", "substrate"]).target.agg(["size", "sum"])
    pair["below_background"] = pair["size"] - pair["sum"]
    pair["mixed_across_conditions"] = (pair["sum"] > 0) & (pair.below_background > 0)
    pair["minimum_conflicting_rows_if_single_pair_label"] = np.minimum(pair["sum"], pair.below_background)
    save_csv(pair.reset_index(), "pair_condition_audit.csv")
    score_rows, prediction_rows, split_rows = [], [], []
    for seed in SEEDS:
        predictions = {arm: np.full(len(data), np.nan) for arm in ARMS}
        folds = np.full(len(data), -1)
        splitter = GroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for fold, (train, test) in enumerate(splitter.split(base, target, groups)):
            assert not set(groups[train]) & set(groups[test])
            assert len(np.unique(target[train])) == len(np.unique(target[test])) == 2
            folds[test] = fold
            rng = np.random.default_rng(seed * 10 + fold)
            shuffled = context[train][rng.permutation(len(train))]
            inputs = {
                "no_context": (base[train], base[test]),
                "true_context": (np.column_stack([base[train], context[train]]), np.column_stack([base[test], context[test]])),
                "shuffled_train_context": (np.column_stack([base[train], shuffled]), np.column_stack([base[test], context[test]])),
                "context_substrate_only": (np.column_stack([substrate[train], context[train]]), np.column_stack([substrate[test], context[test]])),
            }
            for arm, (train_x, test_x) in inputs.items():
                model = RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5,
                                               max_features=1.0, random_state=seed * 10 + fold, n_jobs=2)
                model.fit(train_x, target[train])
                predictions[arm][test] = model.predict_proba(test_x)[:, 1]
            split_rows.append(dict(seed=seed, fold=fold, train_rows=len(train), test_rows=len(test),
                                   train_sequence_groups=len(set(groups[train])),
                                   test_sequence_groups=len(set(groups[test])), group_overlap=0))
        for arm in ARMS:
            assert np.isfinite(predictions[arm]).all()
            score_rows.append(dict(seed=seed, arm=arm, **metrics(target, predictions[arm])))
        for i, row in data.iterrows():
            prediction_rows.append(dict(observation_id=row.observation_id, protein_id=row.protein_id,
                                        seed=seed, fold=int(folds[i]), target=int(target[i]),
                                        **{arm: float(predictions[arm][i]) for arm in ARMS}))
        print(f"Completed seed {seed}: " + "; ".join(f"{r['arm']} Brier={r['brier']:.6f}"
              for r in score_rows if r["seed"] == seed), flush=True)
    scores = pd.DataFrame(score_rows)
    save_csv(scores, "metrics_by_seed.csv")
    save_csv(pd.DataFrame(prediction_rows), "out_of_fold_predictions.csv")
    save_csv(pd.DataFrame(split_rows), "split_checks.csv")
    summary = scores.groupby("arm", sort=False)[list(metrics(target, np.full(len(data), target.mean())))].agg(["mean", "min", "max"])
    summary.columns = ["_".join(c) for c in summary.columns]
    save_csv(summary.reset_index(), "metrics_summary.csv")
    baseline = scores[scores.arm == "no_context"].set_index("seed")
    real = scores[scores.arm == "true_context"].set_index("seed")
    delta = real.select_dtypes(include="number") - baseline.select_dtypes(include="number")
    save_csv(delta.reset_index(), "paired_real_minus_no_context.csv")
    inputs = [SOURCES / "cb500244v_si_003.xlsx", SOURCES / "cb500244v_si_004.xlsx",
              PILOT / "gh1_nims_core96_ncbi_sequences.fasta", PILOT / "gh1_nims_core96_ncbi_crosswalk.csv",
              HERE / "实验事先约定.md", Path(__file__)]
    manifest = dict(source_article="https://doi.org/10.1021/cb500244v", seeds=SEEDS,
                    source_core_rows=len(all_rows), source_core_proteins=int(all_rows.protein_id.nunique()),
                    source_rows_without_sequence=int((~all_rows.sequence_available).sum()),
                    duplicate_source_cells=int(all_rows.duplicate_key.sum()),
                    boundary_or_unresolved_source_cells=int(all_rows.target.isna().sum()),
                    model_rows=len(data), model_proteins=int(data.protein_id.nunique()),
                    exact_sequence_groups=int(data.sequence_group.nunique()),
                    model_below_background=int((target == 0).sum()), model_above_background=int(target.sum()),
                    model_pairs=len(pair), mixed_pairs=int(pair.mixed_across_conditions.sum()),
                    minimum_conflicting_rows_if_single_pair_label=int(pair.minimum_conflicting_rows_if_single_pair_label.sum()),
                    versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                                  sklearn=sklearn.__version__, openpyxl=openpyxl.__version__),
                    parameters=dict(n_estimators=200, max_depth=8, min_samples_leaf=5, max_features=1.0,
                                    folds=5, threads=2, hyperparameter_search=False),
                    inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs})
    (HERE / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), constrained_layout=True)
    labels = ["No context", "True context", "Shuffled train\ncontext", "Context +\nsubstrate only"]
    for axis, metric, title in zip(axes, ["brier", "roc_auc"], ["Brier error (lower is better)", "ROC-AUC (higher is better)"]):
        for seed in SEEDS:
            values = scores[scores.seed == seed].set_index("arm").loc[ARMS, metric]
            axis.plot(range(4), values, "o-", alpha=0.5, linewidth=1)
        axis.set_xticks(range(4), labels, fontsize=8)
        axis.set_title(title)
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle("GH1 source-table trial: five repeated protein-group splits")
    fig.savefig(HERE / "context_comparison.png", dpi=180)
    plt.close(fig)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(summary.to_string())


if __name__ == "__main__":
    main()
