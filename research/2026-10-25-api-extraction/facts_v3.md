# 最小事实合约 v3

`facts_v3.py` 提供 `validate_facts(payload, job, candidates)`、JSON Schema 字典 `SCHEMA` 和填好的 `EXAMPLE`。本单元检查非结构化阴性恢复记录的类型、出处与候选归属；生物学解释仍进入语义复核。模块只使用 Python 标准库，调用过程没有文件、网络、环境变量或 key 访问。

## 调用者材料

每次传入一个 candidate，可返回多条观察。parent 负责准备和冻结原文：

```python
from facts_v3 import EXAMPLE, validate_facts

candidate = {"candidate_id": "SYNTHETIC:C1", "anchor_sentence_ids": ["S1"]}
sentence = {
    "sentence_id": "S1", "unit_id": "SYNTHETIC:U1",
    "text": "Synthetic analogues A and B did not improve target Z degradation relative to synthetic reference R; this does not establish inactivity.",
    "char_start": 0,
}
# 用实际字符串长度计算末端；偏移为原始 unit 内的 Python Unicode 字符索引。
sentence["char_end"] = len(sentence["text"])
job = {
    "paper_id": "SYNTHETIC_FORMAT_ONLY", "doi": None,
    "source_sha256": "synthetic-source-not-a-real-paper",
    "sentences": [sentence],
    "frozen_context": {"sentences": [sentence], "candidate": candidate},
}
result = validate_facts(EXAMPLE, job, [candidate])
```

以上 S1 是**明确合成的格式示例，非本项目实际数据、非专家金标**。示例 source hash 是占位符；正式调用由 parent 填入已校验来源的 SHA256。本模块透传来源身份，不读取来源文件验证其散列。

`job.sentences` 支持上述列表，以及 `{sentence_id: sentence_object}` 源句段映射。映射值可以省略 `sentence_id`；出现时必须与键一致。句段原文键支持 `text` 或 `quote`，同时出现时必须相同。`unit_id`、`char_start`、`char_end` 必须来自 parent，偏移为左闭右开且长度必须与原文一致；段落也可作为一个句段。

`frozen_context.sentences` 是实际提供材料的列表，可放完整句段对象或注册于 `job.sentences` 的 ID。完整对象的文本及位置必须与源映射一致。仅在源映射中、没有实际冻结提供的 ID 不可引用。重复 ID、错误偏移、冻结材料与源映射不一致均为调用者错误，抛出 `ValueError`。

`candidates` 为长度一的列表或元组。`frozen_context.candidate` 必须等于该候选；候选的 `anchor_sentence_ids` 为非空、不重复的字符串列表，顺序决定原文拼接顺序。缺失的锚句会进入 coverage notes，不自动补取。`paper_id`、`source_sha256` 必须为非空字符串，`doi` 可省略或为 null/非空字符串。调用者材料可保留额外元数据。

## 模型输出与提取提示词

将下面规则与 `SCHEMA`、`EXAMPLE` 一起用于 parent 的请求构造。模型只输出一个 JSON 对象：

```json
{
  "status": "observations",
  "reason": null,
  "observations": [{
    "values": {
      "subject": "Synthetic analogues A and B",
      "target": "target Z",
      "endpoint": "target Z degradation",
      "observation": "did not improve degradation relative to reference R",
      "comparator": "synthetic reference R",
      "scope_condition": null
    },
    "outcome_type": "not_improved",
    "evidence": {
      "subject": ["S1"], "target": ["S1"], "endpoint": ["S1"],
      "observation": ["S1"], "comparator": ["S1"], "scope_condition": []
    }
  }]
}
```

- 阅读实际提供的句段，恢复已经实施的实验观察。`observations` 至少一条；同一句不同终点或不同强度分别输出，保留组对象字符串，不擅自拆成各化合物。
- 六个 `values` 键全部保留，值仅为字符串或 null。没有依据的可选条件填 null；每个非空字段的 `evidence` 必须含至少一个已提供句段 ID。null、空串和空白串的 evidence 必须为 `[]`。
- 引用只输出句段 ID。禁止输出复制的引文、来源编号、paper/DOI、anchor、context flags 等额外字段；程序反查原文与位置。
- `endpoint` 使用原文支持的自由字符串。遇到表格必须读表头、图注及相应测定描述，再解释量化终点；`activity`、`potency`、`EC50` 词本身不能确定测定种类。程序不使用将所有 EC50 归入增殖的规则，也不改写终点。
- outcome 仅为 `not_observed`、`not_significant`、`reduced`、`not_improved`、`conditional_loss`、`reported_zero`、`uncertain`。保留实际强度；**无提高不等于无活性，未达统计显著不等于无作用**。`reported_zero` 仅用于原文明确报告的量化零值，不能由“未检测到”推导。
- 若对象、终点或观察尚不明确，可以在一条结构完整的观察中保留 null/不确定措辞和 `outcome_type: "uncertain"`，进入 `semantic_pending`。缺少 dose、浓度、时间或 Figure 本身不应使已经明确的核心观察整体弃答。
- 整个候选确实无法判断时输出 `status: "uncertain"`、非空 `reason`、`observations: []`；确认为未测试、预测、非实验阴性等时输出 `not_experimental_negative`、非空 reason 和空数组。程序保留 reason，检测声称 missing/omitted anchor 与实际冻结材料的冲突。

`SCHEMA` 规定 JSON 结构；字段内容与 evidence 的交叉约束、实际提供范围和锚句归属由 `validate_facts` 检查。非法 envelope 返回 rejected 与 unresolved，`accounting_complete=False`；单条非法观察隔离到 rejected，不丢弃同候选的其他合法观察。额外模型字段一律拒绝。

## 标准返回值

```python
{
    "accepted": [{"candidate_id": "SYNTHETIC:C1", "record": canonical}],
    "rejected": [],
    "unresolved": [],
    "coverage_notes": ["anchor_present"],
    "accounting_complete": True,
}
```

`accepted` 表示结构、句段 ID 与锚句连接校验通过，包含 `core_usable` 和 `semantic_pending` 两类记录。每个非空 observation 字段至少引用一条候选锚句；所有锚句必须实际提供。程序不通过字符串匹配证明字段的科学含义与原文一致。

canonical 固定保留：`values`、`outcome_type`、`field_evidence`、`source_sha256`、`paper_id`、`doi`、`candidate_id`、`record_key`、`anchor_sentence_ids`、`original_quote`、`record_status`、`expert_gold`、`semantic_review`、`ready_for_training`。

- 每个 `field_evidence` 项为 `{field, sentence_id, unit_id, quote, char_start, char_end}`，由可信句段生成完整引文和 unit 内偏移。
- `original_quote` 为候选锚句原文，按候选顺序用换行拼接；字段证据可额外引用同一冻结上下文的支撑句段。
- `record_key` 为规范 JSON 的 SHA256：包含来源 hash、论文、候选、全部六字段和 outcome。subject、target、endpoint、原文强度、比较对象、适用条件的变化会改变 key；字典键顺序不会改变 key。证据数组顺序不参与 key。逐观察输出，不去重、不合并；完全相同的观察可有相同 key。
- subject、endpoint、observation 均有内容且没有明确不确定标记，并且 outcome 不是 `uncertain` 时，标记 `core_usable`。仅有通用 endpoint `activity`、`potency` 或 `EC50` 进入 `semantic_pending`，保留原值。缺 target、comparator、scope_condition 不阻止核心可用；明确表达的 uncertain/unknown 等不确定词或缺核心字段会进入 `semantic_pending`。
- 所有记录固定 `expert_gold=False`、`semantic_review="pending"`、`ready_for_training=False`。

`rejected` 中的观察带 `candidate_id`、零起始 `observation_index` 和 `errors`。有效 `not_experimental_negative` 带 status、原 reason 和空 errors，是候选处置，不生成 record。所有观察均被拒绝时同时保留 `unresolved: no_valid_observations`。

`uncertain` 保留候选 status、原 reason 和 errors，进入 unresolved。已知缺图/缺可选条件单独导致弃答，或 reason 声称缺失的锚句实际已提供时，errors 明确含 `invalid_abstention_reason`，coverage notes 附具体原因；即使模型选择 `not_experimental_negative` 也转入 unresolved。真实缺锚句记录 `anchor_missing:ID`，不会误报为伪缺失。

reason 检测覆盖明确的英文 missing/omitted/absent/unavailable/not provided 等及中文缺失/缺少/未提供/省略，采用有限短语匹配。若 reason 同时明确陈述核心对象、终点或观察的缺口，则不把缺图直接认定为唯一弃答原因。此检测提示已知错误形态，剩余语义判断仍待复核；程序不据此创造观察。

`accounting_complete` 只表示该单候选的响应结构可逐项记账。有效 uncertain、非阴性处置、逐观察隔离都可以为 True，不能据此判断恢复完整、科学正确或已完成复核。

## 离线验证

在本目录运行：

```powershell
python -B -m unittest -v test_facts_v3
```

测试只使用合成材料，覆盖字段类型、合法空值、证据范围、程序引文、同句多观察、组对象、稳定身份、弃答检测、不确定终点和调用者材料完整性。`-B` 避免生成缓存文件。
