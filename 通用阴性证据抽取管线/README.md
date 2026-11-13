# 通用阴性证据抽取管线

这是从项目原有“分子胶阴性证据抽取管线”中抽出的通用层。它解决的是跨生化领域都成立的工程问题：

```text
论文全文
  → 正文/段落/句子定位
  → 发现实验阴性或低性能候选
  → 按领域 schema 抽取对象、结果和条件
  → 用原文证据校验每个字段
  → 输出可审计 JSON/CSV
```

核心层不写死分子胶、酶工程或任何具体实验终点；领域差异放在项目根目录的 `阴性证据领域适配器/` 中，通用提示词保留在本目录的 `prompts/` 中。

## 当前目录

```text
通用阴性证据抽取管线/
├─ README.md                         本文件
├─ pipeline.py                       通用 CLI：prepare/prompt/validate/export/status
├─ test_pipeline.py                  离线结构测试
├─ prompts/
│  ├─ discovery_generic.md           通用候选发现提示词
│  └─ extraction_generic.md          通用字段抽取提示词
└─ examples/
   ├─ manifest.json                  输入论文清单格式
   └─ sample_response.json            模型响应格式示例
```

## 这个版本能做什么

已经抽出的通用能力：

1. 读取纯文本、Markdown、HTML 和常见 XML/JATS 全文；
2. 保留论文、段落、句子、字符偏移和源文件 SHA-256；
3. 将全文切成可处理的 job；
4. 为发现阶段和字段抽取阶段生成领域适配 prompt；
5. 校验模型输出是否引用了真实句子，是否把未测试/未知误写成阴性；
6. 将通过结构校验的记录导出为 JSON/CSV，并保留失败和未决记录；
7. 支持多篇论文和重复运行，不覆盖已有 workspace。

核心层只做“来源、结构和证据绑定”检查，不把结构校验当作科学事实金标准。科学语义仍需要领域适配规则和人工复核。

## 最小使用流程

以下命令均在项目根目录执行。

### 1. 准备论文清单

复制示例清单：

```powershell
Copy-Item `
  '通用阴性证据抽取管线/examples/manifest.json' `
  '通用阴性证据抽取管线/my_manifest.json'
```

编辑 `my_manifest.json`：

```json
[
  {
    "paper_id": "P001",
    "path": "D:/papers/paper_001.xml",
    "doi": "10.xxxx/example",
    "title": "Example paper",
    "url": "https://doi.org/10.xxxx/example"
  }
]
```

`path` 必须指向已经取得的全文文件。没有全文的论文不进入抽取阶段；不能把数据库中没有记录直接当成阴性。

### 2. 准备 workspace

以项目根目录下的酶工程适配器为例：

```powershell
python 通用阴性证据抽取管线/pipeline.py prepare `
  --manifest 通用阴性证据抽取管线/my_manifest.json `
  --adapter 阴性证据领域适配器/enzyme_engineering.json `
  --out work/enzyme_engineering_01
```

准备阶段只读本地论文，不调用模型。它会生成：

```text
work/enzyme_engineering_01/
├─ manifest.json
├─ documents/       解析后的来源与句子
├─ jobs/            待处理文本块
├─ responses/       外部模型响应放这里
├─ results/         通过结构校验的结果
└─ exports/         最终 JSON/CSV/summary
```

### 3. 生成模型提示词

先列出 job：

```powershell
python 通用阴性证据抽取管线/pipeline.py status `
  --workspace work/enzyme_engineering_01
```

生成发现阶段提示词：

```powershell
python 通用阴性证据抽取管线/pipeline.py prompt `
  --workspace work/enzyme_engineering_01 `
  --job-id P001_<job_hash> `
  --stage discovery `
  --out work/enzyme_engineering_01/prompts/P001_discovery.txt
```

生成字段抽取阶段提示词：

```powershell
python 通用阴性证据抽取管线/pipeline.py prompt `
  --workspace work/enzyme_engineering_01 `
  --job-id P001_<job_hash> `
  --stage extraction `
  --out work/enzyme_engineering_01/prompts/P001_extraction.txt
```

模型调用可以使用队伍已有的 API 客户端，也可以人工把 prompt 交给模型。模型返回的 JSON 必须保存为：

```text
work/enzyme_engineering_01/responses/<job_id>.json
```

这一步不由通用核心自动发送请求，避免不同服务的 key、预算、模型协议混进通用层。

### 4. 校验模型响应

```powershell
python 通用阴性证据抽取管线/pipeline.py validate `
  --workspace work/enzyme_engineering_01
```

校验内容包括：

- `paper_id`、`job_id` 是否一致；
- 字段是否符合当前 adapter；
- outcome 是否属于领域允许的结果类型；
- 每个非空字段是否绑定证据；
- 引文是否真实存在于当前 job；
- `not_tested`、`unknown` 是否被错误当成阴性；
- 没有合法记录时是否给出明确原因。

### 5. 导出结果

```powershell
python 通用阴性证据抽取管线/pipeline.py export `
  --workspace work/enzyme_engineering_01
```

主要输出：

```text
exports/records.json      通过结构与引文检查的记录
exports/records.csv       Excel 可打开的表格，UTF-8 with BOM
exports/rejected.json     字段或证据校验失败的记录
exports/unresolved.json   模型标为不确定或无法判断的候选
exports/summary.json      论文、job、记录、失败数和证据统计
```

## 酶工程适配器的研究边界

当前示例适配器的目标是：

> 从酶工程论文中恢复突变体/酶—反应或底物—实验条件—活性结果之间的阴性或低性能观察。

它把以下状态分开：

```text
loss_of_function          功能丧失
no_detectable_activity    无可检测活性
low_activity              低活性
low_yield                 低产率
low_selectivity           低选择性
conditional_failure       特定条件下失败
not_tested                未测试
unknown                   证据不足
```

`not_tested` 和 `unknown` 不会进入可训练阴性记录。表达失败、蛋白不稳定和催化失活也应分别记录，不能只用一个 `inactive` 标签覆盖。

## 换领域时怎么做

只需要在项目根目录的 `阴性证据领域适配器/` 中新增一个 adapter，并替换领域 prompt：

1. 定义对象字段；
2. 定义结果类型；
3. 定义哪些结果算实验阴性；
4. 定义“未测试、未报告、检测失败、条件性失败”的区分规则；
5. 编写领域语义复核规则；
6. 建立少量人工金标准后再批量运行。

例如，蛋白互作可以使用 `protein_a`、`protein_b`、`mutation`、`assay`、`kd_or_ddg` 和 `binding_outcome`；底物相容性可以使用 `enzyme`、`substrate`、`reaction`、`conversion`、`yield` 和 `selectivity`。适配器不放在通用框架内部，便于多个领域共用同一套核心程序。

## 现有旧管线与本目录的关系

旧管线仍保留在：

```text
之前的调研/research/2026-10-25-api-extraction/
```

旧管线的核心工程经验已抽象到本目录，但它的 prompt、字段和语义规则仍然面向分子胶降解。不要把旧目录中的 `prompt.md`、`discovery_v3.md` 或 `contract.py` 直接当作通用配置。

## 运行离线测试

```powershell
python -m unittest -v 通用阴性证据抽取管线/test_pipeline.py
```

测试只使用合成文本和合成响应，不代表任何论文科学事实，也不产生模型效果结论。

