param(
    [string]$Datasets = 'PyKS,SUMO1,TPK1,UBE2I,GB1,Bgl3_LT',
    [int]$Folds = 3,
    [int]$Hyperparameters = 5,
    [int]$Cores = 2
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Force 'reproduction/results/multidataset' | Out-Null
Rscript 'reproduction/run_multidataset.R' $Datasets 'reproduction/results/multidataset' $Folds $Hyperparameters $Cores
