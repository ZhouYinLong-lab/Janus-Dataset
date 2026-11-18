# BglM-G1：表格破折号与正文阴性陈述的歧义审计

**初审日期：** 2026-09-30；**全文复核：** 2026-10-01  
**关联度：** 3/3（直接测试文献中的底物阴性如何表示，以及抽取时怎样避免将缺失值误读为零）  
**定位：** 与 LpBgl5 清晰易读样例配对的困难案例；用于发现标注歧义，不估计总体抽取性能。

## 来源和可确认内容

Mhaindarkar 等 2018 年在 *Communications Biology* 报道 GH1 β-glucosidase BglM-G1 及其 H75R 变体。[PMC全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC6192996/)，[PubMed记录](https://pubmed.ncbi.nlm.nih.gov/30345395/)，DOI [10.1038/s42003-018-0167-7](https://doi.org/10.1038/s42003-018-0167-7)。

完整 Results 的段落结构进一步限定了这句证据的实体范围：在“The metagenomic protein BglM-G1 is a bona fide β-glucosidase”小节中，作者先介绍 BglM-G1 的底物实验，随后写“tested substrates that contained α-glycosidic bonds”未检测到活性。Table 1列出 p-nitrophenyl-α-D-arabinofuranoside 与 p-nitrophenyl-α-D-rhamnopyranoside。因此这两种底物的 BglM-G1（野生型）观察可记录为**正文级、面板范围的定性阴性**；但该句不应在没有额外证据时自动扩展至 H75R。Table 1中BglM-G1和H75R的四格仍都是破折号，作者没有在可见表注中定义破折号。H75R是在随后独立段落才引入，作者称其底物特异性与野生型“comparable”，但该概括不足以给两个具体H75R单元格定性。Methods表明底物特异性实验使用2 mM底物、50 mM sodium citrate（pH 6.0）、45°C，酶量范围为2.0–207.0 pmol；分光测定p-nitrophenol、设相应底物空白、至少三次技术重复。该酶量范围不是每个底物/变体对应的具体用量。

## 抽取边界

| 层级 | 可记录内容 | 不应推断的内容 |
|---|---|---|
| 正文陈述 | BglM-G1小节报告受测α-糖苷键底物未检出活性；可映射到列出的两种底物 | 不应无依据地把该句扩展到H75R，也不能推断所有α-糖苷或所有条件下绝对无活性 |
| 表格单元格 | 两种底物 × 两种蛋白变体共有四个“–”；BglM-G1两格另有对应的面板级正文支持，H75R两格无明确逐格或明确面板结果 | H75R破折号仍可能表示未检出、未测或未报告；没有表注定义时不能把它改写成0 |
| 条件 | 2 mM；pH 6.0 citrate；45°C；分光读数；底物空白；至少三次技术重复 | 逐单元格 enzyme pmol、反应时间点、检测限及原始重复值没有从本次来源核出 |
| 生物学解释 | 在作者所述测试范围内，α-糖苷阴性与多种 β-糖苷底物的正活性并存 | 不能将特定底物阴性改成蛋白整体 inactive |

因此，标注应拆成两条已被作者正文支持的BglM-G1定性阴性（NP005、NP007），以及两条H75R破折号歧义项（NP006、NP008）。即使对BglM-G1，也不要把作者报告的“未检出活性”误写成数值0或有已知LOD的测量。这个案例适合困难评估层：测试流程是否能借助段落标题和上下文正确确定主语，同时不把组级结论越界传播到变体。逐行状态同步至 [`annotation_pilot_v0.csv`](pilots/enzyme-negative-literature/annotation_pilot_v0.csv) 和 [`database_coverage_adjudication_v0.csv`](pilots/enzyme-negative-literature/database_coverage_adjudication_v0.csv)；本轮没有进行BRENDA/SABIO等数据库交叉核查。

## 数据库交叉核验状态

本文研究对象 BglM-G1 是根据 GOS metagenome 序列合成的蛋白；正文报告其与 GenBank KRO51423 的同源蛋白有 99% 序列同一性。这个近缘 accession 不是自动等同于受测构建体。为避免把实体层近似匹配写成 observation coverage，本轮没有将任何 BRENDA 结果计为已覆盖或数据库新增。LpBgl5 的另一条 BRENDA 精确序列查询也尚未返回可解释结果，见 J043 的 crosswalk 状态；该超时不构成阴性覆盖证据。

## 对当前研究判断的影响

与 LpBgl5 清楚的“0 relative activity/no hydrolysis”不同，BglM-G1 例子显示现实文献可能同时出现正文层明确结论、表格破折号和不完全逐记录条件。若流程只做关键词匹配或将空值统一转 0，会制造虚假的观测。下一步的小型 source-linked 评估集应至少区分：数值零、明确低于检测限、正文明确无活性但表格符号未定义、未报告/未测、推断负例；并记录证据粒度、酶/变体、底物、assay 条件和需要人工判定的字段。

本文并不回答阴性样本是否改善模型，也未证明文献抽取具有数据库独有覆盖。此处直接贡献是标注规范和误差分析设计，不能扩大为模型效用或项目创新性证据。
