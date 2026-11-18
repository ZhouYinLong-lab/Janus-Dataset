options(stringsAsFactors = FALSE)

# Strict integrity check for the full author-setting PU-vs-enrichment reruns.
# This deliberately audits the paired fold-level files, not just the summaries.
inputs <- data.frame(
  dataset = c("DXS", "LGK", "PyKS", "rocker", "HA", "SUMO1", "UBE2I", "TPK1", "Bgl3", "GB1"),
  summary_file = c(
    "reproduction/results/enrichment/DXS_enrichment_summary.csv",
    "reproduction/results/enrichment/LGK_enrichment_summary.csv",
    "reproduction/results/enrichment_pyks_full/PyKS_enrichment_summary.csv",
    "reproduction/results/enrichment_rocker_full/rocker_enrichment_summary.csv",
    "reproduction/results/enrichment_ha_full/HA_enrichment_summary.csv",
    "reproduction/results/enrichment_sumo1_full/SUMO1_enrichment_summary.csv",
    "reproduction/results/enrichment_ube2i_full/UBE2I_enrichment_summary.csv",
    "reproduction/results/enrichment_tpk1_full/TPK1_enrichment_summary.csv",
    "reproduction/results/enrichment_bgl3_full/Bgl3_LT_enrichment_summary.csv",
    "reproduction/results/enrichment_gb1_full/GB1_enrichment_summary.csv"
  ),
  detail_file = c(
    "reproduction/results/enrichment/DXS_enrichment_detail.csv",
    "reproduction/results/enrichment/LGK_enrichment_detail.csv",
    "reproduction/results/enrichment_pyks_full/PyKS_enrichment_detail.csv",
    "reproduction/results/enrichment_rocker_full/rocker_enrichment_detail.csv",
    "reproduction/results/enrichment_ha_full/HA_enrichment_detail.csv",
    "reproduction/results/enrichment_sumo1_full/SUMO1_enrichment_detail.csv",
    "reproduction/results/enrichment_ube2i_full/UBE2I_enrichment_detail.csv",
    "reproduction/results/enrichment_tpk1_full/TPK1_enrichment_detail.csv",
    "reproduction/results/enrichment_bgl3_full/Bgl3_LT_enrichment_detail.csv",
    "reproduction/results/enrichment_gb1_full/GB1_enrichment_detail.csv"
  ),
  author_mean_difference = c(0.002690, 0.000241, 0.000492, 0.010200, 0.001830,
                             0.007006, 0.003216, 0.002796, 0.016694, 0.004746)
)

audit_one <- function(spec) {
  if (!file.exists(spec$summary_file) || !file.exists(spec$detail_file)) {
    stop("Missing summary or detail file for ", spec$dataset)
  }
  summary <- read.csv(spec$summary_file, check.names = FALSE)
  detail <- read.csv(spec$detail_file, check.names = FALSE)
  needed_summary <- c("rep", "enrichment_auc", "pu_auc", "difference")
  needed_detail <- c("rep", "fold", "enrichment_auc", "pu_auc", "difference")
  if (!all(needed_summary %in% names(summary)) || !all(needed_detail %in% names(detail))) {
    stop("Unexpected columns for ", spec$dataset)
  }
  if (anyDuplicated(summary$rep) || anyDuplicated(detail[c("rep", "fold")])) {
    stop("Duplicate replicate or replicate/fold row for ", spec$dataset)
  }
  expected <- expand.grid(rep = 1:10, fold = 1:10)
  observed <- detail[c("rep", "fold")]
  if (nrow(summary) != 10L || nrow(detail) != 100L ||
      !setequal(summary$rep, 1:10) || !setequal(paste(observed$rep, observed$fold),
                                                paste(expected$rep, expected$fold))) {
    stop("Expected exactly 10 replicates x 10 folds for ", spec$dataset)
  }
  if (any(!is.finite(as.matrix(detail[c("enrichment_auc", "pu_auc", "difference")])))) {
    stop("Non-finite fold metric for ", spec$dataset)
  }
  fold_error <- abs(detail$difference - (detail$pu_auc - detail$enrichment_auc))
  if (any(fold_error > 1e-10)) stop("Fold-level difference mismatch for ", spec$dataset)

  by_rep <- aggregate(cbind(enrichment_auc, pu_auc, difference) ~ rep, detail, mean)
  summary <- summary[match(by_rep$rep, summary$rep), ]
  summary_error <- max(abs(summary$difference - by_rep$difference))
  if (!is.finite(summary_error) || summary_error > 1e-10) {
    stop("Summary does not match fold-level metrics for ", spec$dataset)
  }
  data.frame(
    dataset = spec$dataset,
    n_replicates = nrow(summary),
    folds_per_replicate = 10L,
    mean_enrichment_auc = mean(by_rep$enrichment_auc),
    mean_pu_auc = mean(by_rep$pu_auc),
    mean_difference = mean(by_rep$difference),
    author_mean_difference = spec$author_mean_difference,
    local_minus_author_difference = mean(by_rep$difference) - spec$author_mean_difference,
    fold_identity_mismatches = sum(fold_error > 1e-10),
    max_summary_aggregation_error = summary_error,
    status = "PASS"
  )
}

result <- do.call(rbind, lapply(seq_len(nrow(inputs)), function(i) audit_one(inputs[i, ])))
out_file <- file.path("reproduction", "results", "enrichment_multidataset_audit.csv")
write.csv(result, out_file, row.names = FALSE)
print(result, row.names = FALSE)
cat("Wrote", out_file, "\n")
