# 检索记录：问题是否存在

## 概念块

- 阴性结果：`negative result`, `failed experiment`, `inactive`, `non-binder`, `no reaction`, `null result`, `dark data`
- 数据缺口：`publication bias`, `reporting bias`, `missing data`, `dataset bias`, `coverage bias`, `selective reporting`
- 分子领域：`chemistry`, `molecular science`, `bioactivity`, `reaction`, `synthesis`, `materials`, `assay`

## 核心检索式

```text
("negative result*" OR "failed experiment*" OR inactive OR "no reaction" OR "dark data")
AND (chemistry OR molecular OR bioactivity OR synthesis OR materials)
AND (dataset OR database OR literature OR reporting)
```

```text
("publication bias" OR "reporting bias" OR "coverage bias" OR "dataset bias")
AND (chemical OR molecular OR bioactivity OR reaction)
```

```text
(inactive OR negative OR counter-screen*)
AND (ChEMBL OR PubChem OR "high-throughput screening" OR "chemical biology")
AND (database OR benchmark OR dataset)
```

## 纳入与排除

纳入能够说明阴性数据是否被保存、如何定义、是否带实验上下文的原始研究或数据库论文。单纯讨论类别不平衡但不说明阴性来源的论文，只作为背景证据。临床医学中的发表偏倚不直接外推到分子科学。
