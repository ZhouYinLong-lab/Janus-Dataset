options(stringsAsFactors = FALSE)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript reproduction/summarize_enrichment_reproduction.R <dataset_enrichment_summary.csv> [author_mean_difference] [nfolds]")
}

summary_file <- args[[1]]
author_mean_difference <- if (length(args) >= 2) as.numeric(args[[2]]) else NA_real_
nfolds_arg <- if (length(args) >= 3) as.integer(args[[3]]) else NA_integer_
if (!file.exists(summary_file)) stop("Summary file not found: ", summary_file)

x <- read.csv(summary_file, check.names = FALSE)
required <- c("dataset", "rep", "enrichment_auc", "pu_auc", "difference")
if (!all(required %in% names(x))) stop("Input must contain: ", paste(required, collapse = ", "))
if (length(unique(x$dataset)) != 1) stop("Input must contain exactly one dataset")
if (any(!is.finite(x$difference))) stop("Replicate differences must all be finite")

d <- x$difference
mean_ci <- if (length(d) > 1) t.test(d, mu = 0)$conf.int else c(NA_real_, NA_real_)
p_value <- if (length(d) > 1) t.test(d, mu = 0)$p.value else NA_real_
dataset_name <- unique(x$dataset)
result <- data.frame(
  dataset = dataset_name,
  nrep = length(d),
  nfolds = if (is.finite(nfolds_arg)) nfolds_arg else if ("nfolds" %in% names(x)) unique(x$nfolds)[1] else NA_integer_,
  mean_enrichment_auc = mean(x$enrichment_auc),
  mean_pu_auc = mean(x$pu_auc),
  mean_difference = mean(d),
  sd_replicate_difference = if (length(d) > 1) sd(d) else NA_real_,
  ci95_lower = mean_ci[1],
  ci95_upper = mean_ci[2],
  replicate_level_t_p_value = p_value,
  author_mean_difference = author_mean_difference
)

out_file <- sub("_enrichment_summary\\.csv$", "_enrichment_repro_summary.csv", summary_file)
if (identical(out_file, summary_file)) {
  out_file <- file.path(dirname(summary_file), paste0(dataset_name, "_enrichment_repro_summary.csv"))
}
write.csv(result, out_file, row.names = FALSE)
print(result)
cat("wrote", out_file, "\n")
