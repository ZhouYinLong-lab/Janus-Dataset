options(stringsAsFactors = FALSE)

args <- commandArgs(trailingOnly = TRUE)
dataset_arg <- if (length(args) >= 1) args[[1]] else "DXS,LGK,HA"
out_dir <- if (length(args) >= 2) args[[2]] else file.path("reproduction", "results", "multidataset")
nfolds <- if (length(args) >= 3) as.integer(args[[3]]) else 5L
nhyperparam <- if (length(args) >= 4) as.integer(args[[4]]) else 10L
nCores <- if (length(args) >= 5) as.integer(args[[5]]) else 2L
datasets <- trimws(strsplit(dataset_arg, ",", fixed = TRUE)[[1]])

if (!requireNamespace("pudms", quietly = TRUE)) stop("pudms is not installed")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
paper_root <- normalizePath(file.path("reproduction", "pu-learning-paper-analysis-upstream"), mustWork = TRUE)

reference_auc <- data.frame(
  dataset = c("DXS", "GB1", "PyKS", "rocker", "UBE2I", "Bgl3_LT", "SUMO1", "TPK1", "LGK", "HA"),
  reference_auc = c(0.979644503433839, 0.869844250134942, 0.849753278800652, 0.818176344358205,
                   0.803275489330949, 0.794615994869779, 0.763221300673299, 0.761575564672715,
                   0.744099037230703, 0.680454834486221)
)

all_metrics <- list()
for (protein.name in datasets) {
  safe_name <- gsub("[^A-Za-z0-9_.-]", "_", protein.name)
  log_file <- file.path(out_dir, paste0(safe_name, ".log"))
  zz <- file(log_file, open = "wt")
  sink(zz, type = "output")
  sink(zz, type = "message")
  started <- Sys.time()
  ok <- FALSE
  tryCatch({
    cat("dataset=", protein.name, "\n", sep = "")
    cat("started=", format(started, tz = "UTC"), "\n", sep = "")
    data_file <- file.path(paper_root, "data-r", paste0(protein.name, ".rda"))
    if (!file.exists(data_file)) stop("Missing data file: ", data_file)
    e <- new.env(parent = emptyenv())
    load(data_file, envir = e)
    protein_dat <- e[[protein.name]]
    cat("unique_sequences=", nrow(protein_dat), "\n", sep = "")
    cat("labeled_reads=", sum(protein_dat$labeled), "\n", sep = "")
    cat("unlabeled_reads=", sum(protein_dat$unlabeled), "\n", sep = "")

    refstate <- if (protein.name == "DXS") "A" else NULL
    fit <- pudms::v.pudms(
      protein_dat = protein_dat,
      nfolds = nfolds,
      refstate = refstate,
      nCores = nCores,
      pvalue = FALSE,
      full.fit = FALSE,
      seed = 23002020,
      nhyperparam = nhyperparam,
      verbose = TRUE
    )
    saveRDS(fit, file.path(out_dir, paste0(safe_name, ".rds")))
    selected <- fit$roc_curves[[which(fit$py1 == fit$py1.opt)]]
    ref <- reference_auc$reference_auc[match(protein.name, reference_auc$dataset)]
    row <- data.frame(
      dataset = protein.name,
      n_unique = nrow(protein_dat),
      labeled_reads = sum(protein_dat$labeled),
      unlabeled_reads = sum(protein_dat$unlabeled),
      nfolds = nfolds,
      nhyperparam = nhyperparam,
      selected_py = fit$py1.opt,
      auc_corrected = selected$auc,
      auc_pu = selected$auc_pu,
      reference_auc = ref,
      difference_from_reference = selected$auc - ref,
      status = "ok",
      stringsAsFactors = FALSE
    )
    all_metrics[[protein.name]] <- row
    write.csv(row, file.path(out_dir, paste0(safe_name, "_metrics.csv")), row.names = FALSE)
    cat("selected_py=", fit$py1.opt, "\n", sep = "")
    cat("auc_corrected=", selected$auc, "\n", sep = "")
    cat("auc_pu=", selected$auc_pu, "\n", sep = "")
    cat("reference_auc=", ref, "\n", sep = "")
    ok <- TRUE
  }, error = function(err) {
    row <- data.frame(dataset = protein.name, status = paste0("error: ", conditionMessage(err)), stringsAsFactors = FALSE)
    all_metrics[[protein.name]] <<- row
    write.csv(row, file.path(out_dir, paste0(safe_name, "_metrics.csv")), row.names = FALSE)
    cat("ERROR: ", conditionMessage(err), "\n", sep = "")
  })
  cat("finished=", format(Sys.time(), tz = "UTC"), "\n", sep = "")
  cat("status=", if (ok) "ok" else "error", "\n", sep = "")
  sink(type = "message")
  sink(type = "output")
  close(zz)
}

combined <- do.call(rbind, all_metrics)
write.csv(combined, file.path(out_dir, "metrics.csv"), row.names = FALSE)
print(combined)
