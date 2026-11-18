options(stringsAsFactors = FALSE)

if (!requireNamespace("pudms", quietly = TRUE)) {
  stop("pudms is not installed. Run: Rscript -e \"install.packages('reproduction/pudms-upstream', repos=NULL, type='source')\"")
}

args <- commandArgs(trailingOnly = TRUE)
out_dir <- if (length(args) >= 1) args[[1]] else file.path("reproduction", "results", "author_example")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

pkg_root <- normalizePath(file.path("reproduction", "pudms-upstream"), mustWork = TRUE)
pos_file <- file.path(pkg_root, "inst", "quickexample", "Rocker_sel_sequences_filtered.txt.gz")
unlab_file <- file.path(pkg_root, "inst", "quickexample", "Rocker_ref_sequences_filtered.txt.gz")

log_file <- file.path(out_dir, "run.log")
zz <- file(log_file, open = "wt")
sink(zz, type = "output")
sink(zz, type = "message")
on.exit({
  sink(type = "message")
  sink(type = "output")
  close(zz)
}, add = TRUE)

cat("R version:", R.version.string, "\n")
cat("pudms version:", as.character(packageVersion("pudms")), "\n")
cat("Positive file:", pos_file, "\n")
cat("Unlabeled file:", unlab_file, "\n")

protein_dat <- pudms::create_protein_dat(path_l = pos_file, path_u = unlab_file)
cat("Unique sequences:", nrow(protein_dat), "\n")
cat("Labeled reads:", sum(protein_dat$labeled), "\n")
cat("Unlabeled reads:", sum(protein_dat$unlabeled), "\n")

# The author's example scans ten prevalence values and uses five folds.
# We use two workers on Windows to keep the run reproducible and modest.
fit <- pudms::v.pudms(
  protein_dat = protein_dat,
  py1 = NULL,
  order = 1,
  refstate = NULL,
  nobs_thresh = 10,
  n_eff_prop = 1,
  nhyperparam = 10,
  nfolds = 5,
  nCores = 2,
  seed = 20260921,
  verbose = TRUE
)

saveRDS(fit, file.path(out_dir, "author_cv_fit.rds"))
write.csv(
  data.frame(py1 = fit$py1, selected = fit$py1 == fit$py1.opt),
  file.path(out_dir, "py_grid.csv"),
  row.names = FALSE
)

selected_roc <- fit$roc_curves[[which(fit$py1 == fit$py1.opt)]]
writeLines(
  c(
    paste0("selected_py=", fit$py1.opt),
    paste0("auc_corrected=", selected_roc$auc),
    paste0("auc_pu=", selected_roc$auc_pu),
    paste0("n_folds=5"),
    paste0("n_hyperparameters=10")
  ),
  file.path(out_dir, "metrics.txt")
)

if (requireNamespace("ggplot2", quietly = TRUE)) {
  p <- pudms::rocplot(
    roc_curve = selected_roc,
    py1 = fit$py1.opt
  )
  ggplot2::ggsave(file.path(out_dir, "Rocker_CV_ROC.png"), p, width = 6, height = 5, dpi = 150)
}

cat("Selected py:", fit$py1.opt, "\n")
cat("Completed author-example reproduction.\n")
