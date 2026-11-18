# LpBgl5 文献阴性读数的可恢复性小样例

**日期：** 2026-09-30  
**关联度：** 3/3（直接检验蛋白–底物实测阴性如何在正文、表格和图中出现，以及上下文能否恢复）  
**定位：** 候选方法学阳性对照/便利样例，不是随机或代表性样本；不用于估计总体抽取精确率、召回率或新颖性。

## 来源与结果

Godse、Fernandes 与 Kulkarni 2025 年在 *Lactiplantibacillus plantarum* NCIM 2903 的10个候选 GH1 glycosyl hydrolase 中对可溶表达蛋白做了功能筛查，并对 LpBgl5 展开底物范围实验。研究的 lpbgl5 核苷酸 accession 为 PQ462659。[期刊全文](https://link.springer.com/article/10.1007/s00253-025-13472-8)，[PubMed PMID 40199767](https://pubmed.ncbi.nlm.nih.gov/40199767/)。

在同一论文内，可辨认出两种不同的“阴性”证据：

| 证据单元 | 负向结果 | 可恢复的主要实验语境 | 尚缺/须谨慎之处 |
|---|---|---|---|
| pNP 底物面板 | p-nitrophenyl-α-D-glucopyranoside 与 p-nitrophenyl-β-D-galactopyranoside：Table 1 相对活性为0，正文称未检测到活性 | 10 mM 底物、25 µg 酶、50 mM citrate-phosphate（pH 6）、40°C、1 h；A405；三重复；almond β-glucosidase 正对照、空载体 E. coli 蛋白负对照 | “0”是报告的相对活性/检测结果，不代表理论活性绝对为零；未给分析检测限；归一化参考底物为 pNP-β-D-glucopyranoside |
| 天然糖苷面板 | arbutin 与 cellobiose：96 h 未见水解 | 1 mM 底物、50 µg 酶、50 mM citrate-phosphate（pH 6）、40°C；TLC 时间点延伸至96 h；almond β-glucosidase 与空载体对照 | 定性 TLC 未水解，没有定量检测限；需保留“在该方法/时间内未见水解”，不能泛化成酶永久无活性 |

文章还报告 LpBgl5 对 pNP-xyloside 的相对活性为384%、对 pNP-mannoside 为82%，并能水解其他天然糖苷；因此这些阴性标签是底物特异的，不应把蛋白整体标为 inactive。详细字段逐条保存在 [`lpbgl5_negative_extraction.csv`](pilots/enzyme-negative-literature/lpbgl5_negative_extraction.csv)。

## 对方法可行性的含义

这是一个适合验证抽取 schema 的**容易样例**：明确蛋白/基因、底物、多个阴性结果、同一实验中的正负对照，以及足以重建主要 assay 条件的 Methods。它同时展示结构化表格的数值零与正文/图像支持的定性 no-hydrolysis 不是同一种标签。能从这种清楚的文章提取，不等于能解决分散、含糊或仅在补充材料中的文献；故不作为历史文献抽取已普遍可行的证明。

作者称研究数据可按合理请求向通讯作者索取；本次可从公开全文逐读 Table 1 与 Figure 3，但没有取得独立机器可读的原始重复数据或 TLC 原始量化值。因此这篇论文可支持“公开文章中可恢复研究者报告的阴性标签和部分语境”，不能支持独立复算原始活性。

## 可复现来源

- DOI：[10.1007/s00253-025-13472-8](https://doi.org/10.1007/s00253-025-13472-8)
- 期刊方法段：enzyme assay、substrate specificity、controls、triplicates，见[Springer全文](https://link.springer.com/article/10.1007/s00253-025-13472-8)
- 重跑/审核字段：[`lpbgl5_negative_extraction.csv`](pilots/enzyme-negative-literature/lpbgl5_negative_extraction.csv)

## 与主课题的边界

这篇文章不构成全新的负数据资源或模型收益证据，也不证明这些观察未被 ChEBI/BRENDA/其他酶库覆盖。它适合纳入后续跨论文 pilot，用作“表格数值零 vs 自然语言/图示未检出、语境完整度、正负对照”类别的已知案例；与 Q25BW5 的 BRENDA/NIMS source-trace case 合在一起，可形成少量但异质的抽取挑战集。下一步优先核其序列/引文在 BRENDA 的实体级可见性，再继续纳入困难案例，而不从此便利样例推算 prevalence。
