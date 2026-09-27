options(stringsAsFactors = FALSE)

# Combine per-replicate PU-vs-enrichment results from local reproductions.
# Incomplete datasets remain visible and are marked as such.

args <- commandArgs(trailingOnly = TRUE)
out_file <- if (length(args) >= 1) args[[1]] else
  file.path("reproduction", "results", "enrichment_multidataset_summary.csv")

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
    "reproduction/results/enrichment_bgl3_full/Bgl3_enrichment_summary.csv",
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
    "reproduction/results/enrichment_bgl3_full/Bgl3_enrichment_detail.csv",
    "reproduction/results/enrichment_gb1_full/GB1_enrichment_detail.csv"
  ),
  author_mean_difference = c(0.002690, 0.000241, 0.000492, 0.010200, 0.001830,
                             0.007006, 0.003216, 0.002796, 0.016694, 0.004746)
)

rows <- lapply(seq_len(nrow(inputs)), function(i) {
  spec <- inputs[i, ]
  if (!file.exists(spec$summary_file)) return(NULL)

  x <- read.csv(spec$summary_file, check.names = FALSE)
  required <- c("dataset", "rep", "enrichment_auc", "pu_auc", "difference")
  if (!all(required %in% names(x))) stop("Invalid summary columns: ", spec$summary_file)
  if (any(!is.finite(x$difference))) stop("Non-finite difference: ", spec$summary_file)
  if (anyDuplicated(x$rep)) stop("Duplicate replicate IDs: ", spec$summary_file)

  fold_counts <- integer()
  if (file.exists(spec$detail_file)) {
    detail <- read.csv(spec$detail_file, check.names = FALSE)
    if (all(c("rep", "fold") %in% names(detail))) {
      fold_counts <- vapply(split(detail$fold, detail$rep), function(z) length(unique(z)), integer(1))
    }
  }
  nfolds <- if (length(fold_counts) && length(unique(fold_counts)) == 1L) unname(fold_counts[1]) else NA_integer_
  if (is.na(nfolds) && "nfolds" %in% names(x) && length(unique(x$nfolds)) == 1L) {
    nfolds <- as.integer(unique(x$nfolds))
  }

  d <- x$difference
  test <- if (length(d) > 1L) t.test(d, mu = 0) else NULL
  ci <- if (!is.null(test)) test$conf.int else c(NA_real_, NA_real_)
  status <- if (length(d) == 10L && identical(nfolds, 10L)) "complete_10x10" else "partial_or_unverified"
  data.frame(
    dataset = spec$dataset,
    nrep = length(d),
    nfolds = nfolds,
    status = status,
    mean_enrichment_auc = mean(x$enrichment_auc),
    mean_pu_auc = mean(x$pu_auc),
    mean_difference = mean(d),
    sd_replicate_difference = if (length(d) > 1L) sd(d) else NA_real_,
    ci95_lower = ci[1],
    ci95_upper = ci[2],
    replicate_level_t_p_value = if (!is.null(test)) test$p.value else NA_real_,
    author_mean_difference = spec$author_mean_difference,
    local_minus_author_difference = mean(d) - spec$author_mean_difference
  )
})

result <- do.call(rbind, Filter(Negate(is.null), rows))
if (is.null(result) || !nrow(result)) stop("No local enrichment summaries were found")
dir.create(dirname(out_file), recursive = TRUE, showWarnings = FALSE)
write.csv(result, out_file, row.names = FALSE)
print(result, row.names = FALSE)
cat("wrote", out_file, "\n")
