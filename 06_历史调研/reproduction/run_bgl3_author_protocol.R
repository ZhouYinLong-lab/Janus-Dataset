options(stringsAsFactors = FALSE)

library(pudms)

paper_root <- normalizePath(file.path("reproduction", "pu-learning-paper-analysis-upstream"), mustWork = TRUE)
e <- new.env(parent = emptyenv())
load(file.path(paper_root, "data-r", "Bgl3_LT.rda"), envir = e)
protein_dat <- e[["Bgl3_LT"]]

out_dir <- file.path("reproduction", "results", "multidataset_high_setting")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
log_file <- file.path(out_dir, "Bgl3_LT_author_protocol.log")
zz <- file(log_file, open = "wt")
sink(zz, type = "output")
sink(zz, type = "message")
on.exit({
  sink(type = "message")
  sink(type = "output")
  close(zz)
}, add = TRUE)

cat("dataset=Bgl3_LT\n")
cat("protocol=author_vfit_Bgl3_LT.R\n")
cat("py1=0.35\n")
cat("nfolds=10\n")
cat("nhyperparam=1\n")
cat("n_unique=", nrow(protein_dat), "\n", sep = "")

vfit <- pudms::v.pudms(
  protein_dat = protein_dat,
  py1 = 0.35,
  nfolds = 10,
  nCores = 2,
  pvalue = TRUE,
  full.fit = TRUE,
  full.fit.pvalue = TRUE,
  seed = 23002020,
  nhyperparam = 1,
  verbose = TRUE
)
vfit$py1.opt <- 0.35
saveRDS(vfit, file.path(out_dir, "Bgl3_LT_author_protocol.rds"))

roc <- vfit$roc_curves[[which.min(abs(vfit$py1 - 0.35))]]
result <- data.frame(
  dataset = "Bgl3_LT",
  protocol = "author_vfit_Bgl3_LT.R",
  py1 = 0.35,
  nfolds = 10,
  nhyperparam = 1,
  n_unique = nrow(protein_dat),
  auc_corrected = as.numeric(roc$auc),
  auc_pu = as.numeric(roc$auc_pu),
  reference_auc = 0.794615994869779,
  difference_from_reference = as.numeric(roc$auc) - 0.794615994869779,
  stringsAsFactors = FALSE
)
write.csv(result, file.path(out_dir, "Bgl3_LT_author_protocol_metrics.csv"), row.names = FALSE)
print(result)
