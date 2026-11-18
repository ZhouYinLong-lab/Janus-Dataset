# CRBN叙述性阴性用途小试验

先读[结果报告](结果报告.md)，再查[缺口核查](缺口核查.md)和[推进记录](推进记录.md)。本轮已经结束：5篇、20题、15次生成、56份文本、16道三组完整题。没有训练或自动push。

可复用文件：`reviewed_cases.json`保存卡片、题目和原文位置，`manual_judgments.json`保存逐题评分依据，`逐题评分.csv`便于筛选，`results_summary.json`保存配对汇总，`引用核查.csv`保留引用错误。来源版本和哈希见两个manifest，冻结前资料长度与预算见 `preflight_summary.json`。

本机的原文、基线副本、完整请求/响应/事件、冻结任务都在被忽略的 `local/`。实际调用账本继续使用 `../2026-10-25-api-extraction/local/round_01_budget.json`，当前暂停。`local/trial_01/summary.json`是自动导出状态，正式评分见公开 `results_summary.json` 的 `graded=true`，两者含义不同。

从仓库根目录复查已有结果（不发生成请求）：

```powershell
D:/Environment/Miniconda3/python.exe research/2026-10-26-crbn-rag-pilot/pilot.py export --out research/2026-10-26-crbn-rag-pilot/local/trial_01
D:/Environment/Miniconda3/python.exe research/2026-10-26-crbn-rag-pilot/evaluate.py
D:/Environment/Miniconda3/python.exe research/2026-10-26-crbn-rag-pilot/audit_citations.py
```

离线保护检查使用隔离模拟账本：

```powershell
D:/Environment/Miniconda3/python.exe -m unittest discover -s research/2026-10-26-crbn-rag-pilot -p test_pilot.py
```

`collect_baselines.py`固定通用工作版本并筛选DOI；`curation.py`重建助手核对材料；`pilot.py`负责冻结任务、检索、批量回答和导出。每次真实请求之前预留原共享预算，成功或未知请求均不自动重发。后续实验需明确新的问题与评价设计，不把本轮开发题继续称为独立测试。
