# Countercheck: exact pair keys in Theisen et al.'s released measured-data splits

**Date:** 2026-09-30  
**Author data/code:** [Harmonic-Discovery/activity-integration](https://github.com/Harmonic-Discovery/activity-integration), inspected at commit `c185bedde8a7081045bc8414906a5775f4271a1c`.  
**Reproducible audit:** [`audit_split_pair_integrity.py`](pilots/kinase-activity-integration/audit_split_pair_integrity.py); outputs [`theisen_measured_split_integrity_summary.csv`](pilots/kinase-activity-integration/theisen_measured_split_integrity_summary.csv) and [`theisen_measured_duplicate_pairs.csv`](pilots/kinase-activity-integration/theisen_measured_duplicate_pairs.csv).

## Why this countercheck was run

An initial PowerShell `Group-Object` analysis reported 426 repeated compound–target keys and apparent train/test overlaps. That command used PowerShell's default case-insensitive string grouping. In SMILES, letter case is chemically meaningful: for example, aromatic `c3ccccc3` is not the same as aliphatic `C3CCCCC3`. The initial grouping therefore merged distinct molecules and its overlap counts were false positives.

## Exact-key result

The corrected audit reads the CSV with Python's standard `csv` module and uses exact, case-sensitive `(canonical_smiles, uniprot_id)` tuple keys. Among 141,193 measured rows it finds 141,193 unique exact pair keys and no duplicate exact keys. Exact train/test overlap is zero in each released split:

| Split | Measured train pairs | Measured test pairs | Exact pair keys in both |
|---|---:|---:|---:|
| Compound–kinase (`ck`) | 120,015 | 21,178 | 0 |
| Ligand | 120,129 | 21,064 | 0 |
| Cluster | 114,408 | 26,785 | 0 |

This is consistent with the paper's stated split design: `ck` holds out compound–kinase pairs, ligand split holds out compounds, and cluster split holds out compound clusters. It **does not** establish absence of every possible chemical-equivalence or target-alias issue; it tests exact standardized SMILES strings and exact UniProt accessions in the released CSV only.

## Corrected interpretation

There is no exact-key split leakage signal in this audit. The earlier 426/101/96/41 figures should not be cited as properties of the dataset; they resulted from case-insensitive key grouping and have been withdrawn. This countercheck is a data-integrity sanity check, not evidence about negative labels, literature recovery, or model utility.

