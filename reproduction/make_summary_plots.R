options(stringsAsFactors = FALSE)

if (!requireNamespace("ggplot2", quietly = TRUE)) stop("ggplot2 is not installed")
library(ggplot2)

fig_dir <- file.path("reproduction", "results", "figures")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

metrics <- read.csv(file.path("reproduction", "results", "multidataset", "metrics_all.csv"), check.names = FALSE)
high_file <- file.path("reproduction", "results", "multidataset_high_setting", "metrics_all.csv")
if (file.exists(high_file)) {
  high <- read.csv(high_file, check.names = FALSE)
  high$source_file <- basename(high_file)
  replace_datasets <- intersect(metrics$dataset, high$dataset)
  metrics <- rbind(
    metrics[!metrics$dataset %in% replace_datasets, , drop = FALSE],
    high
  )
}
author_bgl3_file <- file.path("reproduction", "results", "multidataset_high_setting",
                             "Bgl3_LT_author_protocol_metrics.csv")
if (file.exists(author_bgl3_file)) {
  author_bgl3 <- read.csv(author_bgl3_file, check.names = FALSE)
  bgl3_idx <- which(metrics$dataset == "Bgl3_LT")
  if (length(bgl3_idx)) {
    metrics$auc_corrected[bgl3_idx[1]] <- author_bgl3$auc_corrected[1]
    metrics$reference_auc[bgl3_idx[1]] <- author_bgl3$reference_auc[1]
    metrics$nfolds[bgl3_idx[1]] <- author_bgl3$nfolds[1]
    metrics$nhyperparam[bgl3_idx[1]] <- author_bgl3$nhyperparam[1]
  }
}
author_setting_file <- file.path("reproduction", "results", "multidataset_author_setting",
                                "metrics_all.csv")
if (file.exists(author_setting_file)) {
  author_setting <- read.csv(author_setting_file, check.names = FALSE)
  for (dataset_name in author_setting$dataset) {
    idx <- which(metrics$dataset == dataset_name)
    src <- which(author_setting$dataset == dataset_name)[1]
    if (length(idx)) {
      metrics$auc_corrected[idx[1]] <- author_setting$auc_corrected[src]
      metrics$reference_auc[idx[1]] <- author_setting$reference_auc[src]
      metrics$nfolds[idx[1]] <- author_setting$nfolds[src]
      metrics$nhyperparam[idx[1]] <- author_setting$nhyperparam[src]
    }
  }
}
metrics <- metrics[order(metrics$reference_auc), , drop = FALSE]
metrics$dataset <- factor(metrics$dataset, levels = metrics$dataset)
metrics_long <- rbind(
  data.frame(dataset = metrics$dataset, value = metrics$auc_corrected, series = "Reproduced AUC"),
  data.frame(dataset = metrics$dataset, value = metrics$reference_auc, series = "Author reference AUC")
)

p_auc <- ggplot(metrics_long, aes(dataset, value, fill = series)) +
  geom_col(position = position_dodge(width = 0.78), width = 0.7) +
  geom_text(data = metrics, aes(dataset, auc_corrected, label = sprintf("%sfold/%spy", nfolds, nhyperparam)),
            inherit.aes = FALSE, vjust = -0.3, size = 3) +
  coord_cartesian(ylim = c(0.6, 1.02), clip = "off") +
  labs(x = NULL, y = "ROC AUC", fill = NULL,
       title = "PU learning: reproduced vs author reference AUC") +
  theme_classic(base_size = 13) +
  theme(axis.text.x = element_text(angle = 35, hjust = 1), legend.position = "top")
ggsave(file.path(fig_dir, "multidataset_auc_vs_reference.png"), p_auc,
       width = 10, height = 5.8, dpi = 220)

dxs <- read.csv(file.path("reproduction", "results", "enrichment", "DXS_enrichment_summary.csv"))
lgk <- read.csv(file.path("reproduction", "results", "enrichment", "LGK_enrichment_summary.csv"))
ha_full_file <- file.path("reproduction", "results", "enrichment_ha_full", "HA_enrichment_summary.csv")
pyks_file <- file.path("reproduction", "results", "enrichment_pyks_full", "PyKS_enrichment_summary.csv")
rocker_file <- file.path("reproduction", "results", "enrichment_rocker_full", "rocker_enrichment_summary.csv")
sumo1_file <- file.path("reproduction", "results", "enrichment_sumo1_full", "SUMO1_enrichment_summary.csv")
ube2i_file <- file.path("reproduction", "results", "enrichment_ube2i_full", "UBE2I_enrichment_summary.csv")
enr_tables <- list(dxs, lgk)
if (file.exists(pyks_file)) enr_tables <- c(enr_tables, list(read.csv(pyks_file)))
if (file.exists(rocker_file)) enr_tables <- c(enr_tables, list(read.csv(rocker_file)))
if (file.exists(ha_full_file)) enr_tables <- c(enr_tables, list(read.csv(ha_full_file)))
if (file.exists(sumo1_file)) enr_tables <- c(enr_tables, list(read.csv(sumo1_file)))
if (file.exists(ube2i_file)) enr_tables <- c(enr_tables, list(read.csv(ube2i_file)))
enr <- do.call(rbind, lapply(enr_tables, function(x) x[, c("dataset", "difference")]))
enr$dataset <- factor(enr$dataset, levels = c("DXS", "LGK", "PyKS", "rocker", "HA", "SUMO1", "UBE2I"))
p_diff <- ggplot(enr, aes(dataset, difference, fill = dataset)) +
  geom_boxplot(width = 0.45, alpha = 0.65, outlier.shape = NA) +
  geom_jitter(width = 0.08, size = 2, alpha = 0.8) +
  geom_hline(yintercept = 0, linetype = "dashed") +
  labs(x = NULL, y = "AUC(PU) - AUC(enrichment)",
       title = "PU vs enrichment baseline: paired AUC differences") +
  theme_classic(base_size = 13) +
  theme(legend.position = "none")
ggsave(file.path(fig_dir, "enrichment_pu_auc_difference_all.png"), p_diff,
       width = 6.5, height = 5.2, dpi = 220)

cat("wrote", file.path(fig_dir, "multidataset_auc_vs_reference.png"), "\n")
cat("wrote", file.path(fig_dir, "enrichment_pu_auc_difference_all.png"), "\n")
