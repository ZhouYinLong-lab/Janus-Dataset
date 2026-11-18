# 检索记录：成本收益

## 核心检索式

```text
(chemical OR reaction OR molecular)
AND (literature mining OR information extraction OR curation)
AND (cost OR time OR efficiency OR throughput OR human evaluation)
```

```text
(LLM OR agent OR NLP)
AND (chemistry OR scientific literature)
AND (manual OR curator OR expert)
AND (seconds OR minutes OR cost OR speed)
```

```text
(negative data OR failed experiment*)
AND (value OR utility OR performance OR prospective validation)
AND (chemistry OR materials OR bioactivity)
```

## 纳入与排除

优先纳入同时报告人工与自动流程、样本量、质量和时间/费用的研究。只报告 token 费用但忽略人工校验的不视为完整成本证据。其他科学或临床领域的成本研究可以帮助设计方法，但不直接用于估计化学专家成本。

## 试点需要自行产生的数据

- 文献获取成功率与许可状态；
- 候选命中率、有效阴性密度与重复率；
- 复核和争议仲裁时间；
- 按错误类型计算的返工成本；
- 数据增量带来的模型收益或少做实验的机会价值。
