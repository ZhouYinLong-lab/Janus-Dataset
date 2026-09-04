# 检索记录：模型效用

## 核心检索式

```text
(negative OR inactive OR unsuccessful OR failed)
AND (chemical OR molecular OR reaction OR bioactivity OR materials)
AND (machine learning OR language model OR prediction)
AND (ablation OR benchmark OR validation OR performance)
```

```text
("negative data" OR "failed experiments")
AND ("reaction prediction" OR "target prediction" OR "materials discovery")
```

```text
(decoy OR "random negatives" OR "presumed inactive" OR "measured inactive")
AND (molecular OR virtual-screening OR bioactivity)
AND (bias OR comparison OR evaluation)
```

## 纳入与排除

必须有对照组，且能把含阴性数据的模型与 active-only、随机负例、decoy 或其他合理基线比较。只有训练集描述、没有消融的模型论文不能证明阴性数据的增量价值。随机切分结果可记录，但不能作为最终主证据。

## 待补检索

- 文献恢复数据与数据库现成阴性记录的直接对照；
- 负例上下文字段的消融；
- 时间外、实验室外和 assay 外的独立验证；
- 负例噪声率与模型收益之间的剂量关系。
