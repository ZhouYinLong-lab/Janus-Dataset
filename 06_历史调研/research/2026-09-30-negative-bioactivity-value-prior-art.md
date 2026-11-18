# 分子靶点预测中加入阴性生物活性数据的直接先例

**核查日期：** 2026-09-30  
**核心来源：** Mervin et al., *Target prediction utilising negative bioactivity data covering large chemical space*, *Journal of Cheminformatics* 7, 51 (2015), [DOI](https://doi.org/10.1186/s13321-015-0098-y)、[全文](https://link.springer.com/article/10.1186/s13321-015-0098-y)、[PubMed](https://pubmed.ncbi.nlm.nih.gov/26500705/)。  
**主课题关联：** 3/3；直接处理分子生物活性负类及其模型效用。  
**证据边界：** 论文同行评审且原文可读；下述结果是作者报告，本轮未独立重跑其全量 benchmark。

## 这篇论文实际做了什么

作者构建 PIDGIN 靶点预测流程：从 ChEMBL 18 获取活性数据，从 PubChem BioAssay 提取提交者标注为 inactive 的 assay 结果；对于 inactive 太少的 target class，又从 ChEMBL 化合物中按球排斥（sphere exclusion）挑选与已知 active 足够不同的结构，补入“presumed inactive”。论文报告整个 benchmark 为 206,559,765 个 ligand-target pairs、1,080 个 target-class 模型，并为稀疏类别额外采样约 1,100 万条 presumed-inactive 记录。模型为 Bernoulli Naive Bayes，输入 2048-bit ECFP4。

模型评估包括五折分层交叉验证，以及 WOMBAT 2011.1 外部集。WOMBAT 留出集为 65,123 个活性分子、418 个 target class；与 ChEMBL/PubChem 训练集结构完全相同的 3,624 个记录被移除。论文明确承认 WOMBAT 没有实验确认的 inactive：目标没有记录的 compound-target pair 被当作 inactive，因此真正未测试、未报道的 pair 可能被错标为阴性。

## 作者报告的“加负类”结果

| 比较 | 作者报告 | 可以说明什么 |
|---|---:|---|
| Negative-inclusive vs active-only，外部 WOMBAT 平均 PR-AUC | 0.56 vs 0.45 | 该研究的完整负类方案在其外部评估设定下排序表现更好 |
| 同一比较，BEDROC | 0.85 vs 0.76 | 该方案在早期富集指标上更好 |
| 对 PR-AUC / BEDROC 的 Wilcoxon signed-rank test | p=4.96×10⁻⁵ / 7.08×10⁻⁸ | 论文报告 target 级配对差异具有统计显著性 |
| 有至少 1,000 个已确认 inactive、仍加入额外 sphere-exclusion 样本的 20 个目标 | WOMBAT precision 在 19/20 个目标提高 | 在该局部对照中，额外加入的是结构上与 active 不相似的 presumed negatives，不是新增实验 inactive |

## 批判性解释：它证明了什么、没有证明什么

**它确实关闭了一个宽泛研究主张：**“分子靶点预测从未把 inactive 数据加入模型”或“没有人比较过负类对模型的价值”都不成立。2015 年这项工作已明确将负类与仅活性训练的方案比较，报告了外部 PR-AUC、BEDROC 和显著性检验结果。

**但它没有隔离实测阴性的独立因果贡献：**

1. negative-inclusive 训练数据混合了 PubChem BioAssay 的 assay outcome inactive 和 ChEMBL sphere-exclusion 选择的结构远离 active 的 presumed inactive；后者约 1,100 万条，不能称作实测阴性。
2. active-only 对照用的是 ChEMBL 活性数据，而 negative-inclusive 方案另含 PubChem 负类和额外 presumed negatives。训练数据规模、覆盖度、来源和类别组成并未按“只改变标签是否为实测阴性”的原则严格匹配。
3. WOMBAT 外部评估不含实验确认的 inactive，未被标注的 pair 被视作阴性；所以负类模型的所谓假阳性/真阴性可能受评测端缺失标签影响。作者也承认外部 precision 受这项假设影响。
4. 内部表现与 target 类别大小、活性类内相似度、负类抽样策略明显相关；作者指出有些过高指标来自 sphere-exclusion 要求负例与正例足够不相似。它不能直接外推到 scaffold/OOD 泛化或校准。

因此，最稳妥的结论是：**一套同时包含实验 inactive 与结构推定 inactive 的负类方案，在该靶点预测研究中优于其 active-only 比较方案；实测 inactive 是否独立产生该收益仍未被识别。**

## 对 Janus 主课题的影响

- 不把“把阴性类别加进分子模型”作为创新点。
- 把待检验问题收窄为：在 assay、样本量、类比例、结构相似度和训练/测试划分匹配时，实验确认 inactive、删失边界、文献恢复的明确阴性、PU 未标注和结构推定负例分别能带来什么收益？
- 先做低成本模型（如 ECFP + logistic regression / random forest / BernoulliNB）消融，不需要大显卡；把 GPU 留给确有必要的复杂表示。
- 指标优先考虑 PR-AUC、早期富集、校准及按 assay/scaffold/time 的分层结果；不能只报总体 accuracy。
- 需区分加入负类的“任务可学性/排序收益”和增加样本量、化学空间覆盖、类别平衡所带来的收益。

## 仍需后续核查

1. 获取或复原 PIDGIN 的 benchmark 与模型流程，核对 2015 论文所称 paired comparison 的 exact train/test 数据构成及统计单位。
2. 对可公开 assay 做小型 matched ablation：同一 active 集、同一测试集、相同负例数和类比例，分别替换 measured inactive、sphere-exclusion、random unlabeled/decoy；至少做 scaffold split 与时间或 assay 外推。
3. 对测试端优先使用完整筛选 assay 的已测 inactive，而非把未测试对象自动补成阴性。

## 可引用来源

- [Mervin et al. 2015, Journal of Cheminformatics](https://doi.org/10.1186/s13321-015-0098-y)
- [论文全文（含 methods/results）](https://link.springer.com/article/10.1186/s13321-015-0098-y)
- [作者代码 PIDGIN](https://github.com/lhm30/PIDGIN)
- 本地全文：[Mervin_2015_negative_bioactivity.pdf](value_assessment/03_model_utility/papers/Mervin_2015_negative_bioactivity.pdf)
