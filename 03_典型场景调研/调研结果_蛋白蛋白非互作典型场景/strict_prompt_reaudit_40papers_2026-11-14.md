# 蛋白—蛋白非互作：严格提示词扩展复核（40篇富集样本）

## 复核结论

原样本清单实际包含40篇论文，不是旧报告所写的30篇。40篇中29篇产生了关键词候选句；按新提示词逐条排除Figure/Table/补充材料、明确数值结果、结构化结果复述、技术对照、推测和重复后，保留6个独立证据块，分布于6篇论文，可展开为8条蛋白对或构建体级记录。

## 严格抽取结果

[1]

Evidence:

"Dimeric UL16 did not bind MICB and could not be converted to monomer by incubation with reducing agents."（来源位置：PMC2797645，Methods，Expression and purification of UL16。）

Description:
二聚体UL16不与MICB结合，且还原剂处理不能将其转化为单体。

[2]

Evidence:

"Both full-length BICDR-1 and an N-terminal region of BICDR-1, amino acids 1–353, interact with the C-terminal tail domain of Kif1C, amino acids 811–1090 and not with other tail regions of Kif1C or other kinesin motors, such as Kif5 (Figure 7A; data not shown)."（来源位置：PMC2876961，Results，Kif1C participates in transport of secretory vesicles in neurons。）

Description:
BICDR-1全长及其N端区段不与Kif5互作；该部分结果标为“data not shown”。

[3]

Evidence:

"Under similar conditions, C4BP did not bind to either immobilised CD95 (Fas) or CD178 (Fas Ligand) and did not affect the ability of immobilised CD95 to bind soluble CD178 (Data not shown)."（来源位置：PMC1764644，Results。）

Description:
在原文所述相同实验条件下，C4BP既不与固定化CD95结合，也不与固定化CD178结合，并且不影响固定化CD95与可溶性CD178的结合。

[4]

Evidence:

"Unlike NusG, RfaH reduces pausing at hairpin-dependent sites, does not bind to Rho (IA, data not shown), and only acts on operons that encode a 12-nt long ops element."（来源位置：PMC2995049，Introduction。）

Description:
RfaH不与Rho结合；原文将该结果标为“data not shown”，未报告具体测量数值。

[5]

Evidence:

"In our hands however, Prdx2 did not bind PTEN, as we were unable to detect an interaction of Prdx2 and PTEN by immunoprecipitation (data not shown)."（来源位置：PMC2688529，Discussion。）

Description:
作者通过免疫沉淀未检测到Prdx2与PTEN之间的互作，结果未在图表中展示。

[6]

Evidence:

"Both APC10 D2 and APC10 D9, when expressed in yeast as fusion proteins of B42, failed to bind the LexA fusion protein of Smad3 in the yeast-two hybrid system (data not shown)."（来源位置：PMC420458，Results。）

Description:
在酵母双杂交体系中，以B42融合蛋白表达的APC10 D2和APC10 D9均未与LexA-Smad3融合蛋白结合。

## 数量与质量

| 指标 | 结果 |
|---|---:|
| 样本清单 | 40篇 |
| 产生关键词候选的论文 | 29篇 |
| 严格有效证据块 | 6 |
| 严格命中文献 | 6篇 |
| 文献命中率 | 15.0% |
| 平均证据块密度 | 0.15块/篇 |
| 实体/构建体级记录 | 8 |

按可复核信息完整性分级：PMC1764644、PMC2876961、PMC2688529和PMC420458共4块明确给出对象、实验语境或方法及阴性结果，质量较高；PMC2797645和PMC2995049共2块虽是真实正文独有结果，但未在同一句中完整交代结合检测方法，质量中等。没有将低信息量推测计入数量。

## 对旧16条结论的纠正

旧报告保留的16条中，大部分其实是正文对Figure、Supplementary Figure、pull-down、免疫印迹或结构结果的解释；新提示词明确要求结果本身不能已被结构化记录，因此这些机制说明不能再作为新的阴性样本计数。旧报告还把40篇样本误写成30篇。旧“16条、11篇命中、0.53条/篇”的结论废止，以本报告的“6块、6篇命中、0.15块/篇”为准。

## 可行性标签

**失败。** 该方向证明了正文独有阴性证据确实存在，但在已经用Negatome定向富集的样本中仍只有0.15块/篇；同时现有PPI benchmark主要评价平面蛋白对，不能直接承接第三方因子、构建体和状态条件。它可保留为抽取方法的案例方向，不应作为当前申报书的主场景。

