# 小分子生物活性阴性数据：偏倚、证据恢复与机器学习价值

**文献类型：** 初步范围综述  
**版本：** 0.1  
**检索更新：** 2026-09-06  
**当前范围：** 小分子化合物与蛋白靶点的生物活性数据

## 摘要

公开分子数据并不等于实验世界的完整记录。研究者通常更关注活性化合物，数据库还会受到发表、报告、筛选流程、人工阈值和后续整理方式的共同影响。由此形成的问题不只是正负样本数量失衡，还包括哪些分子被测试、实验条件是否保留、未达到阈值的结果是否进入数据库，以及模型是否在利用数据集的构造规律而非可迁移的化学规律。

本轮检索显示，相关工作已经形成四条较成熟的路线。第一，PubChem、ChEMBL、LIT-PCBA、ECBD 等资源包含实测 inactive 或完整筛选结果。第二，Mervin 等人的工作、InertDB 及反应预测研究已经检验阴性数据的模型价值。第三，DUD-E、CARA 和覆盖偏倚研究证明人工负例、数据切分和化学空间覆盖会显著影响模型评价。第四，BioMiner 在 2026 年建立了包含 16,457 条记录的文献生物活性抽取基准 BioVista，并将自动抽取的数据用于预训练和 QSAR 模型。

因此，课题不能再以“首次收集阴性分子”或“首次从论文中抽取活性数据”为主要贡献。当前仍未被充分解决的交叉问题，是如何专门识别不同科学含义的阴性证据，区分 unknown 与 negative，保留 assay、阈值、比较符和出处，并用严格的消融实验证明这些信息相对普通活性数据带来的增量价值。这个方向仍可能形成论文，但前提是先在一个窄领域完成可行性验证，而不是直接声称覆盖全部分子科学。

## 1. 研究问题

这项调研要回答四个递进问题：

1. 分子生物活性数据是否存在偏向阳性结果、忽略低活性或失败结果的现象？
2. 阴性信息能否从数据库、论文正文、表格和补充材料中可靠恢复？
3. 加入这些信息是否改善模型，而不是仅仅增加样本数量或改变类别比例？
4. 如果相邻工作已经存在，新的数据集和方法应在哪个环节做得更好？

这里的“阴性数据”不是一个天然统一的类别。本报告把研究对象称为“阴性观察”，即某个化合物在明确的靶点、实验体系和判断标准下表现为不活跃、低于要求、没有改善或实验未成功的一条观察记录。

## 2. 范围与方法

### 2.1 范围

第一阶段聚焦小分子与蛋白靶点的生物活性，优先考虑 IC50、Ki、Kd、抑制率和 active/inactive 判定。材料合成、化学反应、毒理学和临床研究只作为方法或概念上的旁证。

这个范围具备三个实际优势：

- PubChem BioAssay 和 ChEMBL 已提供可核对的结构化记录；
- 激酶筛选等任务存在完整实验矩阵，可用于区分低活性与未测试；
- CARA、LIT-PCBA 等基准可支持 assay、骨架和真实任务场景下的评价。

### 2.2 检索方式

本轮使用“问题是否存在、阴性如何定义、数据集偏倚、文献抽取、弱监督、模型影响”六组检索式，并通过 DOI、PubMed、Europe PMC、出版社页面和论文全文核对核心主张。核心阅读路线保留 11 篇论文，本次更新增加 BioMiner 作为直接的新颖性检查。

这仍属于范围检索。它能回答“主要路线做到哪里”，但不能量化全部文献中的阴性结果遗漏率，也不能证明世界范围内不存在同类工作。

### 2.3 证据强度

- **直接证据：** 论文发布数据、执行对照实验或报告可核对结果。
- **方法证据：** 方法能用于抽取或评价，但没有直接回答阴性证据问题。
- **背景证据：** 综述或框架帮助定义问题，不能单独支撑效果主张。

## 3. 阴性数据的类型必须先拆开

| 类型 | 含义 | 可否直接作为负标签 | 必须保留的信息 |
| --- | --- | --- | --- |
| 实测 inactive | 在一次 assay 中未达到预设活性标准 | 可以，但只对该 assay 成立 | 靶点、实验类型、阈值、浓度、判定规则 |
| 截断值 | 例如 IC50 > 10 μM | 可用于区间或有序标签，不宜伪装成精确值 | 比较符、数值、单位、检测上限 |
| 定性无效 | 正文写明 inactive、no effect 或 weak | 可作为弱标签，需要人工校验 | 原句、指代对象、实验上下文、置信度 |
| 相对变差 | B 比 A 活性低，未必绝对无活性 | 适合成对排序，不宜直接记为 0 | 比较对象、方向、实验条件 |
| 实验失败 | 合成、测量或研究目标未成功 | 取决于任务，不能自动等同 inactive | 失败环节、原因、是否完成测量 |
| 推定阴性 | 未知相互作用按规则抽样为负例 | 只能作为带噪声训练信号 | 构造规则和不确定性 |
| 人工 decoy | 为 benchmark 生成的对照分子 | 不能当作实测阴性 | 生成方法和匹配约束 |
| unknown / untested | 没有观测或没有测试 | 不能 | 缺失原因和数据来源 |

这个分类是整个方向的核心。若把这些记录压成同一个 0，数据量会增加，但科学含义和可解释性会下降。

## 4. 已有工作完成到了什么程度

### 4.1 偏倚和模型评价问题已经得到较强支持

Smajić 等人比较公开与企业内部安全药理数据，发现不同来源的数据组成会影响模型预测倾向。它支持“公开数据的类别分布可能偏斜”，但不能单独把差异全部归因于发表偏倚。

Chen 等人对 DUD-E 的分析表明，模型可以利用 decoy 和配体拓扑偏差得到看似优秀的虚拟筛选结果。这个结果直接否定了“只要负例足够多，模型评价就可靠”的简单推断。

CARA 将 ChEMBL 数据按 assay、测量类型和任务场景组织，并使用 per-assay 评价。作者发现不同 assay 上的模型表现差异较大，整体汇总指标会掩盖失败任务。2026 年关于严格数据切分的研究还显示，当测试分子逐渐远离训练分布时，多类模型的性能明显下降，简单近邻方法可与复杂模型相当。

这些研究共同支持三点：公开数据有选择性；负例构造会引入捷径；模型收益必须在更严格的分布外场景中检验。它们尚未直接测量“论文中有多少阴性结果没有发表”。

### 4.2 明确的阴性记录已经可以找到

PubChem BioAssay 要求提交者给出 active、inactive 等活性结论，并保留 assay 记录。LIT-PCBA 从 PubChem 实测筛选数据构造活性与非活性基准，避免将纯人工 decoy 当成实验阴性。PKIS 则提供广谱激酶测试矩阵，可看到同一化合物在不同靶点上的高、低活性。

ECBD 保存 EU-OPENSCREEN 项目从 primary assay 到 counter-screening 的正负结果。论文报告数据库包含约 430 万个实验数据点，来自定义明确的化合物库和筛选流程。它说明从实验基础设施直接保存完整结果是可行的，也提醒我们：前瞻性保存完整流程与从历史论文恢复遗漏信息是两个不同问题。

InertDB 从 PubChem 整理生物惰性小分子，并使用生成方法扩展化学空间。它与“建立阴性分子资源”高度重叠，但生成分子并不具备真实实验阴性的证据等级。

### 4.3 阴性数据对模型有价值，但结论依赖任务和负例来源

Mervin 等人在 2015 年整合 ChEMBL 与 PubChem 的大规模活性数据，用推定阴性样本训练靶点预测模型，并报告相对 active-only 模型的改善。这是“阴性生物活性数据可用于模型”的直接先例，也暴露了关键限制：推定阴性并不等于实验确认的 inactive。

InertDB 报告其整理和生成的 inactive 数据在部分下游设置中优于随机 inactive 或性质匹配 decoy。反应预测领域的研究也显示负反应数据可以提升小样本任务，但化学反应失败与蛋白生物活性阴性不是同一种观察。

现有证据足以否定“阴性数据没有价值”，还不足以证明“任何阴性数据都会改善任何模型”。真正需要比较的是实测 inactive、推定阴性、人工 decoy 和文献恢复阴性在同一任务中的差异。

### 4.4 文献活性抽取已经进入大规模、多模态阶段

早期工作已经从论文中抽取 assay 描述、化学实体和反应关系。2026 年的 BioMiner 将这一方向推进到与本设想直接相邻的位置：

- BioVista 从 500 篇论文人工整理 16,457 条生物活性记录；
- 72.5% 的记录来自表格，另有正文和图中记录；
- 系统联合处理蛋白、配体结构和定量活性，包含 Markush 结构解析；
- 完整 bioactivity triplet 的 precision、recall 和 F1 均约为 0.32；
- 从 11,683 篇论文抽取的 82,262 条记录用于预训练后，作者报告两个独立测试集上的 RMSE 改善；
- 人机协作整理 NLRP3 数据后，作者报告 QSAR 富集指标改善。

BioMiner 改变了课题的新颖性边界。现在不能再声称“尚无从论文大规模抽取生物活性并验证模型价值的方法”。不过它只收集 IC50、Ki 和 Kd 等定量数据，研究重点是结构和数值的多模态对应，并未建立以阴性语义为核心的类型系统。阈值截断、定性无效、失败原因、unknown 与 negative 的区别，也没有构成它的主要评价任务。其预印本结果还需要后续同行评议和独立复现。

## 5. 对原问题的直接回答

### 5.1 有没有人做过

有人做过，而且相邻工作已经较多。阴性数据入模、inactive 数据库、完整筛选结果保存、真实场景 benchmark 和大规模文献活性抽取均有直接先例。

### 5.2 做到了什么程度

已有研究能够获取数百万级结构化筛选记录，也能够从上万篇论文中自动整理数万条定量生物活性。研究者已多次证明数据组成、负例来源和切分方式会影响模型结论，并在部分任务中观察到加入阴性数据后的性能改善。

### 5.3 还缺什么

本轮检索尚未发现一个以“阴性证据”为核心、同时完成以下工作的成熟方案：

- 区分实测 inactive、截断值、定性无效、相对变差、失败和 unknown；
- 将化合物、靶点、assay、条件、判定规则和原文证据位置绑定到同一观察；
- 评价系统找回了多少阴性信息，而不是只评价一般活性数值抽取；
- 在控制样本量和类别比例后，证明证据类型与上下文带来额外模型收益。

这是阶段性检索结论，不是绝对的“无人做过”。

### 5.4 我们能否做

可以做一个可发表的窄问题，暂不适合直接承诺“覆盖所有分子科学”。最现实的起点是激酶抑制活性：公开 assay 较多，PKIS 等完整矩阵可以充当参照，ChEMBL 和 PubChem 可用于核对，模型评价也有成熟基线。

## 6. 可行的论文问题

建议将研究问题写成：

> 在小分子激酶活性文献中，能否可靠识别并分型带实验上下文的阴性观察；与仅使用常规数据库标签相比，这些证据是否改善模型在新骨架、新 assay 或时间外推条件下的校准和排序？

这个问题包含两个可独立评价的贡献。

### 6.1 数据与方法贡献

建立一个人工核验的小型金标准语料，标注化合物、靶点、测量类型、数值或定性结果、比较符、单位、实验条件、阴性类型、证据位置和置信度。系统采用规则与模型结合的候选召回，再由人工处理难例。

评价至少包含：

- 记录级 precision、recall、F1；
- 关键字段的准确率；
- 原文定位正确率；
- 阴性类型之间的混淆；
- 每条核验记录的人工时间。

### 6.2 模型价值贡献

在同一数据量和同一切分条件下比较：

1. 只有常规 active 数据；
2. active 加推定阴性；
3. active 加实测 inactive；
4. active 加文献恢复的阴性观察；
5. 第 4 组去掉 assay 上下文或证据置信度。

这样才能区分收益来自更多样本、真实阴性、上下文信息，还是偶然的数据泄漏。主要指标应包含 PR-AUC、校准误差和 assay 级表现，不能只报告随机切分下的 ROC-AUC。

## 7. 先做可行性验证

### 7.1 最小试验

从一个激酶子领域抽取约 50 篇论文，优先选择同时存在正文、表格和补充材料的文章。双人核验其中一部分，以估计标注一致性。试验只需回答四个问题：

- 论文中能找到多少数据库未完整保留的阴性观察？
- 这些观察中有多少具备足够条件，可以转成训练记录？
- 自动方法的召回率是否足以减轻人工阅读，而不是制造更多核验负担？
- 新记录是否改变至少一个真实切分下的模型结果或校准？

### 7.2 继续条件

满足以下条件后再扩大：

- 阴性观察具有稳定、可复核的定义；
- 文献相对数据库确实提供新增信息；
- 自动候选筛选能明显减少人工阅读量；
- 模型实验能排除简单扩样本和类别重平衡的解释；
- 数据许可允许公开证据定位、结构化字段和必要的文本片段。

若新增记录极少、上下文普遍不足，或模型收益在严格切分下消失，应将产出收缩为 benchmark、误差分析或数据审计，而不是继续追求大规模数据库。

## 8. 可能形成的产出

当前最合适的前期产出是“范围综述加可行性方案”。它先明确已有工作、术语和证据缺口，便于外部反馈决定是否进入数据标注。

若最小试验通过，后续论文可以是以下组合：

- 一个阴性生物活性证据标注基准；
- 一套可追溯的人机协作文献抽取方法；
- 一项比较不同负例来源和上下文信息的模型研究；
- 一个规模适中、带证据出处的数据集版本。

数据规模不应成为唯一卖点。更有说服力的是标签定义清楚、证据可追溯、与现有数据库相比确有新增信息，并且下游实验能解释改善来自哪里。

## 9. 当前判断

这个方向有论文潜力，但题目必须缩小。2026 年 BioMiner 已经占据“大规模文献生物活性抽取加模型应用”的重要位置，InertDB 和 ECBD 分别占据 inactive 资源与完整筛选流程保存的位置。剩余空间集中在阴性语义、证据等级、unknown 的处理和增量价值验证。

下一步合理顺序是先提交这份范围综述并确认研究问题，再进行 50 篇论文级别的可行性试验。此时不宜直接建设全领域数据集，也不宜先训练复杂模型。

## 参考文献

1. Smajić N, et al. *Identifying Differences in the Performance of Machine Learning Models for Off-Targets Trained on Publicly Available and Proprietary Data Sets*. Chemical Research in Toxicology, 2023. [DOI](https://doi.org/10.1021/acs.chemrestox.3c00042)
2. Chen L, et al. *Hidden bias in the DUD-E dataset leads to misleading performance of deep learning in structure-based virtual screening*. PLOS ONE, 2019. [DOI](https://doi.org/10.1371/journal.pone.0220113)
3. Tian T, et al. *Benchmarking compound activity prediction for real-world drug discovery applications*. Communications Chemistry, 2024. [DOI](https://doi.org/10.1038/s42004-024-01204-4)
4. Elkins JM, et al. *Comprehensive characterization of the Published Kinase Inhibitor Set*. Nature Biotechnology, 2016. [DOI](https://doi.org/10.1038/nbt.3374)
5. Mervin LH, et al. *Target prediction utilising negative bioactivity data covering large chemical space*. Journal of Cheminformatics, 2015. [DOI](https://doi.org/10.1186/s13321-015-0098-y)
6. Tran-Nguyen VK, et al. *LIT-PCBA: An Unbiased Data Set for Machine Learning and Virtual Screening*. Journal of Chemical Information and Modeling, 2020. [DOI](https://doi.org/10.1021/acs.jcim.0c00155)
7. An Y, et al. *InertDB as a generative AI-expanded resource of biologically inactive small molecules from PubChem*. Journal of Cheminformatics, 2025. [DOI](https://doi.org/10.1186/s13321-025-00999-1)
8. Škuta C, et al. *ECBD: European chemical biology database*. Nucleic Acids Research, 2025. [DOI](https://doi.org/10.1093/nar/gkae904)
9. Kretschmer F, et al. *Coverage bias in small molecule machine learning*. Nature Communications, 2025. [DOI](https://doi.org/10.1038/s41467-024-55462-w)
10. Yan J, et al. *BioMiner: A Multi-modal System for Automated Mining of Protein-Ligand Bioactivity Data from Literature*. arXiv, 2026. [Preprint](https://arxiv.org/abs/2604.21508)
11. Lee K, et al. *The Fragility of Bioactivity Prediction: Rigorous Dataset Splits Expose the Illusion of ML Accuracy*. Chemistry, 2026. [DOI](https://doi.org/10.1002/chem.71208)
12. Medina-Franco JL, et al. *Yes SIR! On the structure-inactivity relationships in drug discovery*. Drug Discovery Today, 2022. [PubMed](https://pubmed.ncbi.nlm.nih.gov/35561964/)
13. PubChem. *PubChem BioAssay documentation*. [Documentation](https://pubchem.ncbi.nlm.nih.gov/docs/bioassays)

