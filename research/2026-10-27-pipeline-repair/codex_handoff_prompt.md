# Janus-Dataset 夜间续跑指令（给 Codex）

你在 D:\Projects\Dog\Janus-Dataset 工作。先读 AGENTS.md 和 .agents/skills/anti-defensive-writing/SKILL.md，然后按下面的状态继续，不要问我问题，不要停下来等确认。

## 当前状态（2026-10-28 凌晨）

- v1 复核完成：464 条中 reliable 385、pending 66、excluded 14；裁定与补二审记录在 research/2026-10-27-pipeline-repair/review_completion_20261027/。
- 框架 bundle_v4：1174 行（385 阴性 + 440 结构化 + 256 背景 + 93 MG2Act 阳性），64 个来源组，training_material_ready=True。
- RAG 五组已跑完并盲化评分（助手评分）：recovered 0.897、raw 0.799、background 0.316、no_retrieval 0.303、structured 0.291；recovered−raw=+0.10，CI 跨 0，不显著。
- 小模型训练 ready=True（三组各 116 训练 / 32 验证），但尚未执行。
- 关键文件：research/2026-10-27-pipeline-repair/ 下的 PLAN.md、后续任务.md、v1复核后接入状态、RAG五组盲化评分、MG2Act阳性接入与训练就绪；框架在 research/2026-10-27-evidence-utility/。

## 按优先级继续

1. 运行三组训练（positive_only、domain_control、balanced_negative），再做本地评价，报告任务层指标；损失只用于排查，不当增益。
2. 扩大 RAG 对照：增加题目与来源组，复核 recovered−raw 的 +0.10 是否稳定；补齐 structured/background 的召回审计。
3. 如时间允许，复核 MG2Act 阳性之外的 24 条 v1 阳性候选，或补阳性来源。
4. 每个完成的功能单元单独 commit，不 push；更新结果文档；最后写一份总结：完成了什么、没完成什么、下一步。

## 边界

- 不重置或改写已有账本；新实验用新账本并写明授权。
- 不把 key、原文、共享账户金额带入提交。
- 助手复核不等于专家金标，报告里保持这个口径。
- 遇到额度上限：干净停下，保留可续跑状态，写完总结再退出。
