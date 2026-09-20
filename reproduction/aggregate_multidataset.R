options(stringsAsFactors = FALSE)

args <- commandArgs(trailingOnly = TRUE)
out_dir <- if (length(args) >= 1) args[[1]] else file.path("reproduction", "results", "multidataset")
files <- list.files(out_dir, pattern = "_metrics\\.csv$", full.names = TRUE)
if (!length(files)) stop("No *_metrics.csv files found in ", out_dir)

rows <- lapply(files, function(f) {
  x <- tryCatch(read.csv(f, check.names = FALSE), error = function(e) NULL)
  if (is.null(x) || !nrow(x)) return(NULL)
  x$source_file <- basename(f)
  x
})
rows <- Filter(Negate(is.null), rows)
metrics <- do.call(rbind, rows)
if ("dataset" %in% names(metrics)) {
  order_idx <- match(metrics$dataset, c("DXS", "GB1", "PyKS", "rocker", "UBE2I", "Bgl3_LT", "SUMO1", "TPK1", "LGK", "HA"))
  metrics <- metrics[order(order_idx, metrics$dataset), , drop = FALSE]
}
write.csv(metrics, file.path(out_dir, "metrics_all.csv"), row.names = FALSE)
print(metrics)
