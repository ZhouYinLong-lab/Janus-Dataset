"""Data loading and featurization for CensorADMET experiments.

Two granularities are supported, matching the two questions in the plan:

  * measurement-level (data/measurement_records.parquet): one row per
    ChEMBL activity, each carrying a SINGLE assay_chembl_id / document_chembl_id
    / source_name / document_year. This is what the assay-aware model (plan §4)
    and the new assay/document/threshold/source-held-out splits (§9) require.

Morgan fingerprints are generated deterministically with RDKit and cached per
unique standardized SMILES.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from paths import CACHE_DIR, DATA_DIR, MEASUREMENT_PARQUET

ENDPOINT_DIR = DATA_DIR / "endpoints"


# --------------------------------------------------------------------------- #
# Molecular featurization                                                       #
# --------------------------------------------------------------------------- #
def _morgan_features(smiles: list[str], radius: int, n_bits: int) -> np.ndarray:
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator

    generator = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    out = np.zeros((len(smiles), n_bits), dtype=np.float32)
    for row, smi in enumerate(smiles):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            raise ValueError(f"RDKit could not parse standardized SMILES: {smi}")
        out[row, list(generator.GetFingerprint(mol).GetOnBits())] = 1.0
    return out


def _descriptors_no_leak(smiles: list[str], fill: float = 0.0) -> np.ndarray:
    """RDKit descriptors with LEAKAGE-FREE imputation: any non-finite descriptor
    is replaced by a fixed constant (default 0.0), a per-molecule transform with
    no dataset-level fitted statistic. (The Stage-6 featurizer uses a batch
    median, which would leak across a train/test split when features are computed
    on the whole dataset up front.)"""
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    descs = Descriptors.descList
    arr = np.zeros((len(smiles), len(descs)), dtype=np.float32)
    for i, smi in enumerate(smiles):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            raise SystemExit(f"RDKit could not parse SMILES: {smi}")
        for j, (_, fn) in enumerate(descs):
            try:
                v = float(fn(mol))
            except Exception:
                v = np.nan
            arr[i, j] = v if np.isfinite(v) else fill
    arr[~np.isfinite(arr)] = fill
    return arr


def featurize_smiles(smiles: list[str], feature_set: str = "morgan",
                     radius: int = 2, n_bits: int = 2048,
                     cache_dir: Path = CACHE_DIR) -> np.ndarray:
    """Featurize with deterministic RDKit features, caching by unique SMILES.

    feature_set in {"morgan", "rdkit_descriptors", "morgan_plus_rdkit"}.
    Returns (len(smiles), d) float32 array (rows aligned to the input order).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    uniq = pd.unique(pd.Series(smiles))
    key = hashlib.sha256(("|".join(map(str, uniq)) + f"|{feature_set}|{radius}|{n_bits}").encode()).hexdigest()[:16]
    cache_path = cache_dir / f"feat_{feature_set}_{radius}_{n_bits}_{key}.npz"
    # A cached file may be partially written by a concurrent worker (np.savez is
    # NOT atomic). Try to load; on any failure, fall through and recompute. Cache
    # writes below are atomic (unique tmp + os.replace) so this race self-heals.
    loaded_ok = False
    if cache_path.exists():
        try:
            loaded = np.load(cache_path, allow_pickle=True)
            # materialise arrays ONCE: NpzFile is lazy, so indexing loaded["X"][i]
            # inside a loop re-decompresses the whole array every iteration.
            X_cached = loaded["X"]
            smiles_cached = loaded["smiles"]
            feat_map = {s: X_cached[i] for i, s in enumerate(smiles_cached)}
            loaded_ok = True
        except Exception:
            loaded_ok = False
    if not loaded_ok:
        morgan = _morgan_features(list(uniq), radius, n_bits)
        if feature_set == "morgan":
            X_uniq = morgan
        else:
            # NOTE: we do NOT call s6.rdkit_descriptor_features here because it
            # imputes NaN descriptors with the BATCH median, which -- given we
            # featurize the whole dataset before splitting -- would leak test-row
            # statistics into train features. _descriptors_no_leak imputes NaN
            # with a fixed constant (0.0), a per-molecule deterministic transform
            # with no fitted statistic, so caching over the whole dataset is safe.
            desc = _descriptors_no_leak(list(uniq))
            if feature_set == "rdkit_descriptors":
                X_uniq = desc
            elif feature_set == "morgan_plus_rdkit":
                X_uniq = np.concatenate([morgan, desc], axis=1)
            else:
                raise ValueError(f"unknown feature_set {feature_set}")
        X_uniq = X_uniq.astype(np.float32)
        # atomic write: unique tmp file then os.replace, so concurrent readers
        # never observe a half-written .npz (the cause of "EOFError: No data left
        # in file" under the parallel matrix orchestrator).
        import os
        tmp = cache_path.with_suffix(f".{os.getpid()}.tmp.npz")
        try:
            np.savez_compressed(tmp, X=X_uniq, smiles=np.array(list(uniq), dtype=object))
            os.replace(tmp, cache_path)
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        feat_map = {s: X_uniq[i] for i, s in enumerate(uniq)}
    return np.stack([feat_map[s] for s in smiles]).astype(np.float32)


# --------------------------------------------------------------------------- #
# Dataset container                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class CensoredDataset:
    endpoint_id: str
    X: np.ndarray                    # (n, d) features
    lower: np.ndarray                # (n,) p-scale lower bound (-inf allowed)
    upper: np.ndarray                # (n,) p-scale upper bound (+inf allowed)
    exact_mask: np.ndarray           # (n,) bool
    censoring_class: np.ndarray      # (n,) str
    meta: pd.DataFrame               # (n, ...) grouping columns (assay/doc/source/scaffold/year)
    feature_set: str
    granularity: str                 # "endpoint" | "measurement"
    assay_vocab: dict = field(default_factory=dict)   # assay id -> contiguous idx (0 reserved)

    @property
    def n(self):
        return self.X.shape[0]

    def assay_idx(self, key_col: str = "assay_chembl_id") -> np.ndarray:
        """Contiguous assay indices (0 = unknown/held-out) using the fitted vocab."""
        return np.array([self.assay_vocab.get(a, 0) for a in self.meta[key_col]], dtype=np.int64)


# --------------------------------------------------------------------------- #
# Interval sanitation (shared)                                                #
# --------------------------------------------------------------------------- #
def _sanitize_bounds(lower, upper, cls):
    """Return (lower, upper, exact_mask) with proper +/-inf and exact detection,
    guarding against the historical bug of exact rows carrying a bound tiny-offset."""
    lower = np.asarray(lower, dtype=np.float64).copy()
    upper = np.asarray(upper, dtype=np.float64).copy()
    cls = np.asarray(cls)
    # left-censored: value known to be below upper => lower = -inf
    left = cls == "left_censored_p"
    right = cls == "right_censored_p"
    exact = cls == "exact"
    interval = cls == "interval_censored_p"
    lower[left] = -np.inf
    upper[right] = np.inf
    exact_mask = exact & np.isfinite(lower) & np.isfinite(upper) & np.isclose(lower, upper)
    # for exact rows force lower==upper exactly
    lower[exact_mask] = upper[exact_mask]
    return lower.astype(np.float32), upper.astype(np.float32), exact_mask


# --------------------------------------------------------------------------- #
# Endpoint-level loader                                                        #
# --------------------------------------------------------------------------- #
def load_endpoint(endpoint_id: str, feature_set: str = "morgan",
                  n_bits: int = 2048, radius: int = 2) -> CensoredDataset:
    df = pd.read_parquet(ENDPOINT_DIR / f"{endpoint_id}.parquet").reset_index(drop=True)
    X = featurize_smiles(df["standardized_smiles"].tolist(), feature_set, radius, n_bits)
    lower, upper, exact_mask = _sanitize_bounds(
        df["lower_bound_p"].to_numpy(), df["upper_bound_p"].to_numpy(),
        df["censoring_class"].to_numpy(),
    )
    meta = df[[
        "row_id", "split_group_scaffold", "split_group_connectivity_inchikey",
        "split_group_year", "assay_chembl_ids", "document_chembl_ids",
        "n_assays", "n_documents", "standardized_smiles", "value_p",
    ]].copy()
    # primary assay = first listed (endpoint rows may aggregate several)
    meta["assay_chembl_id"] = meta["assay_chembl_ids"].astype(str).str.split(";|,").str[0].str.strip()
    meta["document_chembl_id"] = meta["document_chembl_ids"].astype(str).str.split(";|,").str[0].str.strip()
    return CensoredDataset(endpoint_id, X, lower, upper, exact_mask,
                           df["censoring_class"].to_numpy(), meta, feature_set, "endpoint")


# --------------------------------------------------------------------------- #
# Measurement-level loader (for assay-aware + new splits)                       #
# --------------------------------------------------------------------------- #
_MEAS_CACHE = None


def _load_measurements():
    global _MEAS_CACHE
    if _MEAS_CACHE is None:
        _MEAS_CACHE = pd.read_parquet(MEASUREMENT_PARQUET)
    return _MEAS_CACHE


def load_measurement_endpoint(target_key: str, standard_type: str,
                              assay_type: str | None = None,
                              feature_set: str = "morgan",
                              n_bits: int = 2048, radius: int = 2,
                              require_clean: bool = True) -> CensoredDataset:
    """Measurement-level endpoint: one row per activity, single assay/doc/source.

    Filters clean_candidate_records to (target_key, standard_type[, assay_type]).
    Uses canonical_smiles (RDKit-parseable) for featurization.
    """
    df = _load_measurements()
    m = (df["target_key"] == target_key) & (df["standard_type"] == standard_type)
    if assay_type is not None:
        m &= (df["assay_type"] == assay_type)
    if require_clean and "core_clean" in df.columns:
        m &= df["core_clean"].astype(bool)
    sub = df[m].copy().reset_index(drop=True)
    # require a usable SMILES and a defined p-interval
    smi_col = "parent_canonical_smiles" if "parent_canonical_smiles" in sub.columns else "canonical_smiles"
    sub = sub[sub[smi_col].notna()].reset_index(drop=True)
    sub = sub[sub["censoring_class"].isin(
        ["exact", "left_censored_p", "right_censored_p", "interval_censored_p"])].reset_index(drop=True)

    eid = f"{target_key}_{standard_type}" + (f"_{assay_type}" if assay_type else "")
    X = featurize_smiles(sub[smi_col].tolist(), feature_set, radius, n_bits)
    lower, upper, exact_mask = _sanitize_bounds(
        sub["lower_bound_p"].to_numpy(), sub["upper_bound_p"].to_numpy(),
        sub["censoring_class"].to_numpy(),
    )
    meta = sub[[
        "activity_id", "assay_chembl_id", "document_chembl_id", "source_name",
        "document_year", "confidence_score", "assay_type", "standard_relation",
    ]].copy()
    meta[smi_col] = sub[smi_col]
    meta = meta.rename(columns={smi_col: "standardized_smiles"})
    meta["value_p"] = sub["p_value"].to_numpy()
    return CensoredDataset(eid, X, lower, upper, exact_mask,
                           sub["censoring_class"].to_numpy(), meta, feature_set, "measurement")


ADMET_DIR = DATA_DIR / "admet_endpoints"


def load_admet_endpoint(endpoint_key: str, feature_set: str = "morgan",
                        n_bits: int = 2048, radius: int = 2) -> CensoredDataset:
    """Measurement-level loader for the broadened ADMET endpoints curated by
    curate_admet.py (solubility, clearance, half-life, ...). The parquet already
    carries the per-measurement assay/document/source/year columns and p-scale
    interval bounds, so it plugs directly into the same pipeline as the CYP/hERG
    measurement endpoints."""
    df = pd.read_parquet(ADMET_DIR / f"{endpoint_key}.parquet").reset_index(drop=True)
    df = df[df["standardized_smiles"].notna()].reset_index(drop=True)
    X = featurize_smiles(df["standardized_smiles"].tolist(), feature_set, radius, n_bits)
    lower, upper, exact_mask = _sanitize_bounds(
        df["lower_bound_p"].to_numpy(), df["upper_bound_p"].to_numpy(),
        df["censoring_class"].to_numpy(),
    )
    meta = df[[
        "activity_id", "assay_chembl_id", "document_chembl_id", "source_name",
        "document_year", "confidence_score", "assay_type", "standard_relation",
        "standardized_smiles",
    ]].copy()
    meta["value_p"] = df["value_p"].to_numpy()
    # assay_description if present (for the transfer embedding)
    if "assay_description" in df.columns:
        meta["assay_description"] = df["assay_description"]
    return CensoredDataset(endpoint_key, X, lower, upper, exact_mask,
                           df["censoring_class"].to_numpy(), meta, feature_set, "measurement")


def fit_assay_vocab(ds: CensoredDataset, train_idx: np.ndarray,
                    min_count: int = 1, key_col: str = "assay_chembl_id") -> None:
    """Assign contiguous indices (>=1) to assays seen in the TRAIN split only, so
    test-only assays map to 0 (unknown) and get no random-effect offset (plan §4).
    Mutates ds.assay_vocab in place."""
    vc = ds.meta.iloc[train_idx][key_col].value_counts()
    vocab = {}
    nxt = 1
    for a, c in vc.items():
        if c >= min_count and pd.notna(a) and str(a) not in ("", "nan", "None"):
            vocab[a] = nxt
            nxt += 1
    ds.assay_vocab = vocab
