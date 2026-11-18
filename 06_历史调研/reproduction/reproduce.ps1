param(
    [switch]$InstallRPackages,
    [int]$SyntheticSeeds = 20
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command Rscript -ErrorAction SilentlyContinue)) {
    throw 'Rscript not found. Install R before running the author reproduction.'
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python not found. Install Python before running the synthetic sanity check.'
}

if ($InstallRPackages) {
    Rscript -e "options(repos=c(CRAN='https://cloud.r-project.org')); install.packages(c('PUlasso','PRROC','ggplot2','pbapply','data.table','doParallel','magrittr','foreach','R.utils'), type='binary')"
    Rscript -e "install.packages('reproduction/pudms-upstream', repos=NULL, type='source')"
}

New-Item -ItemType Directory -Force 'reproduction/results/author_example' | Out-Null
New-Item -ItemType Directory -Force 'reproduction/results/synthetic_pu' | Out-Null

Rscript 'reproduction/run_author_example.R' 'reproduction/results/author_example'
python 'reproduction/run_pu_synthetic.py' --out-dir 'reproduction/results/synthetic_pu' --seeds $SyntheticSeeds

Write-Host 'Reproduction runs completed.'
