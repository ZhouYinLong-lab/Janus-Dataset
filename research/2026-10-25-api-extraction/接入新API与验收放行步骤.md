# 接入新 API → 五篇试跑 → 验收放行 → 全库提取

整理日期：2026-10-27。本文件只给操作顺序和命令，不发起任何请求。以下命令都在 `research/2026-10-25-api-extraction/` 下执行。

## 2026-10-27 当前试跑接续

已建立第二轮 `local/round_02_budget.json`，五篇 `local/sentence_v3_ws_pilot` 已绑定该账本。点击入口现在优先读取已有工作区的绑定；即使 `sentence_launch.json` 仍留旧账本路径，也不会拿旧账本恢复本次试跑。准备/启动前若五篇与全库工作区绑定不同账本，入口会停止并显示冲突，保留各自历史。

验收报告存在但未通过时，点击启动仍会续跑五篇；只有报告中 `passed` 为布尔 `true` 才进入全库放行校验。

`句段-查看进度与结果.cmd` 直接从当前任务工件读取状态，显示四类论文、完成分块、记录数、停止原因及共享用量。打开的Markdown是最近一次自动导出，实时状态以控制台为准。查看进度不发送生成请求。

用户已取消固定200次和额度不足需反复询问的限制；实际用量继续记账，旧请求不清零。当前优先完成五篇管线检查，暂不运行RAG/训练或直接扩到全库。下文保留首次API接入的操作参考，已有工作区应续跑，不重复prepare或创建账本。

## 代理连接故障的修复入口

本机2026-10-27实测：通过 `127.0.0.1:7890` 代理访问模型列表发生SSLEOFError，直连同一个API返回HTTP 200。若五篇因连续网络失败暂停，可双击 `句段-修复连接.cmd`，或运行：

```
python sentence_launch.py repair
```

修复只发送模型列表GET，不发送生成；取得同服务、同模型的直连可达证据后，记录诊断及恢复事件，并在 `local/sentence_launch.network.json` 保存该API的连接设置。随后双击原来的 `句段-启动或续跑.cmd` 即可接续。入口在提取子进程的NO_PROXY中加入该API域名，不修改系统代理、冻结模型配置或原任务标识。未知请求和依赖范围继续阻止重发，成功请求继续复用。

修复前取得账本和工作区运行锁；已有提取进程时拒绝操作。直连诊断失败或模型未列出时，保留停止状态。API或模型改变后，旧直连设置失效，需要对新配置诊断。

需要限制一次验证的新增请求数时，可使用 `python sentence_launch.py run --max-new-requests 3`；这是本次启动的请求数限制，累计用量继续写入原绑定账本。

## 0. 先看清两件事

1. **额度是本地文件，不是平台限制。** 上限写在 `local/round_01_budget.json`，由 `batch_budget.create` 于 2026-10-25 21:42 创建，授权字段原文：「用户明确回复：授权全流程，上限200次生成；对应提问含800万token预留。旧B022未决请求不重发。」`max_requests=200`、`max_reserved_tokens=8,000,000`，当前已用 200/200。该文件记录已花请求，不能重置；换额度等于新建一个账本文件，旧账本保留不动。
2. **全库工作区已准备好**：`local/sentence_v3_ws_full` 收 193 篇（27 篇有 XML 全文 + 166 篇缺全文），492 个发现任务。全库付费运行被「五篇验收」锁住；验收需要真实生成，所以顺序固定为：接 API → 跑五篇 → 复核 → 验收 → 放行全库。

## 1. 接入新 API（只改两个文件）

- `.env`：写一行 `JANUS_API_KEY=你的key`。若改 `api_key_env` 名称，两边一起改；同一文件只放这一条赋值。
- `config.local.json`：`base_url` 改你的服务地址（必须 https；localhost 测试允许 http），`model` 改实际模型 ID（不能含 `REPLACE_`）。
  - `max_requests` 是**单个工作区**的请求上限，不是总额度；全库请按 27 篇的发现+事实+按需条件预估后设大（例如 5000）。
  - `max_reserved_tokens` 是**单工作区**的保守 token 上限，按需设大（例如 50,000,000）。
  - `timeout_seconds`、`max_output_tokens`、`output_token_parameter`（`max_tokens`/`max_completion_tokens`）、`response_format`（`json_object`/`none`）按服务能力填。
  - 配置键必须恰好是这九个，多一个少一个都会被 `check_config` 拒绝；密钥只从环境读，不写进配置。
- **换 API 要在第一次真实运行前完成。** 第一次运行会生成 `candidate_state.json` 并绑定 config（含 base_url/model）；之后再改配置会被 `IntegrityError: Stored config changed` 拒绝。当前两个工作区都还没有 state，可以直接改。

## 2. 新建预算账本（不要改旧账本）

```
python batch.py budget --ledger local/round_02_budget.json --max-requests N --max-reserved-tokens M --authorization "用户明确授权：本轮上限 N 次生成、M token 预留"
```

- 只创建新文件；文件已存在会报错，不会覆盖。
- `authorization` 是账本里的审计字段，写清本轮授权。
- 之后所有 `--ledger` 都指向 `local/round_02_budget.json`。

## 3. 准备（换 API 后建议重做）

双击 `句段-准备与检查.cmd`，或手动：

```
python batch_candidate.py prepare --workspace local/sentence_v3_ws_pilot --protocol sentence_v3 --phase pilot
python batch_candidate.py prepare --workspace local/sentence_v3_ws_full --protocol sentence_v3 --manifest local/molgluedb_inventory/papers.json --phase full
python batch_candidate.py check --workspace local/sentence_v3_ws_pilot --config config.local.json --ledger local/round_02_budget.json
```

- prepare 只冻结输入、提示词、schema 和代码，不发请求；check 只读。
- 如果已双击过准备，设置存在 `local/sentence_launch.json`；把其中的 `ledger` 改成新账本路径，或删掉该文件重新生成后再改。
- 工作区一旦建立就绑定代码哈希；改过 `sentence_*.py` 后要重新 prepare 新工作区，否则 `verify` 报 `Runtime changed`。

## 4. 五篇试跑（第一次真实付费）

```
python batch_candidate.py run --workspace local/sentence_v3_ws_pilot --config config.local.json --ledger local/round_02_budget.json --env-file .env --phase pilot --live --resume-operator-pause
```

- 三阶段：发现（120 个任务）→ 事实（每个候选一次）→ 按需条件（每条候选最多追加一次）。
- 断点续跑：重复执行同一条命令，已完成任务复用，不再付费。
- 未知结果（断连）记 `needs_attention` 并阻止同范围重发；不要靠换线路自动重发。
- 输出上限：发现 2,048 / 事实 4,096 / 条件 2,048 tokens。

## 5. 复核与验收（决定能否放行全库）

```
python batch_candidate.py export --workspace local/sentence_v3_ws_pilot
```

看 `local/sentence_v3_ws_pilot/exports/`：`records.json`（权威记录）、`candidate_audit.csv`、`paragraph_coverage.csv`、`failures.csv`、`summary.md`。

逐条核对六类已知错误（终点错配、未提高写成无活性、缺图弃答、锚点已给却称缺失、字段类型错误、名称在同段前一句），然后写 review JSON。格式见 `sentence_acceptance.py` 文件头：每个 record 一行，必须带 `decision`（supported/quarantine/uncertain）和布尔 `severe_error`；每个核心参考一行（recovered/missed/uncertain），missed/uncertain 不能带 record_keys。再执行：

```
python sentence_acceptance.py assess --workspace local/sentence_v3_ws_pilot --review <review.json> --out local/sentence_v3_acceptance.json
python sentence_acceptance.py binding --workspace local/sentence_v3_ws_pilot --config config.local.json
```

放行条件（`THRESHOLDS`）：支持率 ≥0.90、完整召回 ≥0.80、核心参考 ≥20（当前冻结参考 84 条）、严重错误 =0。`assess` 返回 `passed:false` 时看 `blockers` 逐项修；这一步不是「等用户确认」。

## 6. 放行全库（第二次真实付费）

```
python batch_candidate.py run --workspace local/sentence_v3_ws_full --config config.local.json --ledger local/round_02_budget.json --env-file .env --phase full --acceptance local/sentence_v3_acceptance.json --live --resume-operator-pause
```

- `--phase full` 先 `require_acceptance`：重算验收并核对 runtime、提示词、config 绑定；任一项变化都拒绝启动。
- 全库 193 篇里 166 篇没有全文，prepare 阶段记为 `input_gap`，不进发现队列；要补全文先跑 `fetch`（不花生成额度）。

## 7. 看进度

双击 `句段-查看进度与结果.cmd`，或：

```
python batch_candidate.py status --workspace local/sentence_v3_ws_full
```

`exports/summary.md` 直接列 成功 / 失败 / 缺少全文 / 未完成 四类；`paper_coverage.csv` 逐篇给 jobs、jobs_processed、status。

## 8. 不要做的事

- 不重置、不改写 `round_01_budget.json`；不复用它的 200 次。
- 不重发已知未知请求（账本按 `request_sha256` 拦截）。
- 不把 `local/` 里的参考、原文或 key 带进提交。
- `assess` 未通过时不启动全库。
