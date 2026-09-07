# 小分子生物活性阴性数据初步调研

**研究现状与可行性设想**  
**日期：2026 年 9 月**  
**当前范围：小分子化合物与蛋白靶点的生物活性数据**

## 结论摘要

公开生物活性数据并不完整代表实际实验空间。研究过程更关注活性化合物，数据进入论文和数据库时还会受到筛选流程、报告方式、人工阈值和数据整理规则的影响。由此产生的问题不只是正负样本数量不平衡，还包括哪些分子被测试、低活性结果是否被保留、实验条件是否完整，以及模型是否利用了数据集的构造规律。

初步检索表明，这个方向已经有较多相关工作。研究者已经使用阴性生物活性数据训练模型，建立 inactive 化合物资源，保存完整筛选流程中的正负结果，并从论文中大规模抽取定量生物活性。因此，单纯“收集更多阴性分子”或“从论文中抽取活性数据”已不足以构成明确的新意。

目前仍有研究空间的问题是：不同类型的阴性结果经常被压缩为同一个负标签。实测 inactive、超过检测上限的截断值、定性无效、相对变差、实验失败、推定阴性、人工 decoy 和未测试数据具有不同的科学含义。如果能保留这些差异、实验条件和原文证据，再检验它们是否为模型带来独立价值，可能形成一个较明确的研究问题。

## 已有工作做到哪里

| 研究环节 | 代表工作 | 已有成果 | 对本方向的限制 |
| --- | --- | --- | --- |
| 阴性数据用于模型 | Mervin 等，2015 | 整合 ChEMBL 与 PubChem 数据，比较包含推定阴性与仅使用 active 数据的靶点预测模型 | 阴性数据入模不是新问题；推定阴性不等于实测阴性 |
| inactive 数据资源 | InertDB，2025 | 从 PubChem 整理 inactive 化合物，并以生成方法扩展化学空间 | 不能仅靠增加 inactive 分子数量体现贡献；生成分子没有实验阴性证据 |
| 完整筛选流程 | ECBD，2025 | 保存 primary assay 和 counter-screening 中的正负结果，包含约 430 万条实验记录 | 说明完整记录可行，但它解决的是前瞻性保存，不是历史文献恢复 |
| 真实场景评价 | CARA，2024 | 按 assay 和任务场景组织数据，说明整体指标可能掩盖部分 assay 上的失败 | 新数据必须在 assay 级、结构级或时间外推条件下评价 |
| 文献活性抽取 | BioMiner，2026 预印本 | 从 500 篇论文建立 16,457 条人工标注记录；从 11,683 篇论文抽取 82,262 条数据并用于下游模型 | 一般生物活性抽取已有直接先例；完整记录抽取 F1 约为 0.32，仍有较大误差 |

上述工作说明，研究重点应从“有没有阴性数据”转向“阴性证据具体是什么、是否可信、是否具有额外价值”。

## 仍未充分解决的问题

### 阴性标签缺少统一的科学含义

同一个 negative 标签可能来自完全不同的情况：一次实验明确测得 inactive；活性值超过检测上限；正文只描述“无明显作用”；一个候选相对参照物变差；数据库没有记录某个组合；或者研究者为了训练模型而构造了 decoy。只有前几类能够提供实验边界信息，unknown 不能自动转成 negative。

### 实验条件常被弱化

活性是化合物在具体靶点、实验体系、浓度、测量类型和判定阈值下的结果。同一化合物在不同 assay 中可能得到不同结论。若只保存化合物与 0/1 标签，模型无法区分真实差异与实验条件差异。

### 文献抽取尚未专门评价阴性证据

BioMiner 已覆盖正文、表格、图和化学结构，主要目标是恢复 IC50、Ki 和 Kd 等定量活性。它尚未把定性无效、失败原因、阴性类型和 unknown 的区分作为主要评价任务。这使“面向阴性证据的标注体系和基准”仍可能具有独立价值。

### 模型收益的来源需要拆开验证

模型表现改善可能只是因为样本更多、类别更平衡或训练集与测试集更相似。需要在相同数据量和严格切分下，分别比较推定阴性、实测 inactive、文献恢复阴性，以及是否保留 assay 上下文，才能判断真正起作用的因素。

## 建议的具体研究问题

> 在小分子激酶活性文献中，能否可靠识别并分型带实验上下文的阴性观察；与常规数据库标签相比，这些记录是否改善模型在新骨架、新 assay 或时间外推条件下的表现？

激酶活性适合作为起点，因为公开 assay 较多，存在 PKIS 等较完整的测试矩阵，也可以使用 ChEMBL、PubChem 和 CARA 进行核对与评价。这个范围只用于可行性验证，不代表最终必须限制在激酶领域。

## 最小可行性试验

第一步不建设大规模数据库，而是选取约 50 篇激酶活性论文，优先覆盖正文、表格和补充材料。人工标注化合物、靶点、测量类型、结果、比较符、单位、实验条件、阴性类型、证据位置和置信度，并对其中一部分进行独立复核。

第二步使用规则或现有语言模型召回候选句、表格行和图注，比较自动方法与人工标注的 precision、recall、证据定位准确率和人工核验时间。自动方法的作用首先是减少阅读量，而不是直接替代人工判断。

第三步将新增记录与 ChEMBL 或 PubChem 对照，确认文献是否确实提供数据库未完整保留的信息。随后在等样本量条件下比较 active-only、推定阴性、实测 inactive、文献恢复阴性，以及去除 assay 上下文后的结果。

## 继续或收缩的判断标准

项目适合继续扩大，需要同时看到三个信号：文献能够稳定提供数据库缺失的阴性观察；自动候选筛选能够减少人工阅读负担；新增数据或上下文在严格切分下产生可重复的模型差异。

如果新增记录很少或上下文不足，不应继续追求大规模数据集。如果能够建立可靠标注，但模型收益有限，可以收缩为阴性证据 benchmark 或数据审计研究。如果严格评价下没有新增信息和方法优势，应停止扩展并重新选择问题。

## 希望讨论的问题

1. 研究主线应更侧重数据偏倚、阴性证据抽取，还是下游模型影响？
2. 激酶活性是否适合作为第一阶段的验证领域？
3. 50 篇论文级别的试验能否作为进入正式研究前的判断依据？
4. 后续产出更适合定位为数据集、抽取方法、benchmark，还是数据审计？
5. 是否存在可用于对照的内部实验数据、领域知识或相关项目？

## 主要参考文献

1. Mervin LH, et al. Target prediction utilising negative bioactivity data covering large chemical space. *Journal of Cheminformatics*. 2015. https://doi.org/10.1186/s13321-015-0098-y
2. Chen L, et al. Hidden bias in the DUD-E dataset leads to misleading performance of deep learning in structure-based virtual screening. *PLOS ONE*. 2019. https://doi.org/10.1371/journal.pone.0220113
3. Tran-Nguyen VK, et al. LIT-PCBA: An Unbiased Data Set for Machine Learning and Virtual Screening. *Journal of Chemical Information and Modeling*. 2020. https://doi.org/10.1021/acs.jcim.0c00155
4. Tian T, et al. Benchmarking compound activity prediction for real-world drug discovery applications. *Communications Chemistry*. 2024. https://doi.org/10.1038/s42004-024-01204-4
5. An Y, et al. InertDB as a generative AI-expanded resource of biologically inactive small molecules from PubChem. *Journal of Cheminformatics*. 2025. https://doi.org/10.1186/s13321-025-00999-1
6. Škuta C, et al. ECBD: European chemical biology database. *Nucleic Acids Research*. 2025. https://doi.org/10.1093/nar/gkae904
7. Yan J, et al. BioMiner: A Multi-modal System for Automated Mining of Protein-Ligand Bioactivity Data from Literature. arXiv preprint. 2026. https://arxiv.org/abs/2604.21508
8. Lee K, et al. The Fragility of Bioactivity Prediction: Rigorous Dataset Splits Expose the Illusion of ML Accuracy. *Chemistry*. 2026. https://doi.org/10.1002/chem.71208

**结论边界：** 以上判断来自截至 2026 年 9 月的初步范围检索。当前可以确认主要相邻路线和直接先例，但不能据此声称此前没有任何同类研究。正式立项前仍需针对阴性证据抽取及激酶数据开展更系统的查重和小规模验证。

