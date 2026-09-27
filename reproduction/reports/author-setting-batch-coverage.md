# 作者级多数据集复现批次记录

## 批次目的

本批次把 UBE2I、SUMO1、TPK1 从轻量预检提升到作者通用脚本对应的 10 折 × 20 个 `py` 候选值设置，用于判断已有的 PU ROC/AUC 复现是否能够跨数据集稳定成立。

运行命令为：

```powershell
Rscript reproduction/run_multidataset.R "UBE2I,SUMO1,TPK1" reproduction/results/multidataset_author_setting_remaining 10 20 2
```

脚本使用随机种子 `23002020`、`nCores=2`、`pvalue=FALSE` 和 `full.fit=FALSE`。这里的“作者级”指折数和 `py` 搜索规模与作者通用多数据集脚本一致；AUC 复现不等同于重新生成作者全部内部中间对象。

## 已完成结果

| 数据集 | unique sequences | 10 折 × `py` | 选定 `py` | 校正 AUC | PU AUC | 作者参考 AUC | 差值 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| UBE2I | 265,733 | 10×20 | 0.001000 | 0.8032754893 | 0.8029722138 | 0.8032754893 | 约 0 | 完成 |
| SUMO1 | 212,621 | 10×20 | 0.001000 | 0.7632213007 | 0.7629580794 | 0.7632213007 | 约 0 | 完成 |

两个数据集的校正 AUC 都与作者仓库参考值相符到浮点舍入误差。结果文件位于 `../results/multidataset_author_setting_remaining/`，包括每个数据集的 `_metrics.csv`、运行日志和本地 `.rds` 输出；`metrics_all.csv` 是两个已完成数据集的合并表。

## TPK1 的状态

TPK1 的数据规模为 404,137 条 unique sequences、3,591,326 条 labeled reads 和 6,903,397 条 unlabeled reads。它在相同 10×20 设置下运行至第 8 折的约 70% 时被安全停止，原因是系统可用内存降至约 2.1 GB，继续运行可能引发分页或影响系统稳定性。

TPK1 因此不计入作者级完成数，也没有生成可用于最终比较的 AUC。完整的中断日志保留在 `../results/multidataset_author_setting_remaining/TPK1.log`，末尾有 `Execution halted`；不能把此前的 3×5 预检值当作本次作者级结果。

## 当前作者级覆盖

已完成并与参考 AUC 精确一致的数据集为 DXS、LGK、HA、PyKS、Bgl3_LT、UBE2I、SUMO1 和 rocker，共 8 个。rocker 的作者级 10 折 × 20 候选值复现在单独目录 `../results/multidataset_author_setting_rocker/`；PyKS 保存在 `../results/multidataset_author_setting_extra/`；其余结果保存在 `multidataset_author_setting/` 和 `multidataset_high_setting/`；Bgl3_LT 使用作者专用的固定 `py1=0.35` 协议。

TPK1 是原始 UBE2I、SUMO1、TPK1 批次中唯一未完成的数据集，GB1 仍保留 5×10 高设置结果。此前未升级的 PyKS 已完成独立的 10×20 作者级任务，校正 AUC 为 `0.849753278800652`，作者参考值相同，差值为 `-3.33×10⁻¹⁶`；选定 `py=0.03652259`，PU AUC 为 `0.836979382800671`。结果文件位于 `../results/multidataset_author_setting_extra/PyKS_metrics.csv`，运行日志和完整 RDS 输出保留在同目录。

PyKS 批次命令为：

```powershell
Rscript reproduction/run_multidataset.R PyKS reproduction/results/multidataset_author_setting_extra 10 20 2
```

十个数据集目前已有 8 个完成作者级或作者专用协议复现：DXS、LGK、HA、PyKS、UBE2I、SUMO1、rocker 和 Bgl3_LT；TPK1 因内存边界停止，GB1 目前为 5×10 高设置，尚未完成 10×20 作者级复现。

## 解释边界

这批结果支持的结论是：在 UBE2I 和 SUMO1 上，按作者通用脚本的 10 折 × 20 候选 `py` 设置，当前实现可以复现作者报告的校正 ROC/AUC；它不支持“所有十个数据集都已完成作者级复现”，也不支持对 TPK1 的作者级 AUC 作出结论。
