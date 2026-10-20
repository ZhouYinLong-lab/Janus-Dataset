GitHub - eva-mitropoulou/censorADMET: Constraint-satisficing regression for censored ADMET prediction. · GitHub
Skip to content
Navigation Menu
Sign in
Appearance settings
Search
/
Sign in
Sign up
Appearance settings
You signed in with another tab or window.
Reload
to refresh your session.
You signed out in another tab or window.
Reload
to refresh your session.
You switched accounts on another tab or window.
Reload
to refresh your session.
Dismiss alert
Repository navigation
censorADMET
Public
Notifications
You must be signed in to change notification settings
Fork
0
(
0
)
Star
0
(
0
)
You must be signed in to star a repository
About
Constraint-satisficing regression for censored ADMET prediction.
Resources
Readme
MIT license
Cite this repository
Activity
Stars
0
stars
Watchers
0
watching
Forks
0
forks
Report repository
main
Branches
Tags
Go to file
Code
Open more actions menu
Latest commit
History
15 Commits
15 Commits
Folders and files
Name
Name
Last commit message
Last commit date
LICENSES
LICENSES
configs
configs
data
data
figures
figures
results
results
scripts
scripts
src/
censoradmet
src/
censoradmet
tests
tests
.gitignore
.gitignore
.zenodo.json
.zenodo.json
ATTRIBUTION.md
ATTRIBUTION.md
CHANGELOG.md
CHANGELOG.md
CITATION.cff
CITATION.cff
LICENSE_CODE
LICENSE_CODE
LICENSE_DATA
LICENSE_DATA
Makefile
Makefile
README.md
README.md
pyproject.toml
pyproject.toml
View all files
Repository files navigation
CensorADMET
CensorADMET is research software for regression with censored ADMET measurements. It preserves inequality labels such as
IC50 > 10 µM
as probability constraints and provides an explicit accuracy-versus-bound-consistency operating budget.
This
v1.0.0-paper
release freezes the code and artifacts used to audit the accompanying manuscript. It excludes the manuscript itself, model checkpoints, raw ChEMBL database dumps, caches, and internal working material.
Repository layout
src/censoradmet/     model, constrained objective, data loaders, splits, metrics
data/                curated ChEMBL 36-derived inputs and fixed split archives
configs/             frozen manuscript experiment configuration
results/             per-run result matrices and aggregated manuscript summaries
scripts/             validation, fixed-split export, and analysis/figure runners
figures/             frozen manuscript figures
tests/               automated unit and leakage-oriented tests
LICENSES/            licence map and third-party attribution information
data/measurement_records.parquet
is the measurement-level cohort.
data/endpoints/
contains the ten aggregated endpoint inputs, and
data/admet_endpoints/
contains the three broadened-property inputs.
data/fixed_splits/
holds compressed train/test index assignments for the frozen five-fold, split-seed-zero design.
Install
Python 3.11+ and RDKit are required for chemistry-dependent work. A conda environment is the most reliable installation route.
conda create -n censoradmet python=3.11 rdkit -c conda-forge
conda activate censoradmet
pip install -e
'
.[test,chemistry]
'
Quick checks and verification
Run the tests and reconstruct representative manuscript values from the frozen artifacts:
make
test
make verify
make validate-splits
scripts/check_method_numbers.py
verifies 74 representative values against the released result files, with a tolerance of 0.01.
make validate-splits
verifies every archived fold has in-range, non-overlapping train/test indices.
scripts/export_fixed_splits.py
regenerates the compact split archives from
configs/manuscript-v1.0.0.json
; it performs no model fitting.
To inspect a small deterministic example without training a model:
PYTHONPATH=src/censoradmet python -
<<
'
PY
'
from data import load_measurement_endpoint
from splits import make_splits
ds = load_measurement_endpoint('hERG', 'IC50')
name, train, test = make_splits(ds, kinds=('scaffold',), k=5, seed=0)['scaffold'][0]
print(ds.endpoint_id, ds.n, name, len(train), len(test))
PY
Reconstructing reported outputs
The checked manuscript summaries and source result matrices are already released:
results/matrix_endpoint/all_results.parquet
— aggregated endpoint cohort.
results/matrix_measurement/all_results.parquet
— measurement-level cohort.
results/matrix_admet/all_results.parquet
— broadened-property cohort.
results/synthesis/
— endpoint-level summaries, paired comparisons, calibration, feasibility, and broadened-property summaries.
figures/
— frozen Figure 1 and Figure 2 image artifacts.
scripts/synthesize_results.py
rebuilds summary files from these existing artifacts. Full retraining uses
scripts/run_matrix.py
and the settings in
configs/manuscript-v1.0.0.json
; it is computationally expensive and is not part of the release validation workflow.
Licence and citation
Original code is
MIT licensed
. Curated ChEMBL 36-derived inputs, fixed splits, and result artifacts are
CC BY-SA 3.0
; retain the ChEMBL attribution in
ATTRIBUTION.md
. See
LICENSES/README.md
for the file-level map.
Please cite the archived software release, DOI:
10.5281/zenodo.21417709
, using
CITATION.cff
. The manuscript/preprint is a separate scholarly object; its DOI will be added after publication. ChEMBL 36 must also be cited (DOI:
10.6019/CHEMBL.database.36
).
About
Constraint-satisficing regression for censored ADMET prediction.
Resources
Readme
MIT license
Cite this repository
Activity
Stars
0
stars
Watchers
0
watching
Forks
0
forks
Report repository
Releases
Packages
Contributors
Languages
Footer
© 2026 GitHub, Inc.
You can’t perform that action at this time.