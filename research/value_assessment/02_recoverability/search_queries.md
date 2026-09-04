# 检索记录：可恢复性

## 核心检索式

```text
("chemical literature" OR "scientific literature")
AND (extraction OR mining OR "information extraction")
AND (negative OR failure OR unsuccessful OR inactive OR "no reaction")
```

```text
(chemistry OR reaction OR bioassay OR materials)
AND (LLM OR "large language model" OR NLP OR multimodal)
AND (extraction OR curation)
AND (precision OR recall OR benchmark OR evaluation)
```

```text
("supporting information" OR table OR figure OR full-text)
AND (reaction OR assay OR property)
AND (extraction OR parsing)
```

## 纳入与排除

优先纳入有人工金标准、明确样本量以及 precision/recall/F1 的原始研究。只展示若干成功示例、没有测试集或不保留来源定位的系统不能作为可靠性证据。一般化学抽取论文可证明基础可行性，但标记为 `partial`，不能替代阴性语义专项基准。

## 待补检索

- 否定范围识别、hedging 与检测限抽取；
- 补充信息中的 failed/no-conversion/no-product 记录；
- 跨图表、正文和化学结构图的 observation linking；
- 专家复核后的文档级召回率，而不仅是字段级平均分。
