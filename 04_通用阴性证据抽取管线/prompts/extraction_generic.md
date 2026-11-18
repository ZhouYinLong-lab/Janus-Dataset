# 严格的非结构化阴性证据字段抽取

只把已经实施的实验观察转换为记录。所有非空字段必须绑定当前 job 的真实句子；缺失字段填 `null`，不得根据图、常识或上下文猜测。

## 可训练记录的目标关系

```text
具体酶/变体
  + 具体反应/底物
  + 实验条件
  + 功能端点
  + 数值结果或明确的定性失败
```

## 严格区分

- 生化结果与表达/纯化/稳定性流程问题；
- 生化结果与检测失败、无法拟合、无法测量；
- 生化结果与 DFT、QM/MM、结构建模失败；
- 真实阴性与未测试、未报道、未知；
- 正文自然语言增量与 Figure/Table/SI 的复述或指针；
- 本文实验与引言引用的既往研究。

低活性、低产率、低选择性和相对下降优先填写数值。没有数值但原文明确写出 `no product`、`not detected`、`trace product` 等定性结果时，在 `qualifiers` 中加入 `explicit_qualitative_result`。

输出 schema_version 2：

```json
{
  "schema_version": 2,
  "job_id": "SUPPLIED_JOB_ID",
  "paper_id": "SUPPLIED_PAPER_ID",
  "status": "observations",
  "records": [
    {
      "record_id": "C1-R1",
      "outcome_type": "low_activity",
      "record_kind": "biochemical_observation",
      "incremental_status": "narrative_increment",
      "values": {
        "enzyme_or_variant": "Variant X",
        "parent_enzyme": "Parent enzyme",
        "mutation": "A123V",
        "reaction_or_substrate": "substrate Y",
        "product_or_endpoint": "product formation",
        "assay": "HPLC",
        "experimental_condition": "37 °C, 2 h",
        "result_value": "8",
        "unit": "% conversion",
        "observation": "8% conversion, lower than the parent"
      },
      "evidence": {
        "enzyme_or_variant": [{"sentence_id": "S1", "quote": "..."}],
        "parent_enzyme": [{"sentence_id": "S1", "quote": "..."}],
        "mutation": [{"sentence_id": "S1", "quote": "..."}],
        "reaction_or_substrate": [{"sentence_id": "S1", "quote": "..."}],
        "product_or_endpoint": [{"sentence_id": "S1", "quote": "..."}],
        "assay": [{"sentence_id": "S1", "quote": "..."}],
        "experimental_condition": [{"sentence_id": "S1", "quote": "..."}],
        "result_value": [{"sentence_id": "S1", "quote": "..."}],
        "unit": [{"sentence_id": "S1", "quote": "..."}],
        "observation": [{"sentence_id": "S1", "quote": "..."}]
      },
      "qualifiers": []
    }
  ],
  "coverage_notes": []
}
```

模型输出即使通过格式和引文校验，也只能进入 `pending`。人工裁决确认语义、增量性和字段完整性后，管线才允许其成为训练候选。
