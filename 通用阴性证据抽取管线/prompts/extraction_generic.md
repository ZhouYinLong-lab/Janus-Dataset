# 通用阴性证据字段抽取

根据 adapter 提供的字段，将已经发现的候选转换为观察记录。所有非空字段都必须绑定当前 job 中实际提供的句子证据；没有证据的字段填 `null`。

必须遵守：

- 观察结果必须来自已做实验；
- `not_tested`、`not_reported`、`unknown` 不得编码成负结果；
- “未达到预期”“相对较低”“无可检测信号”和“精确为零”分别保留；
- 低表达、低稳定性、催化失活、检测失败和目标反应失败分开记录；
- 不把同一论文中不同实验的条件拼到一起；
- 不猜测图中没有读出的数值、单位、阈值或对象；
- 保留原文的比较对象和适用条件；
- 记录 evidence 的 `sentence_id` 和精确 `quote`。

输出 JSON：

```json
{
  "schema_version": 1,
  "job_id": "SUPPLIED_JOB_ID",
  "paper_id": "SUPPLIED_PAPER_ID",
  "status": "observations",
  "records": [
    {
      "record_id": "C1-R1",
      "outcome_type": "low_activity",
      "values": {
        "enzyme_or_variant": "Variant X",
        "parent_enzyme": null,
        "mutation": "A123V",
        "reaction_or_substrate": "substrate Y",
        "product_or_endpoint": "product formation",
        "assay": "HPLC",
        "experimental_condition": "37 °C, 2 h",
        "result_value": "8",
        "unit": "% conversion",
        "observation": "low conversion compared with the parent"
      },
      "evidence": {
        "enzyme_or_variant": [{"sentence_id": "S1", "quote": "..."}],
        "mutation": [{"sentence_id": "S1", "quote": "..."}],
        "result_value": [{"sentence_id": "S1", "quote": "..."}],
        "observation": [{"sentence_id": "S1", "quote": "..."}]
      },
      "qualifiers": []
    }
  ],
  "coverage_notes": []
}
```

如果候选无法确认，返回 `status: "uncertain"` 和空 `records`；如果确定只是未测试或未报告，返回 `status: "not_experimental_negative"` 和空 `records`。空结果不表示整篇论文没有阴性数据。
