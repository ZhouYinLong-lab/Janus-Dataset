# 小分子生物活性阴性数据：价值、获取现状与可行性方案

**文献类型：** 初步范围综述

**检索更新：** 2026 年 9 月

**当前范围：** 小分子化合物—蛋白靶点生物活性；材料合成和化学反应仅作旁证

## 1. 问题定义

公开生物活性数据并不是实验空间的完整记录。数据从实验进入论文和数据库，要经过研究对象选择、筛选流程、结果报告、发表和数据库整理等环节。因此，这里的偏倚不宜简单归结为“阴性结果没有发表”，更准确的表述是：公开数据可能同时存在**测试覆盖偏倚、阳性结果偏好、低活性结果遗漏、实验条件丢失和负例构造偏差**。

本报告把**阳性数据**定义为：化合物在明确的靶点、实验体系、测量方式和判定标准下达到预设活性要求的实验观察；把**阴性数据**定义为：化合物在同样明确的上下文中未达到预设活性要求、仅表现出低活性或未产生预期结果的实验观察。

“阴性数据”内部仍需继续区分：

| 类型 | 例子 | 科学含义 | 能否直接作为负标签 |
| --- | --- | --- | --- |
| 实测 inactive | assay 判定为 inactive | 在特定实验和阈值下未达到活性标准 | 可以，但只对该 assay 成立 |
| 截断值 | `IC50 > 10 μM` | 真值位于一个区间，而不是精确等于阈值 | 应按区间或有序标签处理 |
| 定性无效 | `inactive`、`no effect`、`weak activity` | 有阴性倾向，但强度和条件可能不完整 | 可作弱标签，需保留原文与置信度 |
| 相对变差 | B 比 A 活性低 | 只说明相对顺序，不一定绝对无活性 | 更适合排序或成对比较 |
| 实验失败 | 未得到预期产物、测量失败 | 失败发生在哪一步决定其含义 | 不能自动等同于 inactive |
| 推定阴性 | 未知组合按规则抽为负例 | 带噪声的建模假设，没有直接实验确认 | 只能作为推定标签 |
| 人工 decoy | 性质匹配的虚拟对照分子 | 用于训练或评价的构造样本 | 不能视为实测阴性 |
| unknown / untested | 没有记录或没有测试 | 缺失状态，不代表无活性 | 不能 |

因此，真正的问题不是简单增加一个负类，而是回答两个问题：**真实阴性信息是否为模型提供了独立价值，以及能否从现有数据库和历史文献中把这类信息连同上下文可靠恢复出来。**

## 2. 阴性数据的价值：已有证据做到哪一步

### 2.1 代表性对照研究

| 工作 | 任务 | 阴性数据类型 | 对照组 | 是否提升 | 提升体现 | 主要局限 |
| --- | --- | --- | --- | --- | --- | --- |
| [Mervin 等，2015](https://doi.org/10.1186/s13321-015-0098-y) | 多靶点预测与排序 | ChEMBL、PubChem 派生的实测记录和推定 inactive | ChEMBL active-only 模型 | 是，直接证据 | 外部测试中 PR-AUC 从 0.45 提高到 0.56，BEDROC 从 0.76 提高到 0.85；同等召回下假阳性更少 | 负例包含 sphere-exclusion 选出的推定阴性；结果受类别规模、化学相似性和过采样影响，不能等同于实测阴性的独立作用 |
| [InertDB，2025](https://doi.org/10.1186/s13321-025-00999-1) | LIT-PCBA、MUV 活性分类 | PubChem 中跨 assay 持续 inactive 的 3,205 个化合物，以及 64,368 个生成扩展分子 | 从 PubChem、ZINC 随机取样的负例，DeepCoy 性质匹配 decoy，原 benchmark 实测 inactive | 部分提升 | 在相同 hold-out 测试集上，人工整理子集总体优于随机 PubChem/ZINC 和 DeepCoy；但替换原 benchmark 实测 inactive 后，LIT-PCBA 无显著差异，MUV 仅小幅提高 | 最强结果说明“负例选择方式重要”，并未证明比等量实测 inactive 普遍更好；生成分子没有实验阴性证据 |
| [Toniato 等，2025](https://doi.org/10.1126/sciadv.adt5578) | 反应结果预测 | 受控构造的错误产物和 HTE 低收率反应 | 只用成功反应微调的模型 | 是，跨领域直接证据 | 在少至 20 个阳性、阴性至少多 40 倍时仍可训练；真实 HTE 低数据设置中验证准确率由 0.610 提至 0.644，测试 top-10 准确率由 0.427 提至 0.441 | 属于化学反应而非蛋白生物活性；收益与强化学习策略绑定，且阴性数量远多于阳性 |
| [PUDT，2016](https://doi.org/10.1016/j.neucom.2016.03.080) | 药物—靶点相互作用预测 | 从未标注集合中推断的可靠/可能负例 | 直接把未知相互作用当负例的常规方法及当时基线 | 是，间接证据 | 将 unknown 保留为未标注数据，在四类靶点数据上取得相当或更好的预测表现 | 没有实验确认的阴性样本；证明的是 unknown 处理方式重要，不是文献阴性的价值 |
| [Chen 等，2019](https://doi.org/10.1371/journal.pone.0220113) | 结构虚拟筛选 | DUD-E 人工 decoy | 结构模型与仅使用配体拓扑的控制模型 | 否；属于反证 | 仅用配体信息也可得到很高分数，说明模型可能利用 analogue/decoy bias | 不能量化实测阴性的收益，但证明 decoy 与真实 inactive 不可互换 |
| [DEEPScreen，2020](https://doi.org/10.1039/C9SC03414E) | 药物—靶点活性分类 | ChEMBL 中有真实实验测量的 inactive | 随机及 scaffold、structure、temporal 等非随机切分 | 未隔离阴性增益 | 证明实测 inactive 与非随机切分可以形成可用基准，并专门分析了负例选择偏差 | 没有 active-only、等样本量实测 inactive 和文献阴性的完整消融，不能证明独立增益 |
| [CARA，2024](https://doi.org/10.1038/s42004-024-01204-4) | assay 级虚拟筛选与先导优化 | ChEMBL assay 内的活性测量与标签 | zero-shot、few-shot、VS、LO 等现实任务设置 | 未直接检验 | 显示不同 assay 和任务场景下表现差异明显，整体指标会掩盖局部失败 | 是评价框架，不是阴性数据价值实验 |

### 2.2 按“改善了什么”归纳

| 可能价值 | 当前证据判断 | 依据与缺口 |
| --- | --- | --- |
| 分类或活性预测 | **有条件支持** | Mervin、InertDB 和跨领域的 Toniato 均报告改善，但阴性来源、样本规模和算法同时变化 |
| 排序与虚拟筛选 | **有直接但有限的支持** | Mervin 的 BEDROC 和早期识别提高；InertDB 在 VS benchmark 上优于若干构造负例；DUD-E 研究同时说明结果极易受 decoy 偏差影响 |
| 概率校准 | **证据不足** | 当前核心文献主要报告 AUROC、PR-AUC、BEDROC 或准确率，未系统比较加入不同阴性类型前后的 Brier score、ECE 或可靠性曲线 |
| scaffold / OOD 泛化 | **证据不足** | DEEPScreen、CARA 等说明必须严格切分，但尚未证明文献恢复阴性在等样本量下能稳定改善新骨架、新 assay 或时间外推 |
| 避免把“未测试”误当作“无效” | **有方法层面的支持** | 正—未标注学习表明 unknown 与 negative 分开处理更合理，但缺少与大量实测阴性共同评价的研究 |
| 比较不同阴性类型 | **已有明确警示，缺少统一对照** | InertDB 和 DUD-E 表明随机负例、性质匹配 decoy、推定阴性和实测 inactive 的效果不同；目前尚无统一 benchmark 同时比较所有类型 |
| 排除类别平衡或扩样本效应 | **尚未解决** | 多数研究同时改变了负例来源、数量、类别比例或训练方法；真正需要的是等样本量、等比例和固定切分下的消融 |

**现阶段可以下的结论是：阴性信息在部分任务和设置下具有明确价值，但现有证据还不足以证明“阴性数据本身具有不依赖样本量、类别平衡、负例构造和任务设置的普遍独立价值”。** 这个较弱但更可靠的结论，也正好给后续研究留下了可检验的问题。

## 3. 阴性数据的获取与挖掘：已有方法做到哪一步

### 3.1 技术路线版图

| 路线 | 可获得的内容 | 代表资源或方法 | 当前成熟度 | 仍然存在的问题 |
| --- | --- | --- | --- | --- |
| 结构化数据库直接获得 | active、inactive、inconclusive、数值结果、assay 描述 | [PubChem BioAssay](https://pubchem.ncbi.nlm.nih.gov/docs/bioassays)、ChEMBL、[LIT-PCBA](https://doi.org/10.1021/acs.jcim.0c00155) | 较成熟 | `inactive` 由提交者和 assay 规则定义；不同 assay 的阈值和质量不一致，数据库没有记录的组合仍是 unknown |
| 完整筛选矩阵与 HTS 流程 | primary screen、confirmatory assay、counter-screen、整批高低活性结果 | [PKIS](https://doi.org/10.1038/nbt.3374)、[ECBD](https://doi.org/10.1093/nar/gkae904)、PubChem HTS | 在特定项目中成熟 | 覆盖的是少数化合物库和靶点；属于实验流程的前瞻性完整保存，不能自动恢复历史论文中的遗漏信息 |
| 论文正文中的定量结果 | IC50、Ki、Kd、抑制率等明确数值 | 化学信息抽取工具、assay 描述抽取方法、[BioMiner](https://arxiv.org/abs/2604.21508) | 已进入大规模、多模态阶段 | 化合物指代、Markush 结构、单位、靶点和条件联合对齐仍难；BioMiner 完整三元组 F1 约 0.32 |
| 截断或区间结果 | `IC50 > 10 μM`、低于检测限等 | BioVista 已包含 `Ki > 20000 nM` 一类样例 | 可抽取，但未被单独评价 | 比较符一旦丢失就会改变标签含义；尚缺截断阴性专门的召回率和错误分析 |
| 定性阴性与相对阴性 | `no activity`、`weak`、`less active than`、无剂量反应 | 通用文本抽取、规则和语言模型可召回候选 | 初步可行，尚不成熟 | 指代、否定范围、比较对象和实验条件复杂；本轮未找到以此为核心并公开金标准的成熟生物活性系统 |
| 表格、图和补充材料 | assay 矩阵、失败化合物、无响应项、结构—数值对应 | BioVista 中 72.5% 的记录来自表格，11.6% 来自图，15.8% 来自正文 | 表格/图抽取已有进展 | 补充材料格式分散；空白单元格可能表示未测、缺失或无响应，不能直接判为阴性 |
| 构造型负例 | assumed negative、random negative、decoy、property-matched decoy | Mervin 的推定阴性、DUD-E、DeepCoy、正—未标注学习 | 建模上成熟 | 成本低但缺少直接实验依据，容易引入捷径；应作为对照组而不是“已找回的阴性证据” |

PubChem 已经能够按 assay 下载测试过的 active 或 inactive 化合物，并保留 primary、confirmatory 等 assay 类型。LIT-PCBA 进一步使用 PubChem 的实测 active/inactive 构造虚拟筛选数据集。PKIS 和 ECBD 则证明，只要从实验流程起就保留完整矩阵，低活性和阴性结果可以被系统保存。

文献侧也不是空白。BioMiner 从 500 篇论文人工整理了 16,457 条生物活性记录，其中大部分位于表格；随后从 11,683 篇论文抽取 82,262 条定量记录，并报告了下游模型改善。但它的主体仍是 IC50、Ki、Kd 等定量活性与化学结构的对应，没有把定性无效、相对变差、失败原因、unknown 与 negative 的区分作为核心标注和评价任务。

> **“已有阴性数据”与“从历史文献恢复真实阴性证据”不是同一个问题。** 前者可以来自结构化筛选、推定规则或 decoy 构造；后者要求证明某个实验确实发生过，保留化合物、靶点、assay、阈值、条件、结果类型和原始证据位置，并说明它与数据库已有记录相比增加了什么。

## 4. 现有工作的共同缺口

| 问题 | 已有工作较成熟 | 仍明显不足 |
| --- | --- | --- |
| 阴性数据是否有价值 | 靶点预测、活性分类、反应预测中已有改善案例 | 不同阴性类型的独立价值；排除扩样本、重平衡和数据泄漏后的因果解释 |
| 阴性数据资源 | inactive、HTS、完整筛选矩阵和 decoy 均已存在 | 历史文献中带出处、实验条件和不确定性的观察级阴性证据 |
| 自动抽取 | 定量活性、化学实体、表格和图抽取已有较大进展 | 定性阴性、相对阴性、失败原因、否定范围和空白单元格语义 |
| 标签表达 | 二分类标签和连续活性值已有成熟工具链 | 阴性类型、区间值、证据等级、unknown、inconclusive 和 uncertainty 的统一表达 |
| 下游评价 | 随机切分、常规分类和排序指标非常普遍 | scaffold、temporal、unseen-assay 条件下的增量价值、校准与简单相似性基线 |
| 数据质量 | 数据库筛选、去重、标准化和人工整理已有实践 | 原文证据可追溯性、跨来源冲突、重复实验及 assay 条件完整度的联合审计 |

这张版图显示，单纯“收集更多 inactive 分子”很难形成新的贡献；单纯“从论文中抽取 IC50、Ki、Kd”也已有直接先例。比较清楚的交叉缺口是：**建立阴性专用的类型体系和证据链，并用控制充分的实验判断这些信息是否比普通负标签更有用。**

## 5. 具体研究问题

建议先把问题限定为：

> **在小分子激酶活性文献中，能否可靠识别并分型带实验上下文的阴性观察；与常规数据库 inactive、推定阴性和人工 decoy 相比，这些文献证据是否改善模型在新骨架、新 assay 或时间外推条件下的排序、分类和校准？**

这个问题可以拆为四个可验证的子问题：

1. 论文正文、表格和补充材料中，存在多少未被 ChEMBL 或 PubChem 完整保存的阴性观察？
2. 实测 inactive、截断值、定性无效和相对变差能否稳定区分，自动方法能达到怎样的召回率和证据定位准确率？
3. 在固定样本量、类别比例和数据切分后，文献恢复阴性是否优于数据库 inactive、推定阴性或 decoy？
4. 如果产生收益，收益来自真实负类边界、assay 上下文、证据质量，还是更接近测试集的化学结构分布？

激酶活性适合作为起点，因为已有 PKIS 等较完整矩阵可充当参照，ChEMBL、PubChem 可用于查重，assay 和结构切分也有成熟基线。这个范围用于验证方法，不等于最终只能研究激酶，更不应在可行性试验前承诺覆盖所有分子科学领域。

## 6. 最小可行性实验

### 6.1 数据与标注

选择约 50 篇激酶活性论文，优先覆盖正文、表格和补充材料，并包含一部分可与 PKIS、ChEMBL 或 PubChem 对照的论文。以“实验观察”为单位记录：

- 化合物及结构标识；
- 靶点、assay 类型、测量类型和实验体系；
- 数值、比较符、单位、检测限和判定阈值；
- 阴性类型、unknown / inconclusive 状态和置信度；
- 原文、表格或补充材料中的证据位置；
- 与数据库记录的对应、缺失或冲突关系。

先双人复核其中一部分，建立小型金标准。若类型之间的一致性很低，应先修改定义，而不是扩大语料。

### 6.2 抽取与恢复评价

使用关键词规则、表格解析和现有语言模型召回候选，再由人工核验。至少报告：记录级 precision、recall、F1，关键字段准确率，证据定位准确率，各阴性类型的混淆矩阵，以及每条有效记录所需的人工时间。

抽取实验要分别统计正文、表格和补充材料，特别记录三类失败：把 unknown 当阴性、丢失 `>`/`<` 比较符，以及把相对变差误判为绝对 inactive。

### 6.3 数据库增量评价

将人工确认记录与 ChEMBL、PubChem 对齐，区分：完全已有、数值已有但条件或比较符缺失、数据库无记录、数据库与论文冲突。只有后面三类才能说明文献恢复产生了实际增量。

### 6.4 模型价值评价

在相同 active 集、相同负例数量、相同类别比例和相同切分下比较：

1. active-only 基线；
2. active + 随机/推定阴性；
3. active + 性质匹配 decoy；
4. active + 数据库实测 inactive；
5. active + 文献恢复阴性；
6. 将 unknown 保持为未标注数据的正—未标注学习基线；
7. 第 5 组去掉 assay 上下文或证据置信度。

评价至少包括 PR-AUC、BEDROC 或 EF1%、Brier score / ECE、assay 级结果，并设置 random、scaffold、temporal 和 unseen-assay 切分。还应加入最近邻或简单指纹模型，避免把复杂模型的记忆能力误认为数据价值。

### 6.5 继续、收缩或停止

项目继续扩大的条件是：文献能稳定提供数据库缺失且可复核的阴性观察；自动召回明显减少人工阅读；在严格切分和等样本量对照中，至少一个阴性类型或上下文字段产生可重复的增量。

如果能可靠标注但模型收益有限，可收缩为阴性证据 benchmark、数据质量审计或抽取方法论文；如果新增记录很少、上下文普遍不足，或收益在严格对照下消失，则不应继续追求大规模统一数据集。

## 结论

现有研究已经证明：阴性信息并非没有价值，负例来源会显著影响模型，结构化 inactive 和完整筛选数据也能够被系统保存；文献定量生物活性抽取甚至已经进入万篇论文规模。但目前能够支持的仍是“**部分阴性数据在部分任务和设置下有价值**”，而不是“任何阴性数据都能普遍改善模型”。

仍值得研究的不是再建一个普通 inactive 集合，而是从历史文献中恢复**带类型、上下文、不确定性和原始出处的真实阴性观察**，并通过等样本量、多负例对照和严格分布外评价证明其增量价值。若小规模试验能够同时通过“可找回、可可靠标注、相对数据库有增量、对模型有独立作用”四项检验，这一方向具备形成数据集、抽取方法与模型评价相结合论文的可能。

## 主要参考文献

1. Mervin LH, et al. *Target prediction utilising negative bioactivity data covering large chemical space*. Journal of Cheminformatics, 2015. [DOI](https://doi.org/10.1186/s13321-015-0098-y)
2. Chen L, et al. *Hidden bias in the DUD-E dataset leads to misleading performance of deep learning in structure-based virtual screening*. PLOS ONE, 2019. [DOI](https://doi.org/10.1371/journal.pone.0220113)
3. Rifaioglu AS, et al. *DEEPScreen: high performance drug-target interaction prediction with convolutional neural networks using 2-D structural compound representations*. Chemical Science, 2020. [DOI](https://doi.org/10.1039/C9SC03414E)
4. Tran-Nguyen VK, et al. *LIT-PCBA: An Unbiased Data Set for Machine Learning and Virtual Screening*. Journal of Chemical Information and Modeling, 2020. [DOI](https://doi.org/10.1021/acs.jcim.0c00155)
5. Tian T, et al. *Benchmarking compound activity prediction for real-world drug discovery applications*. Communications Chemistry, 2024. [DOI](https://doi.org/10.1038/s42004-024-01204-4)
6. An Y, et al. *InertDB as a generative AI-expanded resource of biologically inactive small molecules from PubChem*. Journal of Cheminformatics, 2025. [DOI](https://doi.org/10.1186/s13321-025-00999-1)
7. Škuta C, et al. *ECBD: European chemical biology database*. Nucleic Acids Research, 2025. [DOI](https://doi.org/10.1093/nar/gkae904)
8. Elkins JM, et al. *Comprehensive characterization of the Published Kinase Inhibitor Set*. Nature Biotechnology, 2016. [DOI](https://doi.org/10.1038/nbt.3374)
9. Lan W, et al. *Predicting drug-target interaction using positive-unlabeled learning*. Neurocomputing, 2016. [DOI](https://doi.org/10.1016/j.neucom.2016.03.080)
10. Toniato A, et al. *Negative chemical data boosts language models in reaction outcome prediction*. Science Advances, 2025. [DOI](https://doi.org/10.1126/sciadv.adt5578)
11. Yan J, et al. *BioMiner: A Multi-modal System for Automated Mining of Protein-Ligand Bioactivity Data from Literature*. arXiv, 2026. [Preprint](https://arxiv.org/abs/2604.21508)
12. Swain MC, Cole JM. *ChemDataExtractor: A Toolkit for Automated Extraction of Chemical Information from the Scientific Literature*. Journal of Chemical Information and Modeling, 2016. [DOI](https://doi.org/10.1021/acs.jcim.6b00207)
13. PubChem. *PubChem BioAssay documentation*. [Documentation](https://pubchem.ncbi.nlm.nih.gov/docs/bioassays)

**结论边界：** 以上结论来自截至 2026 年 9 月的初步范围检索和核心论文核对，可以定位主要相邻路线和实验缺口，但不能据此声称不存在任何同类工作。进入正式研究前，仍需为“定性阴性、相对阴性和失败原因抽取”补做专门的系统检索。
