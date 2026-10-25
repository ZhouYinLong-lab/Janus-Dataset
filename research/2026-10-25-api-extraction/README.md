# 分子胶正文阴性证据：API提取管线

目标是从论文正文恢复零散报告的阴性实验结果，保留对象、条件和出处。旧数据的可复用部分见[已有材料复用检查](已有材料复用检查.md)。这套管线只做提取与候选管理，后续RAG和训练另设实验。

## 已完成与下一步

已完成原文来源盘点、正文分块、结构化提取约定、兼容Chat Completions的API请求、断点续跑、调用预算保护、原文引用检查、JSON/CSV导出。只用Python标准库，不需要安装SDK。

软件经过离线测试及真实原文旧案例回放，见[验证记录](validation_report.json)。没有读取个人密钥或向真实模型服务发送请求。下一步由你填入模型名和密钥，先试少量请求，核查新输出后再扩大。

## 一、已有材料可以怎样用

311条旧阴性候选中，165条属于旧筛选纳入的分子胶范围，来自26篇论文；149条结果引文能在正文匹配，16条同时匹配正文和表图。它们可作为候选与回归检查材料，不是新API输出或专家金标。引用出现在正文也不代表该事实仅在正文出现。

新任务默认使用旧队列中标为分子胶且纳入的本地论文。结果另外保留PROTAC、工程化标签、领域不确定、相对变弱和目标未检出等记录。模型对领域的判断仍须复核。

## 二、第一次使用：先跑少量请求

在PowerShell中进入项目：

```powershell
Set-Location D:/Projects/Dog/Janus-Dataset
$janusPython = 'D:/Environment/Miniconda3/python.exe'
$janusTool = 'research/2026-10-25-api-extraction/pipeline.py'
$janusWork = 'research/2026-10-25-api-extraction/local/first_api'
$janusConfig = 'research/2026-10-25-api-extraction/config.local.json'
```

本机已准备好 `first_api`：B022、B046两篇论文，共11个正文分块，尚未调用API。其他机器需先取得旧原文队列和final_records快照，或使用下方自定义清单；旧输入具备后可按以下命令准备。工作区已存在时不要重复执行prepare。

```powershell
& $janusPython $janusTool prepare --papers B022 B046 --limit 2 --out $janusWork
```

将[config.example.json](config.example.json)复制为同目录的 `config.local.json`。填写你的服务地址和实际模型ID；示例地址来自此前提供的 `https://yeysai.com/v1`，兼容性需实际试跑确认。配置里不放密钥。

默认 `max_requests=3` 是整个工作区累计最多3次请求，**不是3篇论文**。`max_reserved_tokens=200000` 是保守预估量上限。这两项只是首轮保护，不会把11个分块全部处理完。

设置当前PowerShell进程的密钥，输入不会回显，也不进入命令历史：

```powershell
$janusSecret = Read-Host '输入API key' -AsSecureString
$env:JANUS_API_KEY = [System.Net.NetworkCredential]::new('', $janusSecret).Password
```

先查看预计任务量；此命令不读取密钥、不联网，配置里的模型名即使还没填也能估算：

```powershell
& $janusPython $janusTool estimate --workspace $janusWork --config $janusConfig
```

确认服务和预算后发送请求：

```powershell
& $janusPython $janusTool run --workspace $janusWork --config $janusConfig --live
& $janusPython $janusTool status --workspace $janusWork
& $janusPython $janusTool export --workspace $janusWork
```

只有带 `--live` 的run会发送模型请求。已完成的分块续跑时跳过；超预算会停下。首次运行后看 `exports/records.csv`、`exports/quarantine.json` 和 `exports/summary.json`，回到原文检查对象、结果方向及条件。即使输出为空，也要看原始响应与coverage_notes，确认是未找到候选还是输入/响应存在问题。

使用完可关闭PowerShell，或从当前进程移除密钥：

```powershell
Remove-Item Env:JANUS_API_KEY
```

也可以将密钥保存在本目录被Git忽略的 `.env`，内容为一行 `JANUS_API_KEY=实际密钥`，然后显式指定文件，不需要先设置进程环境变量：

```powershell
& $janusPython $janusTool models --base-url https://yeysai.com/v1 --env-file research/2026-10-25-api-extraction/.env --live
& $janusPython $janusTool run --workspace $janusWork --config $janusConfig --env-file research/2026-10-25-api-extraction/.env --live
```

models只发送一次读取模型目录的GET请求，不生成文本。密钥文件只在显式指定时读取，普通文本解析，不执行文件内容；日志不显示密钥。

调试时可使用 `run ... --job-ids 指定job_id --live` 仅处理已知案例分块；其余任务仍为pending。这是有目的的接口/格式检查，不能将单个分块完成称为整篇完成，或用其结果估计全文召回率。

## 三、小批通过后再扩大

若只是继续当前两篇，核查实际费用后提高当前配置的 `max_requests`、`max_reserved_tokens`，再运行同一个工作区。完整两篇需要11个正常请求；发生失败后显式重试的请求也计入累计上限。

若准备更多论文，创建新工作区，例如从现有分子胶队列取前20篇：

```powershell
$janusBulk = 'research/2026-10-25-api-extraction/local/bulk_01'
& $janusPython $janusTool prepare --limit 20 --out $janusBulk
& $janusPython $janusTool estimate --workspace $janusBulk --config $janusConfig
```

根据estimate调整预算后，再对这个工作区执行run和export。默认按论文ID排序，取前20篇是操作队列，不是随机研究样本。对已处理论文重新建工作区会重新收费，不要把prepare当作续跑。

现有队列之外的论文，可提供自定义JSON清单，再使用 `prepare --manifest 清单路径 --limit 数量 --out 新工作区`：

```json
[
  {
    "paper_id": "NEW001",
    "path": "D:/your-corpus/paper.xml",
    "doi": "论文DOI",
    "title": "论文题名",
    "url": "原文来源链接",
    "source_license": "原文标明的许可"
  }
]
```

支持JATS XML和BioC XML。PDF需先取得可读XML；当前不处理图片像素或独立补充附件。普通TXT可解析但不视为已有可靠段落角色的正文，当前会报输入缺口，须先整理来源结构。新增全文采集可沿用旧版[采集脚本](../2026-10-22-sol-extraction/batch02/collect_corpus.py)，本工具本身不绕过网站访问限制。先确认领域与原始研究身份，再进入提取队列。

## 四、费用与失败处理

- 请求预算是工作区累计上限，跨多次run仍生效，默认不自动重试。预算预留在请求发出前落盘。
- 预留量采用“输入UTF-8字节数＋2048开销＋请求的输出token上限”。它是保守规划数，不是精确token数或保证的金额上限。服务返回的usage另存；实际费用以服务账单为准，建议同时设置服务端金额限制。
- 超时或连接中断时，服务端可能已经执行并收费，状态为needs_attention，不自动重发。进程被强制结束留下in_flight时也会阻止自动续发，先核对服务端记录。
- HTTP错误、非法JSON、输出截断等会停下并记录失败。确认原因后，已知失败可用 `run ... --live --retry-failed` 显式重试；费用继续累计。未知执行结果不接受这一快捷重试。
- 部分记录引用错误时保留在quarantine，其余记录可导出；整份响应解析失败时保留响应文件，不能当作“该篇无阴性”。run遇到需要检查的失败返回退出码3；配置或文件错误返回2。
- 模型、请求参数或处理代码变化时使用新工作区，防止不同版本混在一起。预算上限允许在原工作区调整。
- 若服务不支持JSON模式，可把response_format改为none；若模型要求max_completion_tokens，可修改output_token_parameter。没有自动降级重试，以免未知兼容问题导致额外收费；修改请求参数后重新准备工作区。
- 并行启动同一工作区会被锁阻止。异常退出留下 `.run.lock` 时，先确认对应进程已结束，再由使用者清理锁；in_flight仍需核对执行结果。

接口按[Chat Completions API约定](https://developers.openai.com/api/reference/resources/chat)组织。第三方服务是否实现对应字段，由首次真实请求确认。

## 五、怎样解释产物

| 文件 | 用途 |
| --- | --- |
| manifest.json / jobs / documents | 冻结来源、提示词、全文分块和上下文，记录哈希 |
| state.json | 累计调用、预算预留、用量与逐分块状态 |
| responses | 服务返回的原始JSON响应，本机留存 |
| results | 引用校验后的候选、隔离记录及覆盖说明 |
| exports/records.json、records.csv | 方便后续检索、查看和复用的记录 |
| exports/primary_candidates.json | 正文结果引用通过检查、模型判断为分子胶阴性的候选 |
| exports/other_or_risk_records.json | 相对变弱、基线未检出、其他领域等记录 |
| exports/quarantine.json | 引用、字段或结构检查失败的记录 |

每个非空字段需要原文引文和unit_id；结果引文必须来自当前扫描的正文分块。不能找到引用的字段会使该条隔离，条件不明时模型应留null。程序能检查“引文是否存在”，字段归属和生物学含义仍需核查，所有新记录的ready_for_training均为false。

“正文出现”与“正文独有”分开处理，table_overlap默认not_evaluated。同一表示在多个分块重复时合并并保留各处provenance；这不证明原实验相同或彼此独立。特殊条件阴性保留experimental_setting、perturbation、construct和qualifiers，不能脱离这些字段使用。

正文逐段扫描，超长段落重叠拆分而不截去尾部；上下文按词汇相关度选取并受长度限制，遗漏数量会记录。完整条件未必都在同一个请求中，跨段落补全需检查原文，不能把这套上下文选择当成完整语义恢复的保证。

## 六、复现验证

```powershell
D:/Environment/Miniconda3/python.exe research/2026-10-25-api-extraction/verify.py
```

该命令运行单元测试、本机HTTP模拟、旧来源盘点复算和4篇原文旧案例回放，刷新validation_report.json；不读取你的密钥或调用真实模型服务。回放只喂入4个预先选定的旧案例，不衡量新模型的抽取准确率或全文召回率。真实模型的小批效果检查在正式扩量前完成。

本目录local、config.local.json及密钥文件默认Git忽略。公开提交代码、简短检查结果与无长原文的来源索引；混合许可全文、请求上下文和响应保留在本机。
