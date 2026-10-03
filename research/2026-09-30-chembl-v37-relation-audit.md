# ChEMBL 37 活性记录关系符初步审计

**审计日期：** 2026-09-30  
**主问题关联度：** 3/3（直接量化结构化分子活性记录中非精确关系值的规模，并检查其派生数值字段是否保留删失语义）。

## 数据源与范围

本轮使用 Hugging Face 用户 `lovingscience` 发布的 [ChEMBL 37 raw activities 镜像](https://huggingface.co/datasets/lovingscience/chembl-v37-raw-activities)，固定到 revision `131ebfa52acce09f540d078a0f7b649fc30c9461`，读取 `chembl_v37_raw_activities.parquet`。这是第三方派生镜像，不是 ChEMBL 官方全库导出。数据卡称其源自 ChEMBL 37，并过滤至 assay confidence score ≥7、排除若干 data-validity 错误和 potential duplicates；数据卡报告 3,895,081 条记录。ChEMBL 官方下载页将 release 37 标为 2026 年 5 月版本。[官方 ChEMBL 下载页](https://chembl.gitbook.io/chembl-interface-documentation/downloads)

使用 DuckDB 对该 Parquet 文件执行逐列聚合。可复算查询：

```sql
SELECT standard_relation, COUNT(*)
FROM read_parquet('chembl_v37_raw_activities.parquet')
GROUP BY 1 ORDER BY 1;
```

本次通过 Hugging Face `resolve/<revision>/...parquet` 远程读取，未把约 200 MB 文件复制进项目。该数据集在 Hub viewer 中列出两个约 200 MB Parquet 文件；本计数只对版本名文件 `chembl_v37_raw_activities.parquet` 执行，避免把 viewer 的 7,790,162 行（两文件合计）误当作不同观察数。另一个 `chembl_raw_activities.parquet` 的总行数、distinct `activity_id` 数及关系符频数均与版本名文件一致，显示其至少在这些汇总层面重复；本轮尚未逐行比较两文件字节或完整记录。

此外，官方 REST API 的第一页 `activity.json?limit=1` 返回当前 `activity` endpoint 总计 24,527,044 条，并返回 activity ID 31863：`standard_type=IC50`、`standard_relation=>`、`standard_value=100000 nM`、`pchembl_value=null`、`activity_comment=null`，而 assay description 明确包含 “no measurable activity”。再以同一个 `activity_id=31863` 查询固定版本 Parquet，得到相同的 assay/document ID、关系符、边界值和描述，但第三方镜像的 `pchembl_value=4.0` 且 `pchembl_source=recalculated`。即这条同一原始观察在官方 API 中保留为删失值且无 pChEMBL，在第三方派生表中却按 100,000 nM 边界赋为点值；这不是 ChEMBL 官方删除关系信息，而是下游派生字段可能压扁关系语义的直接例子。该记录所链 document 为 CHEMBL1137930，可解析到 Wang et al. 2004, DOI `10.1016/j.bmcl.2004.03.095`。PubMed 摘要只概述三种 UK-1 analogs 中 UK-1 与两种 analogs 是 topo II catalytic inhibitors，并未在摘要中点名 activity 31863 对应的单体；BindingDB 聚合页有匹配配体/IC50/来源文章，但页面标注 `Curated by ChEMBL`，因此它不是独立验证，且仍不是原文。此例已被结构化活性资源捕获，不能算作文献抽取带来的新增观察；它只能证明“数据库记录带有可追溯来源和语境字段”及派生值变换，不能声称我们已从原论文正文独立验证了该阴性结果。[PubMed 记录](https://pubmed.ncbi.nlm.nih.gov/15149679/) · [BindingDB 配体-靶点记录](https://w.bindingdb.org/rwd/jsp/dbsearch/PrimarySearch_ki.jsp?entryid=50014787&tag=entry) 单条记录仍不是随机抽样或全库 prevalence 证据。[官方 API 示例查询](https://www.ebi.ac.uk/chembl/api/data/activity.json?limit=1) API 官方文档支持 `__exact` 等过滤并分页，但本环境的关系符全库筛选在 25 秒内无响应，`standard_type` 筛选返回 500，assay 精确筛选也超时；官方 release 37 SQLite 压缩包目录标示约 5.4 GB，故本轮未下载整个归档。[官方 API 文档](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services)

## 计数结果

| `standard_relation` | 记录数 | 占 3,895,081 条比例 |
|---|---:|---:|
| `=` | 3,136,358 | 80.52% |
| `<` | 119,833 | 3.08% |
| `<=` | 7,015 | 0.18% |
| `>` | 603,724 | 15.50% |
| `>=` | 4,000 | 0.10% |
| `>>` | 118 | <0.01% |
| `~` | 485 | 0.01% |
| 空值 | 23,548 | 0.60% |

合计 758,723 条没有精确等号编码（19.48%）；其中 734,572 条使用方向关系符 `<`、`<=`、`>`、`>=`。主要端点的关系符并不罕见：IC50 有 371,886 条非等号或关系符缺失的读数（其中 `>` 为 246,362、`<` 为 97,602、`<=` 为 6,735、`>=` 为 3,196、`>>` 为 104、`~` 为 258、关系符空值为 17,629）；Ki 中 `>` 为 122,379、`<` 为 11,874；Kd 中 `>` 为 92,732、`<` 为 3,456。注意这些是特定第三方镜像、confidence/data-validity/duplicate 过滤之后的记录数，不是 ChEMBL 37 全库的 prevalence 估计。

## 对阴性数据问题意味着什么

1. 结构化库中的方向关系读数在规模上值得专门审计，不能只看等号编码的读数或 pChEMBL 派生列。但“非等号/关系符缺失”是编码状态，不是统一的阴性标签。
2. 关系方向必须与 endpoint、单位、assay cutoff 和目标语义一起读。对常见 potency endpoint，`IC50 > 某阈值` 往往能支持“在该 assay 条件下活性低于阈值”的判断；`IC50 < 某阈值` 则可能相反。其他 endpoint、实验设计和异常 relation 不能照搬此解释。
3. 该镜像 schema 没有 `activity_comment` 或 `standard_text_value` 字段，因此本审计不能计数 ChEMBL 中的显式 `Not Active`、`Inactive` 等文本结果，也不能判断 relation 与源论文描述是否一致。官方数据提交规范分别表示数值、关系符、文本结果和 activity comment；该镜像仅覆盖其选取的字段。[ChEMBL Activity 字段规范](https://chembl.gitbook.io/chembl-data-deposition-guide/file-structure/field-names-and-data-types-minimal-data-submission/activity.tsv)
4. `pchembl_value` 在该镜像每个关系符分组中均非空（包括 `<`、`>`、`~` 和空 relation）。更直接地，同一条 `activity_id=31863` 在官方 API 中为 `IC50 > 100,000 nM` 且 pChEMBL 为空；在第三方镜像里 `pchembl_value=4.0`、来源 `recalculated`，恰为把 100,000 nM 边界当精确值所得的 `-log10(100 μM)`。如果下游把第三方派生 pChEMBL 当普通连续标签，关系方向/区间信息就会被压扁；这提示需要核查具体使用者的转换流程，不能把派生列的问题误写成 ChEMBL 官方原始记录丢失信息。官方规范仍指出原生 pChEMBL 标准值要求 `standard_relation = '='`，因此第三方重算列应与 ChEMBL 原生字段分开解释。
5. 本计数证明该过滤子集含大量可见的非精确记录，但不证明这些记录被所有模型训练流程丢弃，也不证明它们未被 Mayr et al. 2018 等工作按阈值转成 inactive/weak 标签。相反，Mayr 的先例说明部分删失记录早已参与过二分类 benchmark。

## 端点×关系符分组

该聚合用于复核端点差异，未把任何一格直接命名为阴性：

| Endpoint | `<` | `<=` | `=` | `>` | `>=` | `>>` | `~` | 空值 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AC50 | 994 | 0 | 71,186 | 106,532 | 0 | 0 | 1 | 1,336 |
| EC50 | 5,907 | 63 | 184,332 | 35,719 | 233 | 3 | 58 | 4,498 |
| ED50 | 0 | 0 | 3,919 | 0 | 0 | 0 | 0 | 0 |
| IC50 | 97,602 | 6,735 | 1,307,103 | 246,362 | 3,196 | 104 | 258 | 17,629 |
| Kd | 3,456 | 48 | 68,500 | 92,732 | 100 | 0 | 70 | 13 |
| Ki | 11,874 | 169 | 474,058 | 122,379 | 471 | 11 | 98 | 72 |
| Potency | 0 | 0 | 1,027,219 | 0 | 0 | 0 | 0 | 0 |
| XC50 | 0 | 0 | 41 | 0 | 0 | 0 | 0 | 0 |

## 结论与下一步

当前最稳妥结论：**在一个经筛选的 ChEMBL 37 派生子集中，约五分之一记录没有精确等号编码或 relation 缺失；关系符可与数值边界共同携带信息，但不等价于显式实验阴性。我们已在同一 `activity_id` 上观察到第三方派生 pChEMBL 把官方保留为 `>` 的边界值换算成点值；后续数据产品应并存原始值、关系符、endpoint、单位、assay、来源和任何派生标签。**

下一步应使用低负担的官方 API 查询或按 assay 分块，联合检查 `activity_comment`、`text_value`、`standard_relation`、`standard_type`、assay 和 document 字段；随后以 Mayr benchmark 为参照确认哪些原始记录已有标准化建模标签。官方 API 基础查询可用，但关系符全库聚合在本轮超时；完整 SQLite 压缩包约 5.4 GB，不宜为得到一个总数直接下载，应先探索 API 分 assay 分页、官方 SQL/小型导出或公开的 assay 子集。
