# Toniato et al. (2025) negative-reaction-learning reproduction: feasibility audit

**Date:** 2026-09-30  
**Purpose:** Determine whether the public implementation can support a bounded reproduction, and keep environment validation separate from reproducing the paper's scientific result.

## What was checked

- Cloned author repository: [rxn4chemistry/negative_learning](https://github.com/rxn4chemistry/negative_learning), commit `3515a02`.
- Read its `pyproject.toml`, README and selected tests. The declared environment pins PyTorch 2.1.2, Lightning 1.9.5, Transformers 4.30.2, RDKit-pypi 2021.9.2, datasets 2.17.1, scikit-learn >=1.4.1, plus RXN utilities. README refers to a `bin/` directory and shell-based data preparation not present in this public checkout.
- Host GPU is RTX 5070 Ti Laptop GPU (12.2 GiB; compute capability 12.0). The existing Conda environment has PyTorch 2.11.0+cu128 and detects the GPU. A project-local `.venv` was built with `--system-site-packages` to reuse that working CUDA stack; the original Conda environment and upstream source files were not edited.

## Results

- A faithful pinned environment is not available as configured: the configured package index did not offer `rdkit-pypi==2021.9.2` or `scikit-learn==1.4.1`; substitutes RDKit 2023.3.1b1 and scikit-learn 1.4.2 were used. PyTorch 2.1.2 is also not the installed runtime; the installed 2.11.0+cu128 is a compatibility substitution.
- The first CUDA wheel download attempt for a Blackwell-compatible standalone PyTorch wheel was interrupted; nothing was installed into the original environment. This does not block using its already installed PyTorch 2.11 CUDA build through the project-local venv.
- Imports succeed for PyTorch/CUDA, Transformers 4.30.2, Lightning 1.9.5, RDKit, RXN utilities and scikit-learn. The upstream test subset covering baseline, data splitting, SMILES helpers, negative generation, overlap, randomization and teacher-forcing behavior passes **17/17 when CUDA is disabled**.
- With CUDA visible, one upstream teacher-forcing test fails because the test constructs CPU tensors while the model puts parameters on `cuda:0` (device mismatch). The test passes on CPU. This is a test/device-assumption issue, not evidence that paper training has been reproduced.
- Full test collection remains blocked in `test_scorers.py`: importing `datasets` reaches the shared Windows `aiohttp` package, which errors while loading the Windows certificate store (`ssl.SSLError: [ASN1: NOT_ENOUGH_DATA]`). This is environment-level and not yet repaired.
- The package's `datasets==2.17.1` and `transformers==4.30.2` pins were installed into the project-local venv; runtime dependencies inherited from the shared CUDA environment remain mixed. Therefore passing CPU unit tests establish basic code-path viability only.

## Relevance and stop/go judgment

This paper already provides direct but task-specific evidence that negative information can help reaction outcome prediction. A local reproduction could audit the reported effect and test controlled comparisons, but it would still concern reaction products, not assay-level molecular bioactivity or recovery from literature. The actual scientific reproduction has **not** started: the paper's full base-model pretraining is missing, the repo's documented data/bootstrap scripts are absent, and the required environment is not exact.

**Decision:** keep this as an adjacent reproduction candidate, not the next mainline experiment. Before any long training, recover the exact paper datasets/configs/checkpoints and establish matched RL-vs-FT runs with identical examples, budgets, seeds and evaluation. If those artifacts cannot be obtained, stop at this feasibility report rather than presenting a reduced synthetic run as replication.

## Local artifacts

- Repository clone: `research/reproductions/negative-learning/` (upstream files unchanged; `.venv` is local/ignored).
- Primary article and reproduction resources are cited in the main evidence audit [`2026-09-30-negative-chemical-data-model-utility-audit.md`](2026-09-30-negative-chemical-data-model-utility-audit.md).

