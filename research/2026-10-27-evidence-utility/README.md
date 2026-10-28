# 恢复证据的 RAG、训练与下游评价框架

2026-10-27。该目录接在 `sentence_v3` 内容验收之后，回答“恢复的叙述性阴性是否改善模型回答或预测”。2026-10-28已完成冻结真实数据上的RAG、三组LoRA困难固定选项评价和MG2Act外部检查。正式结论见 `正式用途评价总报告_20261028.md`。

当前结论：恢复证据相对结构化数据库和等长背景材料改善RAG回答，但弱于原文检索；平衡阴性LoRA没有提高57题准确率或降低过度推断；MG2Act六组均退化为相同常数预测，没有显示外部迁移增量。

## 入口与当前状态

双击 `检查下游框架.cmd` 查看缺失输入，双击 `准备下游任务.cmd` 冻结本地实验材料。两者使用 `workflow.example.json`，也可复制配置到 `local/` 后用命令指定。准备入口只做接入和冻结；API 生成、小模型训练和本地推理各有显式执行开关。

所有命令从本目录运行：

```powershell
python workflow.py check --settings workflow.example.json
python workflow.py prepare --settings workflow.example.json
python -m unittest discover -v
```

配置中的相对路径均以配置文件所在目录解析；训练模型路径相对于训练配置，模型评价路径相对于模型清单。输入尚未放置时，检查入口列出缺失路径，不生成科研结果。输出目录按批次新建，已有目录拒绝覆盖。

| 子系统 | 已实现行为 | 正式运行所需输入 |
| --- | --- | --- |
| 证据接入 | 验收检查、原文偏移核验、去重、来源隔离、修正轨迹保留 | 发布目录及相应冻结 workspace |
| RAG | 五组检索、冻结请求、预算、响应保存、断点续跑 | 冻结评价题、API 配置、独立账本 |
| 小模型 | 三组 LoRA 继续预训练、固定 token/更新数、checkpoint 恢复 | 可靠阳性/阴性/背景、保留评价题、本地基座 |
| 本地评价 | 基座与三个适配器使用相同问题和上下文 | 本地权重及模型清单 |
| 问答评分 | 盲化包、逐点评分、过度推断/引文评价、来源组 bootstrap | 有来源的参考答案与实际判定 |
| MG2Act | 官方划分与哈希核验、来源审计、数值预测、全测试/fine-test评分 | 已冻结官方 CSV、来源映射、预测结果 |

## 1. 数据接口与划分

`prepare.py` 读取发布目录中的 `acceptance_report.json` 和 `reliable_evidence.json`。要求内容验收已通过且 blockers 为空；记录需有 `content_decision=reliable`、`review_kind`、正文哈希、原句及逐字段出处、任务与响应哈希。`ready_for_training` 单独控制训练资格。待确认、排除和机械通过状态不会自动升级为训练资格。

```powershell
python prepare.py --release local/inputs/release --workspaces local/inputs/sentence_workspace --out local/bundle
```

多个历史 workspace 可同时提供；同一论文的不同来源哈希分别核对。来源文件、文档、引文偏移不匹配时停止接入。所有原始字段、条件、`review_kind`、人工或助手修正字段及 `original_record` 均保留。相同正文和相同字段的重复记录合并到 `duplicate_records`，异值记录保留供核查。

阳性与普通背景通过 `--supplements local/supplements.json` 接入，不从阴性排除项推断。JSON 数组中每条需要：

```text
evidence_id, kind: positive|background|structured, text,
paper_id, doi, source_sha256,
unit_id, quote, char_start, char_end,
review_status: reliable, review_kind, training_allowed: true|false
```

`field_evidence` 可补充对象/条件的原文引用；每个补充引用也核对原文偏移。`structured` 是已有数据库/通用提取的对照材料，需有来源和复核依据。普通背景是否混含目标阴性由内容复核明确判定。

DOI、论文别名、全文哈希、同一实验 ID、相同原句及已标记 `duplicate_group` 形成连通分组，整个分组只进入一个 split。默认 seed 为 20261027，按来源组约 70/15/15 分训练/验证/测试。已知跨论文的近重复须标记 `duplicate_group`；未知实验级关系不会由字符串匹配推定独立。

固定测试论文可通过 `--split-plan local/splits.json` 指定，格式为 `{"10.xxxx/doi":"test"}`，值允许 train/val/test；同一连通组中的冲突划分会报错。正式训练默认至少需 10 个独立来源组，且实际抽样后的训练/验证来源组分别不少于 3/1。五篇阶段保留为开发材料。

## 2. RAG 运行与问答评价

评价题 JSON 数组每条需要：

```text
question_id, question,
split: dev|test,
protocol: evidence_lookup|new_combination,
source_dois: [参考答案来源 DOI], evaluation_group: 来源分组 ID,
rubric: [{id: 评分点 ID, text: 判定规则}],
gold_status: assistant_reviewed|expert_reviewed,
reference_answer, reference_evidence: [用于判定的来源材料]
```

参考答案和评分点保存在评价层，生成请求只含问题和检索证据。开发题与测试题、已知事实检索与新组合预测分别报告。同一来源 DOI 的题须属于同一 `evaluation_group`。助手核对参考继续注明其身份。

五个固定对照组如下：

- `no_retrieval`：回答模型直接作答。
- `structured`：已有结构化资源检索。
- `raw`：相同结构化底座加全文正文/表图文字检索。
- `recovered`：相同结构化底座加阳性支撑与恢复阴性。
- `background_ablation`：相同底座与阳性支撑，以普通背景替代恢复阴性。

检索使用无需模型或向量服务的确定性 BM25。原文池来自所有可读正文单元，未按参考答案位置筛选。已知事实检索允许查对应论文；新组合预测只检索训练分区，排除题目来源 DOI 和来源不明记录。

默认结构化文本上限 3000 字符、额外证据上限 6000 字符；恢复组/消融组为阳性与阴性或背景分配相同上限。过长单元整条跳过并计数，完整单元不截断。`retrieval_audit.json` 保留实际长度及消融是否在 10% 长度差内。长度不足的题不能直接支持阴性的独立贡献。字符预算不是精确 token 预算，实际 usage 单列。

```powershell
python rag.py --bundle local/bundle --questions local/inputs/questions.json --config api.example.json --out local/rag_01
python run.py init-budget --ledger local/rag_budget.json --max-requests 100 --max-reserved-tokens 600000 --authorization "本轮用途实验预算"
python run.py run --out local/rag_01 --ledger local/rag_budget.json
# 正式生成时才加 --live；--env-file 只读取指定密钥，不执行文件内容。
python run.py run --out local/rag_01 --ledger local/rag_budget.json --env-file ../../.env --live --max-new-requests 10
```

生成继承现有账本和 SSE 适配器，保存请求、原始响应、哈希、模型和 usage。成功响应直接复用；不同实验组或工作区的请求完全相同时，从同一账本定位并核验成功原响应，复用不增加请求数。中断后已保存响应离线解析；未知请求不自动重发。403/429、未知响应、JSON/引用/返回模型合约失败会停止当前执行，已有历史和未完成任务留在导出分母。若服务返回版本化模型名，通过首次运行的 `--allowed-models` 明确固定允许列表，后续不得改变。

```powershell
python evaluate.py packet --trial local/rag_01 --out local/judging_01
# 将 blinded_packet.json 复制到 local 下填写 judgment；评分者不看 private_key.json。
python evaluate.py score --trial local/rag_01 --packet local/judging_01 --judgments local/completed_judgments.json --out local/qa_scores_01
```

判定逐点评价结论/必要条件，并填写过度推断、引文是否支持、评分者与理由。主内容分由来源判定，不用字符串命中或另一个模型赞同代替。报告同时给全部预期题分数、失败/未判定数量和完整配对结果。95% bootstrap 区间按来源组抽样；来源组不足时不生成区间。原文检索更好或阴性无增益时保留该结果。

## 3. 小模型训练和推理

默认沿用本机已有 `Qwen3-0.6B-Base`，LoRA 目标为 q_proj/v_proj，r=8、alpha=16。训练采用原文与条件支撑引用的同一种文本表达，目标是继续训练因果语言模型，保留作用边界；下游用问答和预测评价。

三组从相同训练分区抽样：`positive_only` 重复同一阳性集以匹配记录槽位；`domain_control` 为阳性加等量普通背景；`balanced_negative` 为 1:1 的阳性和阴性记录。数据不足时不复制阴性凑数；种子、基座、更新数、序列长度、batch 和累积步数固定。输入 token 数和实际预测 token 数严格由完整 block 计算；记录级 1:1 不等于 token 级 1:1，分类型 token 数和丢弃尾部均单列。

```powershell
python train.py prepare --bundle local/bundle --questions local/inputs/questions.json --config train.example.json --out local/training_material
python train.py run --material local/training_material --arm balanced_negative --out local/train_negative
# 查看 readiness 后，正式训练才加 --execute；已有 checkpoint 使用 --resume。
python train.py run --material local/training_material --arm balanced_negative --out local/train_negative --execute
python train.py run --material local/training_material --arm balanced_negative --out local/train_negative --execute --resume
```

阳性与普通背景缺失、来源组不足、评价题未冻结、测试题 DOI 进入训练/验证时，readiness 列出阻塞，执行训练会拒绝。通过 `--benchmark local/mg2act` 同时核对 MG2Act 验证/测试来源；统一 workflow 自动执行此检查。需要时先更新 split-plan 再冻结新 bundle。所有权重使用本地固定模型，不自动下载；checkpoint 绑定配置、数据和基座文件哈希，保存适配器、优化器与 RNG 状态。

`tokenization_report.json`、`training_metrics.json` 记录 token 组成、完整更新数和验证损失。损失用于排查训练，不作为任务增益指标。默认配置每组 100 个更新、每次 4 个长度 512 的 block，即 204800 个输入 token、204400 个 loss 目标 token。

本地自由生成入口保留用于诊断。正式LoRA比较使用困难固定选项和条件平均对数似然，避免JSON格式失败混入科学得分：

```powershell
python local_eval.py prepare --trial local/rag_01 --models models.example.json --out local/model_eval_01
python local_eval.py run --out local/model_eval_01
python local_eval.py run --out local/model_eval_01 --execute --max-new-tasks 10
python fixed_choice_eval.py prepare --questions local/questions.json --trial local/rag_trial --authored-options local/adjudicated_options.json --review-a local/review_a.json --review-b local/review_b.json --adjudications local/adjudications.json --out local/fixed_choice
python fixed_choice_eval.py run --eval-dir local/fixed_choice --base-model local/base_model --positive-adapter local/positive_adapter --domain-adapter local/domain_adapter --balanced-adapter local/balanced_adapter --out local/fixed_choice_results
```

输出的 `exports/answers.json` 与 RAG 共用判定入口。上下文超长或输出不符合 JSON 时保留失败；不悄悄裁剪或重写回答。`evaluate.py` 还计算 balanced_negative 相对于 base、positive_only、domain_control 的来源组配对增量。

## 4. MG2Act 接口

沿用已核查的 [MG2Act 固定版本 d3f9d1d](https://github.com/Zzy522/MG2Act/tree/d3f9d1da48be93d67cfc2be074c0cf0c6bdbb065)：907/125/127 原划分与 73 条 fine-test，原文件哈希和 fine-test UID/标签都校验。特征仅使用 SMILES、靶标/E3 名称、UniProt 和序列；Score、activity、sDC、pD、Dmax 编码留在评分层。

```powershell
python benchmark.py prepare --data-dir ../2026-10-26-mg2act-audit/local/upstream/MG_data --flags ../2026-10-26-mg2act-audit/benchmark_test_flags.csv --associations ../2026-10-26-mg2act-audit/source_associations.csv --config api.example.json --out local/mg2act --bundle local/bundle
# API 运行共用 run.py；本地基座/适配器也可复用这一套数值任务。
python local_eval.py prepare --trial local/mg2act --models models.example.json --context-arm structured --out local/mg_model_eval
python benchmark.py score --benchmark local/mg2act --predictions local/mg_model_eval/exports/answers.json --out local/mg_scores
python mg2act_local_eval.py prepare --benchmark local/mg2act --out local/mg2act_score_grid
python mg2act_local_eval.py run --eval-dir local/mg2act_score_grid --base-model local/base_model --positive-adapter local/positive_adapter --domain-adapter local/domain_adapter --balanced-adapter local/balanced_adapter --out local/mg2act_local_results
```

数值任务的 structured/recovered/background_ablation 都排除已知验证/测试来源 DOI，检索只使用训练分区。`overlap_audit.json` 列出隔离记录、来源未知和实验独立性未确定项。这里提供的是同一任务上的语言模型比较器；复现作者 ESM-C/GNN 架构可在其环境运行，将每条预测导出为含 `id,prediction` 的 CSV：

```powershell
python benchmark.py import-predictions --benchmark local/mg2act --csv-path local/author_predictions.csv --arm MG2Act --out local/mg2act_author_predictions
python benchmark.py score --benchmark local/mg2act --predictions local/mg2act_author_predictions/answers.json --out local/mg2act_author_scores
```

评分给全测试和 fine-test 的 MAE、RMSE、R²、靶标宏平均 MAE、覆盖率与配对变化。缺失预测保持缺失，并额外给出“缺失误差记为 1”的完整分母敏感性统计。Score=0 继续按作者分档任务解释，定性阴性不会被自动写成 Score=0。该任务衡量综合活性预测，来源问答另行评价引文、条件和过度推断；实验级独立性未建立前不宣称是新增阴性的独立预测收益。

## 验证与接续

测试包含来源篡改/偏移错误、来源连通分组、测试泄漏、黄金答案不进请求、未知/429 停止、成功续跑与已保存响应恢复、固定分母、三组平衡与 token 预算、随机微型模型实际优化、LoRA checkpoint 恢复、困难选项标签隔离、fine-test 和外部数值预测导入。正式用途实验已经执行，异常与不利结果均保留。

核心接入、检索、记账和评分使用标准库及现有提取模块；训练依赖见 `requirements-training.txt`。训练实现参考 [Transformers 因果语言模型接口](https://huggingface.co/docs/transformers/en/main_classes/trainer) 和 [PEFT LoRA](https://huggingface.co/docs/peft/en/developer_guides/lora)，本目录使用显式 PyTorch 更新循环以固定三组预算。

这意味着什么：接口、冻结数据和正式对照已经形成可复核闭环；结果支持RAG局部增量，不支持当前LoRA或MG2Act增量。

下一步应该做什么以完成总体目标：优先做少量专家抽查；若继续训练路线，在更大基座或多seed条件下复验，不重复当前RAG生成。
