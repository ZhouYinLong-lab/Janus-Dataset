options(stringsAsFactors = FALSE)

library(pudms)

paper_root <- file.path("reproduction", "pu-learning-paper-analysis-upstream")
e <- new.env(parent = emptyenv())
load(file.path(paper_root, "data-r", "Bgl3_LT.rda"), envir = e)
protein_dat <- e[["Bgl3_LT"]]

cat("dataset=Bgl3_LT\n")
cat("py1=0.35\n")
cat("n_unique=", nrow(protein_dat), "\n", sep = "")
fit <- pudms::pudms(protein_dat = protein_dat, py1 = 0.35, pvalue = FALSE)
roc <- pudms::adjusted_roc_curve(
  coef = fit$fit$coef,
  test_grouped_dat = protein_dat,
  py1 = 0.35,
  plot = FALSE,
  verbose = FALSE
)
auc_value <- roc$roc_curve$auc
cat("auc=", auc_value, "\n", sep = "")

result <- data.frame(
  dataset = "Bgl3_LT",
  py1 = 0.35,
  n_unique = nrow(protein_dat),
  auc = as.numeric(auc_value),
  stringsAsFactors = FALSE
)
write.csv(result,
          file.path("reproduction", "results", "multidataset_high_setting",
                    "Bgl3_LT_fixed_py035_metrics.csv"),
          row.names = FALSE)
