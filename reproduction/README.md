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
- `results/multidataset_high_setting/`：PyKS、GB1、Bgl3_LT 的 5×10 高设置结果；
- `results/enrichment/`：DXS 和 LGK 的 10×10、10 次重复 baseline 对照；
- `reports/`：复现说明与结果解释。

## 当前边界

当前已经覆盖作者分析仓库中的十个数据集：DXS、GB1、PyKS、UBE2I、Bgl3_LT、SUMO1、TPK1、LGK、HA，以及单独的 rocker 示例。DXS、LGK、HA、PyKS、GB1 和 Bgl3_LT 已完成 5×10 设置；SUMO1、TPK1、UBE2I 保留 3×5 预检结果。GB1 在高设置下接近作者参考 AUC。Bgl3_LT 的通用自动选参结果曾明显偏低，但按作者专用脚本固定 `py1=0.35`、10 折、1 个超参数严格重跑后，AUC 与作者参考值完全一致；因此此前偏差已定位为协议不一致，而不是当前实现链路无法复现。

enrichment baseline 已在 DXS 和 LGK 上按作者的 10 次重复、10 折设置完成。作者仓库的原始 `res_comp.Rdata` 受 Git LFS 服务不可用影响，不能直接读取；本地结果因此区分“作者提交的 CSV 汇总”和“本地重新运行的结果”。
