# 一个已经回到原文核实的蛋白降解例子

日期：2026年10月20日。本例用于选择垂域和说明字段补全，不是新发现或模型性能实验。

原始论文：[Development of PVTX-405 as a potent and highly selective molecular glue degrader of IKZF2 for cancer immunotherapy](https://doi.org/10.1038/s41467-025-58431-z)，2025，开放原文存为[sources/TPD_example2025.xml](sources/TPD_example2025.xml)。已检查Table 1、选择性结果段和Methods的HiBiT degradation assay；未独立量化图像，未检查全部补充材料。

## 原文中的正负结果

Table 1将compound 5的多个靶标结果放在同一表中：IKZF2的DC50为9.7 nM、Dmax为70%；GSPT1的DC50为>10 μM、Dmax为0%。结果段说明在测试浓度至10 μM时，compound 5没有诱导IKZF1/3、GSPT1和CK1α的显著降解；这句话不能改写成其每个靶标的数值均为0。

DC50表示达到50%降解所需浓度，Dmax表示报告的最大降解比例。单独看到DC50大于测试上界，不能认定没有任何降解：同一表中其他靶标也有DC50 >10 μM，但Dmax是非零值。GSPT1本条同时有表格报告的Dmax 0%，仍应保留为该实验范围下的结果。

## 假设已有Excel仅保留化合物、靶标与数值

可以从原文补入：招募蛋白CRBN，表注指定的HiBiT降解测定，方法中的HEK293细胞，给药处理6 h，测试浓度范围0.017 nM至10 μM，以及DC50与Dmax各自的单位和关系符。每个字段保留位置，不能将此实验的细胞和时间套用到文中其他检测。

本例中并未检查用户的实际Excel，故这里是已有字段不足时的示范，不是已经确认用户漏提取了这些字段。

## 现成参照实际可读

作者的[提取工作预印本](https://arxiv.org/abs/2605.11221v1)及[公开仓库](https://github.com/yaochenr/LLM-TPD-Extraction)提供了专家参照。已实际下载并解析：

- [分子胶专家表](sources/TPD_GT_Glues.csv)：104行、7个不同DOI。
- [PROTAC专家表](sources/TPD_GT_PROTAC.csv)：209行、15个不同DOI。

两表各19列，包含化合物、靶标、招募蛋白、测定、细胞、DC50、Dmax及时间等。上述compound 5—GSPT1记录已在分子胶表中，不能计作我们新增恢复的阴性；它的意义是提供可查原文的校验题。作者标注也不是不可质疑的真值，仍需抽样回查。

静态检查发现两表都保留边界符号、范围、近似值和缺失。104行分子胶表中DC50缺14项、34项以比较或近似符号开头；209行PROTAC表中相应为5项和42项。这些是字符串形式统计，不能计作阴性数量，也未证明缺失字段都能从原文恢复。具体下载URL、日期和SHA256见[source_manifest.json](source_manifest.json)。

README明确代码MIT、派生结构化数据CC BY 4.0；上游论文及数据库适用各自条款。GitHub API本轮403，但网页与raw下载可用，不将API失败写成资源不存在。

## 对应的下游问题

RAG可测试：“这篇研究是否支持compound 5能降解所有CRBN相关靶标？对GSPT1的测试范围与结果是什么？”回答应引用Table 1和方法，区分目标、边界与条件。

小参数语言模型若后续训练，可学习这类带条件的事实问答、结果比较与证据适用范围判断。闭卷记住训练记录不等于泛化到新化合物；给定证据回答未见论文的问题，也与闭卷知识记忆属于不同任务，应分别评价。训练方式和模型保持未定。
