options(stringsAsFactors = FALSE)

# Reproduce the enrichment-score baseline used in the authors' comparison.
# This is intentionally a separate script from the PU ROC reproduction because
# the paper's baseline uses a fixed py1 and repeated train/test splits.

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(i, default) if (length(args) >= i) args[[i]] else default
protein.name <- get_arg(1, "DXS")
out_dir <- get_arg(2, file.path("reproduction", "results", "enrichment"))
nrep <- as.integer(get_arg(3, "10"))
nfolds <- as.integer(get_arg(4, "10"))
nCores <- as.integer(get_arg(5, "2"))
maxit <- as.integer(get_arg(6, "1000"))
resume <- tolower(get_arg(7, "true")) %in% c("true", "t", "1", "yes", "y")

if (!requireNamespace("pudms", quietly = TRUE)) stop("pudms is not installed")
library(pudms)
library(pbapply)
library(foreach)
library(parallel)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
paper_root <- normalizePath(file.path("reproduction", "pu-learning-paper-analysis-upstream"), mustWork = TRUE)
source(file.path(paper_root, "functions", "v.enr.R"))
source(file.path(paper_root, "functions", "log_enrichment_score.R"))

py_env <- new.env(parent = emptyenv())
load(file.path(paper_root, "data-r", "py1values.rda"), envir = py_env)
py1val <- unname(py_env$py1values[protein.name])
if (length(py1val) != 1 || is.na(py1val)) stop("No py1 value for dataset: ", protein.name)

data_env <- new.env(parent = emptyenv())
data_file <- file.path(paper_root, "data-r", paste0(protein.name, ".rda"))
if (!file.exists(data_file)) stop("Missing data file: ", data_file)
load(data_file, envir = data_env)
protein_dat <- data_env[[protein.name]]
refstate <- if (protein.name == "DXS") "A" else NULL

cat("dataset=", protein.name, "\n", sep = "")
cat("py1=", py1val, "\n", sep = "")
cat("nrep=", nrep, " nfolds=", nfolds, " nCores=", nCores, " resume=", resume, "\n", sep = "")
enr_nCores <- 1L
cat("enrichment_nCores=", enr_nCores, " (the upstream v.enr source does not export log_enrichment_score to PSOCK workers)\n", sep = "")
cat("unique_sequences=", nrow(protein_dat), "\n", sep = "")

all_rows <- list()
for (r in seq_len(nrep)) {
  rep_dir <- file.path(out_dir, protein.name)
  dir.create(rep_dir, recursive = TRUE, showWarnings = FALSE)
  metrics_file <- file.path(rep_dir, paste0("rep_", r, "_metrics.csv"))
  if (resume && file.exists(metrics_file)) {
    cached <- tryCatch(read.csv(metrics_file, stringsAsFactors = FALSE), error = function(e) NULL)
    valid_cached <- !is.null(cached) && all(c("dataset", "rep", "fold", "enrichment_auc", "pu_auc", "difference") %in% names(cached)) &&
      nrow(cached) == nfolds && all(cached$dataset == protein.name) && all(cached$rep == r) &&
      setequal(cached$fold, seq_len(nfolds)) && all(is.finite(cached$enrichment_auc)) &&
      all(is.finite(cached$pu_auc)) && all(is.finite(cached$difference)) &&
      isTRUE(all.equal(cached$difference, cached$pu_auc - cached$enrichment_auc, tolerance = 1e-12))
    if (valid_cached) {
      all_rows <- c(all_rows, list(cached))
      cat("resume_skip_rep=", r, "\n", sep = "")
      next
    }
  }
  log_file <- file.path(rep_dir, paste0("rep_", r, ".log"))
  zz <- file(log_file, open = "wt")
  sink(zz, type = "output")
  sink(zz, type = "message")
  ok <- FALSE
  tryCatch({
    seed <- 19462020 * r
    cat("rep=", r, " seed=", seed, "\n", sep = "")
    venrfit <- v.enr(
      protein_dat = protein_dat, py1 = py1val, nfolds = nfolds,
      refstate = refstate, test_idx = seq_len(nfolds), seed = seed,
      nCores = enr_nCores, verbose = TRUE
    )
    vfit <- pudms::v.pudms(
      protein_dat = protein_dat, py1 = py1val, nfolds = nfolds,
      refstate = refstate, test_idx = seq_len(nfolds), seed = seed,
      maxit = maxit, pvalue = FALSE, nCores = nCores,
      full.fit = FALSE, verbose = TRUE
    )
    enr_auc <- vapply(venrfit$v.enrfit, function(x) x[[1]]$test_roc$roc_curve$auc, numeric(1))
    pu_auc <- vapply(vfit$v.dmsfit, function(x) x[[1]]$test_roc$roc_curve$auc, numeric(1))
    row <- data.frame(
      dataset = protein.name, rep = r, fold = seq_len(min(length(enr_auc), length(pu_auc))),
      enrichment_auc = enr_auc[seq_len(min(length(enr_auc), length(pu_auc)))],
      pu_auc = pu_auc[seq_len(min(length(enr_auc), length(pu_auc)))],
      difference = pu_auc[seq_len(min(length(enr_auc), length(pu_auc)))] - enr_auc[seq_len(min(length(enr_auc), length(pu_auc)))],
      py1 = py1val, nfolds = nfolds, stringsAsFactors = FALSE
    )
    write.csv(row, metrics_file, row.names = FALSE)
    saveRDS(list(enrichment = venrfit, pu = vfit), file.path(rep_dir, paste0("rep_", r, ".rds")))
    # Use ordinary assignment here: tryCatch evaluates the body in the
    # caller's environment, and indexed <<- assignment is fragile in Rscript.
    all_rows <- c(all_rows, list(row))
    cat("mean_enrichment_auc=", mean(row$enrichment_auc), "\n", sep = "")
    cat("mean_pu_auc=", mean(row$pu_auc), "\n", sep = "")
    cat("mean_difference=", mean(row$difference), "\n", sep = "")
    ok <- TRUE
  }, error = function(err) {
    cat("ERROR: ", conditionMessage(err), "\n", sep = "")
  })
  cat("status=", if (ok) "ok" else "error", "\n", sep = "")
  sink(type = "message")
  sink(type = "output")
  close(zz)
}

if (length(all_rows)) {
  detail <- do.call(rbind, all_rows)
  write.csv(detail, file.path(out_dir, paste0(protein.name, "_enrichment_detail.csv")), row.names = FALSE)
  summary <- aggregate(cbind(enrichment_auc, pu_auc, difference) ~ dataset + rep, detail, mean)
  write.csv(summary, file.path(out_dir, paste0(protein.name, "_enrichment_summary.csv")), row.names = FALSE)
  cat("completed_reps=", length(unique(detail$rep)), "\n", sep = "")
} else {
  stop("No enrichment replicates completed")
}
