# 分子胶降解剂中的叙述性阴性证据与可用基准

检索日期：2026-10-26

## 先说结论

垂域是**靶向蛋白降解中的分子胶降解剂**（molecular glue degraders，MGDs）。在这个垂域里，论文中确实能找到有价值的失败或边界结果，例如“被招募但没有发生降解”“类似物未促进复合物形成”“某些结构改动削弱活性”。

但“用大模型从分子胶论文抽取实验记录”已经有非常接近的先行工作。当前仍可区分的具体问题是：**能否专门、可靠地恢复正文叙述里不以标准 DC₅₀/Dmax 数值呈现的阴性降解证据，并把它与正确分子、靶标、实验条件和原文证据绑定；这些证据是否改善后续模型回答。** 这只是一个仍需验证的差别，不能直接当作已成立的新颖性。

## 直接相关论文与资源

### 1. 大模型提取 TPD 论文数据：最接近的先行工作

[Beyond Manual Curation: Augmenting Targeted Protein Degradation Databases via Agentic Literature Extraction Workflows（Rao et al., 2026，预印本）](https://arxiv.org/abs/2605.11221)直接处理分子胶和 PROTAC 文献，抽取分子、降解靶标、招募蛋白、实验类型、细胞系、DC₅₀、Dmax 等字段。作者用7篇分子胶论文建立专家标注集，报告记录级 F₁ 约0.98；对70篇可处理的分子胶论文运行后，数据库记录数由136增加到246，新增记录抽样复核有效率为92%。代码、提示词、专家标注和抽取结果已公开在[项目仓库](https://github.com/yaochenr/LLM-TPD-Extraction)。

这项工作已经覆盖“跨论文定位记录、恢复条件、用专家标注评价抽取”这条大路线，必须作为主要对照。它的提取目标明确集中于 DC₅₀ 和 Dmax 等定量降解实验记录；基线还排除了 DC₅₀ 与 Dmax 都没有的记录。论文提到弱活性或非活性例子可能被数据库低估，但没有把**定性叙述性阴性**作为单独标签、独立召回目标或专门误差类型来评估。因此，它明显压缩了“做一个分子胶文献提取管线”的新意空间，却没有直接回答“专门找回叙述性阴性证据能否做得可靠、对模型是否有增量”。

### 2. 论文中确有“招募发生、降解没有发生”的结果

[Unveiling the hidden interactome of CRBN molecular glues with chemoproteomics（2024）](https://pmc.ncbi.nlm.nih.gov/articles/PMC11419069/)报告了被 IMiD 类分子招募到 CRBN、但没有观察到相应降解的靶标。论文特别讨论 ASS1 和 ZBED3：它们可被化学蛋白质组实验检出为 CRBN 招募对象，但在最高至5 μM的 pomalidomide 条件下仍没有已报告的降解证据。这个例子说明，分子胶阴性不一定是“分子完全无活性”；也可能是“形成招募/结合，却未形成有效降解”。提取时必须保留实验终点，不能把“未降解”简化成“无活性”。

### 3. 类似物失败和结构边界也散见于正文

[Design principles for cyclin K molecular glue degraders（Kozicka et al., 2024）](https://doi.org/10.1038/s41589-023-01409-z)系统研究91个候选分子。论文比较了不同类似物对 CDK12–DDB1 复合物形成和 cyclin K 降解的影响；例如 SNS-032 被作为不具备增益型分子胶活性的反例，部分结构改动也会降低招募或活性。这类结果比“化合物整体无效”更细：同一骨架上的改动可能保留靶标结合，却失去招募或降解能力。论文还结合图表、定量测定和结构分析，因此适合用来构造“正文叙述＋图表/补充材料上下文”核查样本。

## 与阴性数据有关的现有数据库

[MolGlueDB](https://doi.org/10.1093/nar/gkaf811) 汇集了分子胶文献和实验数据，也纳入“实验评估后未显示预期降解活性”的 inactive MGD candidates。它们是已经被整理的候选阴性，不能算作我们要恢复的“正文中一带而过、缺少结构化记录的叙述性阴性”；但它说明不能笼统声称“分子胶领域没有阴性数据或 inactive 记录”。

[MGDB](https://doi.org/10.1093/nar/gkaf1131) 是另一项分子胶资源，汇集分子、靶标、效应蛋白和多类生物活性记录。它可以用来查重和核对已知分子/结果，但不是专门针对叙述性阴性恢复的 benchmark。

## 可用 benchmark：分别适用于什么问题

| 基准/资源 | 实际评测对象 | 对本项目的用途 | 不能据此声称什么 |
| --- | --- | --- | --- |
| [LLM-TPD-Extraction 专家标注集](https://github.com/yaochenr/LLM-TPD-Extraction) | 从论文和补充材料恢复定量降解 assay records；分子胶部分有7篇专家标注论文 | 最接近的**提取准确率对照**；可先复现其记录匹配与字段评分，再单列定性叙述性阴性子集 | 不能直接代表定性阴性召回率；其 F₁ 不能直接证明我们特定任务已解决 |
| [MG2Act 数据与模型](https://github.com/Zzy522/MG2Act) / [论文预印本](https://doi.org/10.64898/2026.08.08.739980) | CRBN 介导的分子胶降解活性预测；论文报告连续值数据集含1,207个分子–靶标配对、47个靶标 | 若后续做**分子胶活性预测**，可作领域内下游建模参照；应检查数据许可、字段、训练/测试拆分后再决定能否直接使用 | 不是文献抽取 benchmark，也不是 RAG/语言模型问答 benchmark；现有任务不等同于“把阴性证据加入训练后是否更会谨慎回答” |
| [MG-PDB / MGBench](https://github.com/yiyanliao/MGBench) | 分子胶介导的三元蛋白复合物结构；数据集收录221个复合物，MGBench采用88个结构评估共折叠预测 | 只有研究问题变成**三元复合物结构预测**时才适用 | 不评估阴性证据抽取、降解活性分类或语言模型使用效果 |
| [MolGlueDB](https://doi.org/10.1093/nar/gkaf811)、[MGDB](https://doi.org/10.1093/nar/gkaf1131) | 已整理的分子胶及实验/活性记录 | 用于来源查重、已知记录核对和确定哪些记录不是新增 | 它们是数据库，不是独立的阴性抽取或模型用途 benchmark |

## 对我们这条线的判断

1. **提取阶段不能再把目标写成“建立分子胶文献提取 pipeline”。** 这已被 LLM-TPD-Extraction 明确覆盖。更窄且可检验的问题是：该系统及现有数据库对非结构化定性阴性是否漏检、漏在哪些表达和终点上。
2. **最接近的已有提取基准是 LLM-TPD-Extraction 的7篇分子胶专家标注集，但不足以单独评估我们的核心问题。** 应从中筛出真正以正文/表格叙述表达、且有实验支持的失败结果；再补充少量新论文，按论文留出，人工核查对象、终点、条件、证据原句和不确定性。
3. **模型用途需要另设 benchmark。** MG2Act 能测试特定活性预测任务，却不能直接评估 RAG 或小语言模型对文献失败证据的使用。若目标是 RAG，应使用独立留出的论文问题，比较不检索、检索原文、检索结构化阴性证据三种条件，并核查引文与是否把“未测/未显著”说成阴性。若目标是小模型训练，则需要先固定同一任务和独立测试集，再与不加入这些证据的模型对照。

## 参考链接

- Rao et al., 2026, 预印本与数据/代码：[论文](https://arxiv.org/abs/2605.11221) · [仓库](https://github.com/yaochenr/LLM-TPD-Extraction)
- Kozicka et al., 2024, *Nature Chemical Biology*：[论文](https://doi.org/10.1038/s41589-023-01409-z)
- 2024, *Unveiling the hidden interactome of CRBN molecular glues with chemoproteomics*：[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC11419069/)
- Wang et al., 2026, *MolGlueDB*：[论文](https://doi.org/10.1093/nar/gkaf811)
- Li et al., 2025/2026, *MGDB*：[论文](https://doi.org/10.1093/nar/gkaf1131)
- Zhuang et al., 2026, *MG2Act*：[预印本](https://doi.org/10.64898/2026.08.08.739980) · [代码与数据](https://github.com/Zzy522/MG2Act)
- Liao et al., 2025, *MGBench*：[论文](https://doi.org/10.1021/acs.jcim.5c01860) · [代码与数据](https://github.com/yiyanliao/MGBench)
