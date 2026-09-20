# PU learning 论文复现

目标论文：

Song et al., *Inferring protein sequence-function relationships with large-scale positive-unlabeled learning*, Cell Systems (2021).

上游材料：

- `pudms-upstream/`：作者发布的 PUlasso 分析包；
- `pu-learning-paper-analysis-upstream/`：作者发布的论文分析仓库；
- `run_author_example.R`：调用作者自带 Rocker 示例的复现脚本；
- `run_multidataset.R`：调用作者 `v.pudms` 在论文整理后的数据文件上运行多数据集 PU ROC/AUC；
- `run_enrichment_baseline.R`：重跑作者 enrichment-score baseline 对照；
- `aggregate_multidataset.R`：跨批次合并各数据集指标；
- `make_summary_plots.R`：生成 AUC 对照图和 enrichment 差值图；
- `results/author_example/`：运行日志和输出结果；
- `results/multidataset/`：十个数据集的 3×5/5×10 预检结果；
- `results/multidataset_high_setting/`：PyKS 5×10 结果，以及正在推进的 GB1/Bgl3_LT 高设置结果；
- `results/enrichment/`：DXS 和 LGK 的 10×10、10 次重复 baseline 对照；
- `reports/`：复现说明与结果解释。

## 当前边界

当前已经覆盖作者分析仓库中的十个数据集：DXS、GB1、PyKS、UBE2I、Bgl3_LT、SUMO1、TPK1、LGK、HA，以及单独的 rocker 示例。DXS、LGK、HA 使用了 5×10 设置；PyKS 已完成 5×10 复核；其余部分先完成 3×5 预检。GB1 和 Bgl3_LT 的 5×10 高设置正在单独运行，因为低设置与作者参考 AUC 的差异较大。

enrichment baseline 已在 DXS 和 LGK 上按作者的 10 次重复、10 折设置完成。作者仓库的原始 `res_comp.Rdata` 受 Git LFS 服务不可用影响，不能直接读取；本地结果因此区分“作者提交的 CSV 汇总”和“本地重新运行的结果”。
