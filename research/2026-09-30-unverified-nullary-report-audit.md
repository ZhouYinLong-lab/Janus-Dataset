# 未认证灰色文献线索：Nullary 2026 measured-negative 技术报告

**核查日期：** 2026-09-30  
**状态：** 来源认证未完成；不作为同行评审先例或已验证模型结果引用。  
**主题关联度：** 3/3（分子生物活性测量阴性及模型效用），但当前证据确定性低。  
**报告页面：** [Nullary research page](https://nullary.ai/research)；[自托管PDF](https://nullary.ai/research/nullary-negative-results-validation-2026-05.pdf)。

## 为什么要记录

网页与自托管PDF声称 Nullary 团队建立了约1.22亿条多模态阴性发现数据层，并用ChEMBL35激酶数据比较实测inactive与构造decoy的模型效果。这与“阴性数据价值、资源整合、模型验证”高度相关，不能忽略。但网页将报告描述为团队technical report，而非同行评审期刊论文；页面列出的Zenodo DOI `10.5281/zenodo.20370264` 在本次核查时无法解析。

## 来源认证检查

| 检查项 | 结果 |
|---|---|
| Nullary研究页面 | 页面存在，列出Technical Report 1及下载链接 |
| 自托管报告PDF | 下载成功；8页；PDF可读 |
| DOI解析 | `https://doi.org/10.5281/zenodo.20370264` 返回404 |
| DataCite记录API | `https://api.datacite.org/dois/10.5281/zenodo.20370264` 返回404 |
| Zenodo记录API | `https://zenodo.org/api/records/20370264` 返回404 |
| 独立索引/同行评审来源 | 精确题名检索未找到独立出版记录；目前唯一完整报告来源为Nullary自有页面/PDF |
| 底层negative数据与补充表 | 未访问；报告中的数值尚未独立重算 |

这只能说明其所报DOI在本次检查时无效/不可用，**不能据此断言报告或团队造假**。仍可能是DOI录入错误、注册延迟或未发布版本；在得到可解析的稳定存档或数据源之前，证据应保持“未认证”。

## 报告自述的内容（仅作待核验摘要）

- 自称总层包含122,276,636条跨模态negative findings；报告同时说明其中约3,910万条小分子finding兼具结构与UniProt靶点，25激酶示范仅使用约148,851个compound–target pairs。
- 从ChEMBL35选择人源单蛋白kinase/GPCR assay： potency ≤1 µM记active，≥10 µM（或inactive comment）记inactive；1–10 µM中间带剔除，活性/阴性冲突pair也剔除。
- 模型为每靶点ECFP4 + LightGBM。报告自述：25个kinase的scaffold split ROC-AUC中位数0.966；时间切分（训练≤2018、测试≥2020）降至0.775。
- 同架构和scaffold split下，将训练负类从实测inactive替换成1:1构造decoy，作者报告real-negative训练在25/25靶点方向上较好，中位AUC优势+0.031；但时间切分优势降到+0.014、17/25方向上较好。报告称这只是modest advantage。
- 报告承认AVE-debiasing尚未完成、数据finding未经人工逐条来源核验、校准指标有限、kinase/GPCR范围有限。它明确承认PIDGIN已有 per-target measured-inactive 建模先例，主张差异在大规模整合和报告 framing。

## 对Janus研究的实际影响

这条线索提示“测量inactive资源规模化聚合 + 与decoy比较 + 时间切分”可能正在被更晚的团队开展，但还不能作为已经认证的竞品论文或可靠数据集证据。即便报告内容属实，它处理的是ChEMBL等结构化/筛选记录的整合和模型使用，不是从论文正文、图表及补充材料中恢复定性阴性、删失边界、no-detect或失败原因。

因此它暂时不改变正式gap结论，只增加一项来源认证任务。不要仅凭“122M”宣传规模改写立项新颖性；后续需先验证DOI、报告版本、数据下载/API、原始来源字段、去重口径和人工核验基准，再决定是否正式纳入综述/文献矩阵。

## 统一追踪位置

- 总表：[`research_tracker.md`](research_tracker.md) T111
- 文献矩阵：[`literature_matrix.csv`](literature_matrix.csv) J062（明确标记source-unverified-gray-report）
- 搜索日志：[`search_log.csv`](search_log.csv) Q120
- 证据账本：[`evidence_ledger.md`](evidence_ledger.md) E093
- 下载的自托管PDF：[Nullary-2026-measured-negatives-validation-technical-report.pdf](sources/unverified-gray-literature/Nullary-2026-measured-negatives-validation-technical-report.pdf)
