# 分子机器学习中删失实验值的既有工作核查

**核查日期：** 2026-09-30  
**主问题关联度：** 2/3（直接证明分子模型已利用阈值型、非精确实验观测；但不等同于文献中明确的 inactive/no-effect 观察挖掘）。

## 结论先行

“把不精确但带阈值的信息用于分子机器学习”早已有人研究，且已有药物发现研究报告：在内部药企数据上，将删失标签纳入训练，通常改善不确定性预测的负对数似然，效果在多种集成/贝叶斯模型中较明显；公开了可在 TDC 数据上运行的代码框架。不过，这不是“从文献中识别明确阴性结果”本身：删失值是测量超过检测/报告边界后留下的区间信息（如 `IC50 > 某阈值`），它可能支持某个特定 assay 下的低活性判断，但不能脱离 assay、方向、阈值及实验条件就直接改写为通用 inactive 标签。

因此，这批先例削弱“第一次使用被忽略的阈值信息训练分子模型”这一宽泛主张，却没有回答一个更具体的问题：分散在论文、表格和补充材料中的明确无活性/无效应/失败证据，能否被可靠找回、与对应 assay 和实体对齐，并在与删失回归、结构化 inactive 数据及样本量/类别平衡匹配的比较中带来独立收益？

## 直接先例：Svensson 等，2025

Svensson 等在 *Artificial Intelligence in the Life Sciences* 发表的工作，扩展集成模型、Monte Carlo dropout、Bayes by Backprop 与高斯回归模型，使模型可以在精确值之外利用左右删失值；高斯模型使用 Tobit 似然，其他若干模型使用单侧损失。作者在 15 个内部药物研发 assay 上进行时间切分评估，任务覆盖靶点 IC50/EC50 与 ADME-T 性质。各 assay 的删失比例从 0% 到 63% 不等；部分 CYP/hERG assay 约 42%–63%。[论文 DOI](https://doi.org/10.1016/j.ailsci.2025.100128) · [开放全文](https://research.chalmers.se/publication/545243/file/545243_Fulltext.pdf)

**论文报告的主要发现：** 对 epistemic uncertainty，纳入删失值的集成和贝叶斯模型在绝大多数 assay/时间设定中显著更好或相当；aleatoric uncertainty 的收益更多出现在删失数据占比高（约 >35%）的 assay。其主要消融比较使用 NLL 衡量预测与不确定性校准的联合表现，而不是单独证明二分类 inactive 预测或普遍提升某一分类指标。论文建议未来建模保留这些标签。上述结果是作者在内部数据上报告的，外部研究者无法取得核心数据独立复现。

**可复现性边界：** 作者发布 Apache-2.0 的 [UQ4DD 代码](https://github.com/MolecularAI/uq4dd)，并给出基于 Therapeutics Data Commons 数据的示例；README 表明研究中的内部数据、时间信息、重复实验标准差与删失观测不可公开，故公开代码可复用方法但不能复现论文的核心企业数据结果。论文明确指出公开数据中的实验删失值较少。[代码说明](https://github.com/MolecularAI/uq4dd#data)

## 更早的方法先例：Lind，2010

Lind 的 QSAR 工作已经指出，检测限/截断限之上的或之下的结果仍含信息，描述用插补估计潜在数值、纳入删失值的回归方法，并在 Free-Wilson R-group 活性评分中检验稳定性与准确性。[PubMed 记录与摘要](https://pubmed.ncbi.nlm.nih.gov/27464349/) · [DOI](https://doi.org/10.1002/minf.201000074)

这证明删失值并非近年才被注意到，但研究范围是特定 QSAR 回归技术，不是文献证据抽取资源，也不构成阴性语义分类或全域数据集的先例。

## 结构化数据库字段已把数值、分类结果与解释分开

ChEMBL 官方数据提交规范分别定义数值 `VALUE`、关系符 `RELATION`、文本 `TEXT_VALUE` 与解释性 `ACTIVITY_COMMENT`；文本值示例包括 Active/Toxicity/Not Toxic，关系符允许 `<`、`>`、`<=`、`>=` 等。规范还明确提醒解释性 comment 可存数值测量的“Active”判断或分类阈值，非数值观察则应进入 `TEXT_VALUE`。ChEMBL 对 PubChem 的说明称，PubChem 的 active/inactive/inconclusive Activity Summary 会捕获到 ChEMBL 的 Activity Comment；同时通常只导入 PubChem 含 AC potency result 的活动记录，不能把该导入过程误读为所有 PubChem binary summary 都已完整结构化导入。[ChEMBL ACTIVITY 字段规范](https://chembl.gitbook.io/chembl-data-deposition-guide/file-structure/field-names-and-data-types-minimal-data-submission/activity.tsv) · [数值与文本结果使用说明](https://chembl.gitbook.io/chembl-data-deposition-guide/file-structure/field-names-and-data-types-minimal-data-submission/activity.tsv/when-to-use-value-and-text_value) · [Activity/PubChem 常见问题](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions)

该 FAQ 还规定，计算标准化 `pChEMBL` 数值要求 `standard_relation == "="`。所以 ChEMBL 可以在原始 activity 记录层保留 `<`/`>` 与阈值，但这类观测不会进入这一常用精确 potency 标准值字段。这提供了一条“原始结构化记录存在、常用模型-ready 派生值未收录”的可检验链路；被排除的实际数量及其对具体公开 benchmark 的影响尚未测量。

**它说明了什么：** 按理想的数据模式，至少可以分开保存精确/删失数值、分类结果、阈值解释和 assay；这让“真实 inactive 观察根本不存在结构化表示”不成立。

**它仍未说明什么：** 模式规范不等于实际覆盖率，也不证明所有 record 都能追溯到原文句段、阈值和协议；pChEMBL 的排除规则也不等于删失记录被全数据库删除。某条数值为强结合亲和力的记录，其 `activity_comment` 仍可能因 counter-screen、assay 定义或作者总体结论标成 inactive/inconclusive；应回到源 assay 和原始文献查明，而不能用单一数值覆盖该状态。

## 强竞争先例：ChEMBL20 阴性标签已被大规模用于模型训练

Mayr 等 2018 年的 *Chemical Science* 工作以 ChEMBL 20 构建靶点预测 benchmark，补充材料明确写出：先利用 `activity_comment` 中的 `Active`、`inactive`、`Not Active` 等标准文字判定测量结果；其中还包括“10 μM 下抑制率低于 50%、因此未拟合剂量反应曲线”的 `Not Active` 说明。对没有标准 comment 的记录，他们进一步依数值、单位和 `standard_relation`（包括 `<`、`>`、`<=`、`>=` 等）及 log-potency 阈值分配 active/inactive/weak/indeterminate 标签，并剔除同 assay 内同时被标为正负的冲突观测。整理后得到 1,310 个 assay、4,743,712 条 assay measurements、456,331 个化合物；作者用这些标签比较九种靶点预测方法。[论文 DOI](https://doi.org/10.1039/C8SC00148K) · [补充材料：标签定义与数据量](https://www.rsc.org/suppdata/c8/sc/c8sc00148k/c8sc00148k1.pdf) · [作者数据/代码仓库](https://github.com/ml-jku/lsc)

这是本轮发现的直接先例：ChEMBL 中原有的显式 activity comments 与删失数值已被整合为可训练的分子级 active/inactive benchmark。故不能主张“首次把结构化负测量或显式 Not Active 观测用于分子 ML”。

但边界同样重要：作者从 ChEMBL 结构化记录出发，并未建立从全文、表格/补充材料恢复尚未结构化遗漏记录的系统；没有比较原始 ChEMBL 与外部论文挖掘后的增量覆盖，也没有将实测 `Not Active`、按 potency 阈值推定的 inactive、删失区间和 unknown 作为不同证据类型做独立效用消融。其监督学习结果证明这些标签在模型训练中被实际使用，但没有“同数据去掉阴性标签”或类型匹配的消融，故不能据此断言实测阴性本身带来独立因果收益。这使候选贡献必须是“是否能从当前结构化资源之外找回高可信的、带出处/协议的观察”，并展示这些观察不是重复搬运后又改标签。

## 与“阴性数据”的关系：必须分层

| 观察类型 | 实际含义 | 能否直接称作阴性 |
|---|---|---|
| 明确报告 inactive / no activity，且有 assay 对象和判定标准 | 实验者按特定 assay 规则判定未达到活性标准 | 可称该 assay 下实测阴性，但应保留阈值和协议 |
| `IC50 > x`、`Kd > x` 等删失观测 | 数值落在阈值一侧，精确数值未知 | 不能一概而论；方向变换、实验目的、拟合失败规则都影响解释 |
| 没有正活性记录 | 可能未测、未报告、未入库或真正无效 | 不可据此推定阴性 |
| 人工构造 decoy / 随机配对 | 根据算法或抽样假设构造的负例 | 属于推定/合成负例，不是实测阴性 |

例如，作者报告某目标的 IC50 为 `>10 μM`，通常表示在规定实验范围内没有观察到更强的抑制，但若不同 assay 的阈值、质量控制、剂量反应曲线判定或测试浓度不同，这些结果并不能自动形成统一、可互换的 inactive 标签。Kd、EC50 与安全性/ADME endpoint 的 `<`/`>` 关系也不具有同一个生物学“负面”方向。

## 对当前研究设计的修正

1. 不把 `relation` 符号本身等同于 negative label；数据架构至少需保留原始测量类型、relation、阈值、单位、转换方向、assay/target、来源句段及判定规则。
2. 如果选 BindingDB 或 ChEMBL 的亲和力数据做 pilot，首先应把 exact、censored、显式 inactive/no-effect、not-tested/unknown 分开，抽样核验原文和数据库映射。
3. 模型实验应将“纳入删失回归标签”的现有方法作为强基线；阴性证据方案需额外比较其是否改善 assay-specific classification、校准、排序或跨 scaffold/时间/assay 泛化，而不是只报告训练样本增多后的总体分数。
4. 至少控制训练样本量、正负比例、相同测试集与结构/时间泄漏；另区分实测阴性、删失值和合成 decoy。否则无法归因于阴性证据的独立价值。
5. 这篇 2025 论文使用内部数据，公开代码适合方法学习与代码基线，不适合作为能完全重做的公开数据复现目标。

## 当前判断

证据支持：“删失实验观测可被分子模型学习，且在特定真实制药数据和不确定性任务中具有价值”；并且，至少在 ChEMBL20 基准中，结构化 active/inactive comments 与关系符阈值标签曾被用于百万级分子预测任务。

证据**尚不支持**：“所有删失值都是阴性数据”“这些结论可推广至公开文献抽取的显式阴性观察”“只要加入负例就能提高普通活性分类/泛化”。当前有价值的窄问题应落在记录级去重后的证据识别与 assay 语义 grounding、公共结构化源之外的真实增量覆盖，以及对各阴性证据类型进行受控下游评估。
