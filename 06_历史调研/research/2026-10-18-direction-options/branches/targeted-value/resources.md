# 资源可用性与推荐使用次序

2026-10-18。只下载和读取公开文件、解析CSV、做计数；未安装、训练、推理或执行下载脚本。所有文件存于本目录`sources/`；原始网址与SHA-256见[来源清单](来源清单.csv)。

| 资源 | 本轮已实际取得 | 可直接做什么 | 暂不能声称什么 | 建议 |
| --- | --- | --- | --- | --- |
| Goldman酯酶 | [14,016配对CSV](sources/esterase_binary.csv)，146酶×96底物；3,076个1、10,940个0；含SEQ和分子SMILES；[解析脚本](sources/enzyme_reformat_esterase.py) | 审核原补充表空白后，做已知酶/未见底物的普通RF等负例数比较 | 现有0全都经本轮原始实验复核；这些标签是本项目新挖出来的 | **首选主面板** |
| Goldman腈水解酶 | [684配对CSV](sources/nitrilase_binary.csv)，18酶×38底物；85个1、599个0；[脚本](sources/enzyme_reformat_nitrilase.py) | 小型方向复核；读数为氨生成，按>0二值化 | 可支持所有距离层和严格骨架测试的高把握结论 | **只作辅助**；全表满足≥5阳性且≥16阴性的仅5酶，不能承诺充分训练/测试样本 |
| Goldman卤化酶NaBr | [2,604配对CSV](sources/halogenase_NaBr_binary.csv)，42酶×62底物；323个1、2,281个0；[脚本](sources/enzyme_reformat_halogenase.py) | 低转化/未命中负类的敏感性检查 | 所有0都是绝对非底物；与NaCl为独立家族复制 | 可选附加，**不混入严格非底物主结论** |
| AIC_Finder GPCR_3 | [63,643行CSV](sources/AIC_GPCR3.csv)，SMILES/Primary/Score/Confirmatory；确认字段缺失占多数 | 限定有复筛标签候选的质量审计；普通RF或读数基线比较 | 将61,465条初筛0且复筛缺失当复筛真阴性；全库假阴性评估 | **HTS再利用对照，不是论文新增恢复** |
| DataValuationPlatform | [25条元数据](sources/DVP_dataset_metadata.csv)、[预处理源码](sources/DVP_preprocessor.py)、[GPCR_3验证166条](sources/DVP_GPCR3_val.csv) | 确认AID对应、复筛形式与原划分偏好 | 该val代表随机测试；25集合证明定向阴性采样普遍有效 | val按初筛最高读数取10%，**应重建本问题的固定测试**；源码只读未运行 |
| CATNIP/BioCatSet1 | [反应表](sources/CATNIP_reaction_table.csv)、[README](sources/CATNIP_README.md)、论文全文；HF的3个SI Excel仅确认目录可见 | 新来源与实验分母线索 | 完整314×111正负矩阵已取得；未列出即失败 | **不列为即用阴性面板**；未加载pickle或模型 |

来源入口：[Goldman作者仓库](https://github.com/samgoldman97/enzyme-datasets)、[AIC_Finder](https://github.com/dahvida/AIC_Finder)、[DataValuationPlatform](https://github.com/JoshuaHesse/DataValuationPlatform)、[CATNIP](https://github.com/gomesgroup/catnip)、[CATNIP原数据目录](https://huggingface.co/gomesgroup/catnip/tree/main/raw_data)。Goldman为旧文/旧资源，明确不是新发现。HTS两个资源由相同研究团队产生且明显重叠，不计独立复制。

酯酶全表达到≥5阳性且≥16阴性的123/146酶，只是文件描述统计，**不能当训练区筛选资格**；实施时资格只能按训练信息决定。二值脚本的`>0`并不能排除原表NaN落入0，要先检查原表对应单元格，再决定哪些0有资格进主实验。

固定预算务必分两个口径：

1. **内容价值对照**：同种子阳性、同负例数、同RF、同测试，比实测随机/实测近邻/推定随机/推定近邻。事后从金标准筛真阴性属于oracle上限实验，不称等标签获取费用。
2. **实际获取对照**：候选完整标签未知时，花同样核查次数或人时，记录真阴性、阳性、歧义和重复全部产出。达到相同指标所需费用也是有效结局，便宜方法能替代不自动否定数据价值。

公开面板再利用、模拟标签恢复，与历史论文新增恢复是三种结果。只有提供现有资源去重清单、原文证据和新增记录资格审核后，才能报告第三种数量。当前本支路的**历史论文新增恢复量为0**。
