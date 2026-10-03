# 酶学文献阴性证据标注规则 v0.1

**日期：** 2026-09-30  
**用途：** 建立小规模、来源可回链的人工评估集；当前只用于统一提取口径，不能代表整个酶学文献总体。  
**依据样例：** Godse et al. 2025（LpBgl5，清晰样例）、Heins et al. 2014（GH1 NIMS，条件级删失阈值）与 Mhaindarkar et al. 2018（BglM-G1，表格符号歧义样例）。

## 标注单位

优先以“来源中可辨认的一项具体 enzyme/variant × substrate × assay/protocol × 条件结果”为一条观察。若作者只给出一类底物的总括句，而无法分配到具体底物、变体或条件，则另记为**类别级陈述**；不复制成多条看似逐格确认的观察。跨条件结果分别保存，不能把同一酶永久标成 inactive。

## 结果状态

| 状态 | 纳入条件 | 不可做的推断 |
|---|---|---|
| `quantitative_zero_reported` | 原文明确报告数值 0 或相对活性 0，并能确认它对应测量结果 | 不等同于理论绝对零；没有报告检测限时不能补造 LOD |
| `censored_below_threshold` | 原文有方向和阈值，如 `<x`、低于背景/检测限，且语境表明是已做实验 | 不将阈值读数强行改为 0；保存原单位、关系符和阈值 |
| `qualitative_no_detect` | 原文明说未检测到活性、未发生水解、未观察到响应等，且指向已执行的 assay | 不泛化到未测底物、所有条件或整个蛋白功能 |
| `source_claim_only` | 作者给出类别级/汇总级阴性结论，但没有足够信息将其拆配到具体的底物、变体或 assay cell | 不复制成多个观察，不与表中空白符号逐格强行对齐 |
| `weak_or_relative_activity` | 只有低、弱或相对差的活性描述，未定义作者二元阴性标准 | 不自动二值化为 negative |
| `ambiguous_table_symbol` | 表格有破折号、空白或符号，但来源未定义其表示未测、未报告、未检出还是低于阈值 | 不转为 0、不算确认阴性；可保留相关正文类别级说法作为单独证据 |
| `not_tested_or_not_reported` | 来源明确说明未测/未报告，或实验设计/表格结构可确定该项不在测试范围 | 单纯未找到结果不能标为未测试 |
| `inferred_or_constructed_negative` | 由假设、未标注池、结构 decoy、随机负例或算法推定产生 | 不与实验测得阴性合并统计 |

## 必须分开的字段

- **原文证据**：短语、表格原值/符号、图表编号及页/行/列位置；保持作者措辞和单位。
- **实体**：蛋白/基因、突变体/异构体、accession 及其版本；近缘同源物不自动视为同一实体。
- **底物**：保留原始名称和可解析的规范名；相似名称或同一底物类别不可代替精确配对。
- **Assay 语境**：底物浓度、酶量、缓冲液/pH、温度、时间、读数/检测方法、阈值/LOD、重复数和阳性/阴性对照。原文未给字段记 `not reported`，不要用领域常见条件补齐。
- **证据粒度**：数值单元格、定性句、类别级概括、图像/曲线、补充材料行分别标记；同一结论的多个载体可互相佐证，但不能重复计数成独立观测。
- **覆盖状态**：与数据库匹配至少分为 exact same observation/source、same entity+substrate qualitative evidence、entity only、unresolved、not found under documented query。`not found` 必须记录数据库版本、查询键和覆盖边界。

## 双层判定与分歧处理

第一层只判断“作者是否明确报告某种阴性结果”；第二层判断“能否把它可靠地分配成逐条可训练观察”。类别级句子可能通过第一层，而其表格符号在第二层仍是歧义。抽取者分歧需保存各自原文依据和裁决理由，不允许只留共识标签。后续评估应报告按证据类型分层的 precision/recall、实体/底物/条件字段完整度、未决比例和人工复核时间；便利样本与困难样本分别报告，不能混成一个代表性准确率。

## 当前样例的示范裁定

- **LpBgl5：** 两种 pNP glycoside 的表格相对活性 0、正文 no activity detected → `quantitative_zero_reported`；arbutin 与 cellobiose TLC 至 96 h 未见水解 → `qualitative_no_detect`。LOD 未给，不能称绝对无活性。
- **BglM-G1：** 完整原文的 α-glycoside no-detect 句位于 BglM-G1 专属 Results 小节，Table 1 列出两种对应α底物；因此 wild type 的两个底物可记为正文支持的 `qualitative_no_detect`（NP005/NP007），但仍不能把破折号转成数值0。H75R在后续段落引入，不能自动继承该句；其两个破折号继续记为 `ambiguous_table_symbol`（NP006/NP008）。类别级 claim NP015仍单独保留，不重复计为观察。
- **Heins NIMS：** BAE87008.1/Q25BW5 × cellobiose 有 6 个 pH 5/8 × 60/80/90°C 的 `<0.1` 源单元格，背景转换率为 0.1 → `censored_below_threshold`；保留条件和重复数，不转成 0。它们是一个蛋白–底物配对的六个条件观察，不是六个独立pair。

## 版本与限制

这是基于三篇有意选择的示范性文献形成的 v0.1，不是系统标注手册或验证过的 ontology。下一步需纳入正文分散、补充表/图像型及明确“未测试”样本，再由第二名标注者盲标并做冲突裁决。当前不得报告总体 prevalence、自动抽取准确率或模型收益。
