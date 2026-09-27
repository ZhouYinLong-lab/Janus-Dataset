# Enrichment baseline 对照复现

## 目的

Song 等人的分析不仅比较了 PU learning 与作者方法，还把 PU 模型与基于 log-enrichment score 的方法进行对照。这里单独复现这一部分，用同一数据划分、同一 `py1` 和同一批随机种子，比较每个测试折上的 AUC。

## 作者实现

代码来自作者分析仓库：

- `code/enrich_comparison/enr_test_fit.R`
- `code/enrich_comparison/enr_test_summarize.R`
- `functions/v.enr.R`
- `functions/log_enrichment_score.R`

作者脚本的原始设置是每个数据集 10 次重复、每次 10 折；`py1` 从 `data-r/py1values.rda` 读取，种子为 `19462020 * r`。本地脚本 `run_enrichment_baseline.R` 保留这一逻辑，并把每个重复的日志、RDS 和逐折指标单独保存。

## 运行方式

```powershell
$env:R_LIBS_USER = 'D:/Scoop/persist/r/site-library'
Rscript reproduction/run_enrichment_baseline.R DXS reproduction/results/enrichment 10 10 2 1000
```

参数依次为：数据集、输出目录、重复次数、折数、PU 模型的并行 worker 数、最大迭代次数，以及是否断点续跑（默认为 `true`）。开启续跑时，脚本会跳过已有且包含完整折数指标的重复，仅重算缺失或不完整的重复；设为 `false` 可强制重跑。首次验证可使用较小的 `nrep` 或 `nfolds`，但小设置不能直接当作论文原始设置的最终结果。

## 作者仓库中的可用证据

作者提交的 `PU_enr_pvalue_diff.csv` 报告了 PU AUC 与 enrichment AUC 的配对差异检验。其 `mean_diff` 在十个数据集上均为正：LGK 0.000241、PyKS 0.000492、DXS 0.002690、rocker 0.010200、SUMO1 0.007006、HA 0.001830、UBE2I 0.003216、TPK1 0.002796、Bgl3 0.016694、GB1 0.004746；对应的 p 值均小于 0.001。

这支持作者方法在该特定数据和评价设置下优于 enrichment baseline，但不能单独证明优势只来自 PU 标签处理；还需要查看数据划分、模型参数、特征表示和重复实验是否严格一致。本地复现结果以 `*_enrichment_detail.csv`、`*_enrichment_summary.csv` 和每个重复的 `.log` 为准。

## 本地链路验证

已在 DXS 上完成 1 次重复、3 折的快速验证：enrichment 平均 AUC 为 0.976956，PU 平均 AUC 为 0.979634，配对差值为 +0.002677。该结果仅证明脚本、作者函数和指标提取链路可运行；由于重复次数和折数低于作者设置，不能替代十次重复的统计结论。

随后按作者的 10 次重复、10 折设置完成了 DXS。10 次重复的平均差值为 +0.002690，重复间标准差为 0.00000205，配对 t 检验 `p = 1.37 × 10^-29`。这与作者汇总文件中 DXS 的 `mean_diff = 0.002690` 基本一致。由于上游 `v.enr.R` 没有把 `log_enrichment_score` 导出到 Windows PSOCK worker，本地复现将 enrichment 部分固定为单 worker；这改变运行速度，不改变 enrichment 计算公式或数据划分。

LGK 也按 10 次重复、10 折设置完成。10 次重复的平均差值为 +0.0002411，重复间标准差为 0.00000790，配对 t 检验 `p = 6.97 × 10^-15`；作者汇总文件中的 LGK `mean_diff = 0.0002413`，两者在数值上吻合。LGK 的逐折和逐重复结果保存在 `reproduction/results/enrichment/LGK_enrichment_detail.csv` 与 `LGK_enrichment_summary.csv`。

rocker 也按 10 次重复、10 折设置完成。逐重复平均后，enrichment AUC 为 `0.8079594`，PU AUC 为 `0.8181656`，配对差值为 `+0.0102063`（重复间标准差 `8.94 × 10^-6`，95% t 区间 `[0.0101999, 0.0102127]`，对 10 个重复级差值进行单样本 t 检验得到 `p = 4.88 × 10^-29`）。作者汇总文件报告 rocker `mean_diff = 0.010200`，本地复现相差约 `6.3 × 10^-6`。结果见 `reproduction/results/enrichment_rocker_full/rocker_enrichment_detail.csv`、`rocker_enrichment_summary.csv` 和 `rocker_enrichment_repro_summary.csv`；每个重复的日志、逐折指标和 RDS 在同目录的 `rocker/` 子目录中。

聚合统计由 `reproduction/summarize_enrichment_reproduction.R` 从逐重复汇总表计算。例：

```powershell
Rscript reproduction/summarize_enrichment_reproduction.R reproduction/results/enrichment_rocker_full/rocker_enrichment_summary.csv 0.010200 10
```

当前 DXS、LGK、PyKS、rocker 和 HA 五个数据集均完成作者的 10×10 设置，PU 相对 enrichment 的平均 AUC 差均为正，并与作者报告值接近。五数据集逐重复差值图为 `reproduction/results/figures/enrichment_pu_auc_difference_all.png`。

PyKS 的 10×10 批次也已完成。enrichment 平均 AUC 为 `0.8492676`，PU 平均 AUC 为 `0.8497528`，重复级差值均值为 `+0.0004852`（标准差 `3.34 × 10^-6`，95% t 区间 `[0.0004828, 0.0004876]`，重复级单样本 t 检验 `p = 5.65 × 10^-21`）。作者报告 `mean_diff = 0.000492`，本地差约 `−6.8 × 10^-6`。统计上差异稳定为正，但绝对 AUC 增益约 `0.0005`，实际大小有限；不能只凭很小的 p 值称为显著的实际性能提升。结果见 `reproduction/results/enrichment_pyks_full/PyKS_enrichment_detail.csv`、`PyKS_enrichment_summary.csv` 和 `PyKS_enrichment_repro_summary.csv`；重复日志、逐折指标和 RDS 保存在 `PyKS/` 子目录。

HA 的 10×10 批次已完成。enrichment 平均 AUC 为 `0.6786324`，PU 平均 AUC 为 `0.6804630`，重复级差值均值为 `+0.0018305`（标准差 `4.61 × 10^-6`，95% t 区间 `[0.0018272, 0.0018338]`，重复级单样本 t 检验 `p = 6.62 × 10^-25`）；作者报告 `mean_diff = 0.001830`，本地结果与其吻合。结果见 `reproduction/results/enrichment_ha_full/HA_enrichment_detail.csv`、`HA_enrichment_summary.csv` 和 `HA_enrichment_repro_summary.csv`；十次重复的逐折指标、日志和 RDS 保存在 `HA/` 子目录。首轮计算在最终汇总时异常退出；使用断点续跑重读全部十份完整逐折指标后，批次脚本正常生成 detail 和 summary，统计脚本再生成置信区间与检验结果，五数据集图也已更新。

## 已知限制

作者仓库中的 `res_comp.Rdata` 采用 Git LFS，但该仓库当前 LFS 服务不可用，因此本地不能直接读取该二进制汇总文件；可读的 `PU_enr_pvalue_diff.csv` 和源代码仍然存在。本文档区分“作者已提交的汇总证据”和“本地重新运行的结果”，不把前者冒充本地复现。
