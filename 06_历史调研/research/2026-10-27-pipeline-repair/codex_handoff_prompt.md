# Janus-Dataset 续跑指令（2026-10-28 更新）

你在 D:\Projects\Dog\Janus-Dataset 工作。先读 AGENTS.md 和 .agents/skills/anti-defensive-writing/SKILL.md。不要问我问题，按下面状态继续，直到额度用尽再干净停下。

## 当前状态（02:35 夜间续跑刚结束）

- 三组 LoRA 训练已完成：positive_only、domain_control、balanced_negative，各 100 updates、204,800 输入 token，adapter 已保存。
- 本地评价 78 题 × 4 模型 = 312 任务全部 invalid_response（json_or_citation_contract），0 条有效；不能据此说训练无效。
- RAG 扩展已离线准备：57 题、10 个来源组、285 个任务；第一个真实请求结果未知（needs_attention），未重发；状态可续跑。
- 结果文档已提交：小模型三组训练与本地评价_2026-10-28.md、RAG扩展续跑结果_2026-10-28.md、夜间续跑总结_2026-10-28.md。

## 按优先级继续

1. 修小模型评价：给 Qwen3-0.6B 增加 JSON/引用格式适配，或改用可评分的选择/排序任务；重新冻结协议后比较三组。
2. 续跑 RAG 扩展：先查 rag_v4exp_20261028/state.json 的未知请求与独立账本；未知不重发；补齐 285 个真实回答并盲化评分，复核 recovered−raw 的 +0.10 是否稳定。
3. 有余力再复核 MG2Act 之外的 24 条 v1 阳性候选。
4. 每个完成的功能单元单独 commit，不 push；更新结果文档；最后写总结。

## 边界

- 不重置或改写已有账本；新实验用新账本并写明授权。
- 不把 key、原文、共享账户金额带入提交。
- 助手复核不等于专家金标。
- 遇到额度上限：干净停下，保留可续跑状态，写完总结再退出。
