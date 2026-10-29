# Structured prediction follow-up

This directory contains the teacher-aligned structured prediction follow-up for
the molecular-glue negative-evidence project.  It keeps the extraction pipeline
as the main contribution and evaluates whether conventional task-specific
models can use structured inputs more effectively than the earlier language
model experiments.

The first experiment predicts the official MG2Act continuous score from a
Morgan fingerprint, target and E3 sequence composition, and target/E3 identity.
It uses the published 907/125/127 split and never uses test labels for model
selection.

Run locally with:

```powershell
uv run --no-project --with rdkit --with scikit-learn --with pandas --with scipy `
  python research/2026-10-29-structured-negative-learning/mg2act_ml.py `
  --data-dir research/2026-10-26-mg2act-audit/local/upstream/MG_data `
  --fine-labels research/2026-10-27-evidence-utility/local/mg2act_benchmark_v2_20261028/labels.json `
  --llm-summary research/2026-10-27-evidence-utility/mg2act_local_v1_summary.json `
  --out research/2026-10-29-structured-negative-learning/local/mg2act_ml_v1
```

Runtime outputs stay under `local/`.  The compact checked-in summary contains
the measured results and hashes without model weights or source records.

The concise shared update is maintained in both Markdown and Word. Rebuild and
check it with:

```powershell
python research/2026-10-29-structured-negative-learning/build_shared_update_docx.py
python research/2026-10-29-structured-negative-learning/validate_shared_update.py
```

