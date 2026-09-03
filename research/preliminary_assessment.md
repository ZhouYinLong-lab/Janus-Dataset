# 现阶段判断：阴性数据与 AI-ready 分子数据集

**版本：** 0.1  
**日期：** 2026-09-03  
**依据：** 第一轮主题检索、10 篇种子文献和证据台账

## 结论先行

这个问题已经有人做过，但还没有被一个统一、完整的方案解决。

已有研究分别处理了几类相邻问题：有人整理实验上测得的 inactive 化合物，有人研究分子数据集和 benchmark 的偏差，有人利用失败实验训练模型，也有人研究从化学文献中抽取结构化信息。更早的工作已经把大规模 presumed-inactive bioactivity 数据用于靶点预测，近年的资源也开始保存完整筛选流程中的正负结果。

因此，不能再把课题简单表述为“构建一个阴性分子数据库”。这个方向已经存在直接先例。更有价值、也更可能形成差异的切入点，是研究如何把不同类型的阴性证据以可追溯、带实验上下文、带不确定性的形式组织起来，并验证它们是否真正改善分子机器学习在真实场景中的可靠性。

## 一、是否已经有人完成过？

如果问题是“有没有人意识到阴性数据、失败实验和 inactive 样本有价值”，答案是肯定的。

如果问题是“有没有人做过一个覆盖所有分子科学领域的、能够从文献中系统找回阴性证据、保留完整上下文，并证明其能改善模型的统一数据集和方法”，截至目前这轮检索，尚未发现成熟的完整方案。

这个判断不是“没有人做过”的绝对断言，而是基于当前检索范围的阶段性结论。已有工作更多是分散在不同任务和数据类型中，彼此之间还没有形成完全一致的定义、数据模式和评价标准。

## 二、已有工作做到什么程度？

### 1. 阴性或 inactive 数据已经存在，而且并非最近才出现

ChEMBL、PubChem BioAssay 以及一些虚拟筛选 benchmark 中都包含 inactive 或 non-binding 记录。已有工作也会根据活性阈值整理 positive / inactive 样本，并使用 scaffold、结构或时间切分来减少化学相似性造成的数据泄漏。

早在 2015 年，Mervin 等人就把 ChEMBL 和 PubChem 中的大规模 bioactivity 数据用于构建包含 presumed-inactive 数据的靶点预测模型，并与只使用 active 数据的模型进行了比较。[Target prediction utilising negative bioactivity data covering large chemical space](https://doi.org/10.1186/s13321-015-0098-y)

2025 年的 [ECBD](https://doi.org/10.1093/nar/gkae904) 则从数据基础设施角度保存 EU-OPENSCREEN 项目中的正负 activity data，包括 primary assay 和 counter-screening assay。

这说明“数据库里完全没有阴性数据”以及“以前没人把阴性数据用于模型”都不准确。更准确的问题是：这些数据是否足够完整、是否代表真实实验空间、是否保留了决定标签含义的 assay 和实验条件，以及不同来源的阴性证据能否被统一比较。

### 2. 数据集偏差已经被多次证明

针对 DUD-E 等 benchmark 的研究发现，模型的高分有时来自 decoy 或化学结构偏差，而不一定来自真正的分子识别能力。[Chen 等人的研究](https://doi.org/10.1371/journal.pone.0220113) 是这方面的代表性工作。

[CARA benchmark](https://doi.org/10.1038/s42004-024-01204-4) 进一步把 ChEMBL 活性数据按 assay、靶点、测量类型和实验条件组织起来，指出真实数据具有稀疏、异质、测量分布不同和任务场景不同等特征。它说明同一个“active / inactive”标签，脱离 assay 上下文后很容易被过度简化。

此外，[Coverage bias in small molecule machine learning](https://doi.org/10.1038/s41467-024-55462-w) 说明常用分子数据集还可能覆盖不到部分已知化学结构空间。也就是说，数据质量问题不只是正负样本比例问题，还包括化学空间和任务空间的代表性问题。

### 3. 失败实验已经被用于机器学习发现

[Raccuglia 等人在 Nature 的研究](https://doi.org/10.1038/nature17439) 使用实验室历史记录中的失败水热合成反应训练模型，并将模型用于新的材料合成条件选择。该研究保留了 3,955 条完整反应记录，并报告了针对新实验的较高成功率。

这项工作证明失败结果可能包含重要的边界信息，但它研究的是材料合成反应，数据来自实验室记录，并不是从公开分子论文中自动挖掘负面结果。因此，它是重要先例，但不能直接替代我们要研究的问题。

### 4. 已经出现直接的 inactive compound 资源

[InertDB](https://pmc.ncbi.nlm.nih.gov/articles/PMC11983867/) 是目前必须重点比较的工作。它从 PubChem 相关记录中整理生物惰性小分子，并进一步使用生成式方法扩展 inactive compound 空间，同时测试其对下游模型的影响。

它直接说明“构建一个阴性分子资源”本身已经有人做过。因此，Janus 如果继续推进，不能只在数量上重新收集 inactive 化合物，也不能把生成出来的分子和真实实验阴性观测混为一谈。

此外，2015 年的 [Mervin 等人研究](https://doi.org/10.1186/s13321-015-0098-y) 已经报告了将 presumed-inactive 数据纳入大规模靶点预测的效果；2019 年的 [Lee 等人研究](https://www.repository.cam.ac.uk/items/2a26b764-7e66-4db3-b5d0-2e41192c33c3) 还将 high-quality negative data 用于分析 active-negative chemical correlations。由此看，Janus 的新意不能停留在“把阴性样本加入模型”。

### 5. 化学文献抽取技术已经比较活跃

化学实体识别、结构识别、表格抽取和性质抽取已经有较长积累。近期的综述指出，LLM 可以加快化学数据抽取，但抽取系统仍然需要明确的 ground truth、人工核验、错误类型分析和领域约束。[From text to insight](https://doi.org/10.1039/D4CS00913D)

目前的不足不在于“能不能从论文中抽一句话”，而在于能否正确完成以下关联，并与已有结构化负面数据互相校验：

```text
化合物 — 任务/性质 — 靶点或体系 — assay/条件 — 观察结果 — 证据位置
```

尤其是 qualitative negative、relative decrease、failed experiment 和 ambiguous outcome，不能简单压缩成一个 0 标签。

## 三、已有研究取得了什么成果？

已有成果可以概括为四点：

1. 证明实验失败和 inactive 结果具有信息价值，而不只是“无用数据”；
2. 证明分子 benchmark 可能存在 decoy、scaffold、采样和覆盖偏差；
3. 建立了若干可用的 inactive 数据资源和现实场景评价 benchmark；
4. 形成了从化学文献中抽取结构和实验性质的技术基础。

但这些成果主要分别解决单点问题：

- 有的数据集有 inactive，但没有完整 provenance；
- 有的 benchmark 考虑了现实分布，但没有从文献中挖掘遗漏证据；
- 有的工作利用了失败实验，但数据来自内部实验记录；
- 有的抽取方法能识别化学信息，但没有专门围绕阴性证据建立评价集；
- 有的模型显示加入负样本有效，但未必证明这些样本代表真实未观测空间。

## 四、真正没有被充分解决的部分

目前最值得继续追查的空白，不是“有没有 negative data”，而是以下几个问题之间还缺少连接：

### 1. 阴性证据缺少统一的观察层定义

现有工作经常把 inactive、decoy、未命中、失败、低性能和 unknown 放在同一个 negative 类别中。它们在科学含义和可用于模型的方式上并不相同。

### 2. 文献中的阴性信息缺少专门的数据集和金标准

文献抽取研究很多，但专门针对分子 negative / failed evidence 的公开、人工核验语料和评价基准仍需要重点查证。

### 3. 数据补充和模型收益之间缺少严格验证

很多研究证明了数据集或模型可以工作，但还需要区分：

- 增加了更多样本；
- 增加了更多 inactive 样本；
- 增加了更接近真实分布的负面证据；
- 增加了带 assay 上下文和 provenance 的观测。

这几件事不能混为一谈。

### 4. publication bias 仍不能直接当作既定事实

现阶段可以较谨慎地讨论 reporting bias、curation bias 和 selection bias，但不能仅凭公开数据库中阳性结果较多，就直接证明所有失败实验都没有发表。这个因果链需要更专门的证据。

## 五、Janus 还有没有必要做？

有必要，但需要改写研究目标。

不建议的表述是：

> 我们要构建一个包含更多阴性分子的数据库。

更稳妥的表述是：

> 我们研究分子数据中不同类型阴性证据的表示、来源和缺失问题，建立一个保留实验上下文与证据出处的 negative observation 数据集，并检验它是否能改善模型在 assay-level、scaffold-level 或 temporal split 下的可靠性。

其中最重要的设计原则是：

- `unknown` 不等于 `negative`；
- 真实实验 inactive 不等于生成 decoy；
- 定性结果不强行转成精确数值；
- 相对变差可以作为 pairwise 或 ordinal evidence；
- 每条记录保留 DOI、原文片段、表格或页码等证据位置；
- 标签必须带有实验条件、测量类型和置信度。

## 六、现阶段的最终判断

可以把当前结论压缩为一句话：

> 阴性数据、失败实验、分子数据偏差和化学文献抽取都已经有先行研究；大规模 presumed-inactive 建模、完整筛选流程中的正负数据保存，以及专门的 inactive compound 资源也已经出现。但是，面向分子科学的、以观察为单位、区分 unknown 与 negative、保留实验上下文和证据出处，并用真实任务验证数据价值的完整方案，仍然没有被充分解决。

因此，Janus 不应再以“发现阴性数据的重要性”作为主要贡献，而应把贡献集中到“证据驱动的阴性观察表示与评价”上。下一轮查重需要重点确认这个交叉空白是否真实存在，以及是否已经有工作完成了其中的关键环节。

## 参考工作

- [Machine-learning-assisted materials discovery using failed experiments](https://doi.org/10.1038/nature17439)
- [Hidden bias in the DUD-E dataset](https://doi.org/10.1371/journal.pone.0220113)
- [DEEPScreen](https://doi.org/10.1039/C9SC03414E)
- [Chemical property prediction under experimental biases](https://doi.org/10.1038/s41598-022-12116-5)
- [Benchmarking compound activity prediction for real-world drug discovery applications](https://doi.org/10.1038/s42004-024-01204-4)
- [InertDB](https://pmc.ncbi.nlm.nih.gov/articles/PMC11983867/)
- [Coverage bias in small molecule machine learning](https://doi.org/10.1038/s41467-024-55462-w)
- [From text to insight: large language models for chemical data extraction](https://doi.org/10.1039/D4CS00913D)
