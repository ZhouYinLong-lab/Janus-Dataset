# MG2Act → MolGlueDB 来源映射

核查日期：2026-10-26。固定 MG2Act commit：`d3f9d1da48be93d67cfc2be074c0cf0c6bdbb065`。本任务读取公开来源，无认证、无模型生成；原始响应保留本机。

## 交付及结论

机读主表为 [benchmark_provenance.csv](local/source_mapping/benchmark_provenance.csv)，统计及哈希为 [mapping_summary.json](local/source_mapping/mapping_summary.json)。主表是**一条 benchmark 记录对应一个或多个来源候选行**，共 1,239 行，覆盖全部 1,159 个 `(benchmark_split, benchmark_id)`；不能把输出行数当独立 benchmark 样本数。

可随仓库调用的必要身份与来源事实另存为[source_associations.csv](source_associations.csv)，同时纳入53条单独核查的本地身份映射；其快照和上述原始映射统计见[mapping_manifest.json](mapping_manifest.json)。公开表不包含原文和数据库原始测定描述。

固定 CSV 为 train 907、val 125、test 127 行；ID 最小 7、最大 1296。三份文件已从固定 commit 下载，并逐字节比对主工作区 `local/upstream/MG_data/` 中的 CSV。

取得官网全表 1,840 行、1,629 个不同 `DATAID`。全部 1,159 个 benchmark 结构与该表 SMILES **逐字相同**。在同时要求靶标标签、E3 名称和 E3 UniProt 匹配后，表内匹配 1,158 行；剩余 `id=1296` 通过同一官网公开详情 API 找到全表遗漏的条目，因而最终 1,159 行均有结构＋靶标＋E3 对应的数据库来源。

最终分组：

- 1,098 条 benchmark 记录在匹配的数据库来源中只有一个 DOI。
- 60 条存在多个 DOI，全部保留候选。原名匹配可使其中 40 条只有一个名称一致的 DOI；另 20 条仍有多个名称一致 DOI。主表不删除其他来源，也不据此指定唯一训练实验。
- 1 条 `id=357 / MRT-2359 / GSPT1` 的数据库来源为公司公开材料，未提供 DOI；保留原 URL，`source_doi` 为空。
- 0 条未决靶标映射。

这些是数据库已有的“结构—靶标—E3—文献”关联。**尚未证明 MG2Act 的每个标签取自哪一个具体文献实验或剂量条件**；同结构同靶标跨文献读数可能不同，不能任取一个候选复算并归因于模型。

## 接入 overlap_audit.py

使用 UTF-8、标准 CSV 解析，按 `(benchmark_split, benchmark_id)` 分组。主要列如下：

| 列 | 含义 |
| --- | --- |
| `benchmark_structure`, `benchmark_target`, `benchmark_target_uniprot`, `benchmark_e3`, `benchmark_e3_uniprot`, `benchmark_name` | 固定 benchmark 原值 |
| `source_doi`, `source_url`, `compound_original_name` | 来源 DOI、原来源 URL、该来源记录的原化合物名；可供“DOI＋论文 compound ID/名称”回链 |
| `molgluedb_DATAID` | 官网复用的化合物编号，**不等于 benchmark ID** |
| `molgluedb_export_row_number` | 原导出 CSV 的数据行序号，1 起算、不计表头；**不是网页条目 id** |
| `molgluedb_entry_id`, `molgluedb_entry_url` | 仅在本次公开详情 API 直接核实的样本上填写，不从行序号猜测 |
| `mapping_status`, `mapping_basis`, `target_matched_role` | 匹配状态、明确匹配规则、靶标在原库 primary/secondary 中的位置 |
| `doi_candidate_count`, `all_candidate_dois_json` | 同一 benchmark 的完整匹配 DOI 候选集合 |
| `source_name_exact`, `name_matched_doi_count`, `name_matched_dois_json` | 原名规范化后是否相同及其候选集合；名称证据与结构／靶标证据分列 |
| `raw_primary_target_deg_info`, `raw_secondary_target_deg_info` | 数据库原始降解注释全文，保留所有数值、限定符、条件及多靶标上下文 |
| `raw_target_degradation_text`, `raw_readout_scope` | 单一注释靶标的全文或明确标记本靶标的片段；多靶标无法划分时标出未解析 |
| `rawDC50`, `rawDmax` | JSON 数组，保存可定位到本靶标片段的字面读数，含单位、不等号和误差；不是数值化的统一读数 |
| `source_file`, `source_storage`, `source_database_url`, `source_sha256`, `source_row_sha256`, `source_archive_sha256` | 回查本地原文件、公开接口及内容哈希 |

`source_doi` 为空时代表本次来源未提供 DOI。`rawDC50`/`rawDmax` 为 `[]` 代表该规则未提取到字面读数，应继续查看完整注释，不能直接解释成未测试或无效。固定浓度下的百分比降解保留在原文列，**不改称 Dmax**。数据库本身没有独立的 rawDC50/rawDmax 列，本次保存的是其自由文本读数，不是重新查阅各原论文得到的实验金标。

建议重叠比对分别报告：任一数据库候选 DOI＋原名命中、名称一致候选命中、唯一 DOI 候选命中；保留多来源分母，避免把一次命中解释成唯一来源确认。

## 可核查实例

下表的网页条目 id 均由公开 API 返回，结构、靶标、E3 与固定 CSV 同时核对。

| benchmark ID | benchmark／来源原名 | DATAID | 网页条目 id | DOI／来源 | 本靶标原始读数 |
| --- | --- | --- | --- | --- | --- |
| 7 | Compound 12 | 90 | 96 | 10.1021/jacs.4c06127 | CK1α DC50: 170 nM；同段另有 WEE1 22 nM，不能混挂 |
| 8 | Compound 11 | 91 | 97 | 10.1021/jacs.4c06127 | CK1α DC50: 9.1 nM；WEE1 为 2.0 nM |
| 11 | 38 | 164 | 170 | 10.1021/acs.jmedchem.3c01736 | CK1α: 70% degradation at 100 nM；不是 Dmax |
| 14 | LC-04-113 | 300 | 318 | 10.1021/jacsau.4c00762 | DC50 = 10 nM; Dmax = 91% |
| 18 | 12 | 320 | 340 | 10.1021/acsmedchemlett.4c00250 | DC50 = >10000 nM; Dmax = 38%(10 μM); (24 h) |
| 1296 | (S)-5HT | 1016 | 1841 | 10.1038/s41467-020-18488-4 | 详情未填降解读数；保留为空 |

固定版本中 `id=14` 的名称实际为 `LC-04-113`。`id=1296` 的 benchmark 与库中 SMILES 都未标记该手性中心，故名称中的 `(S)` 不能当作结构字段已经确认了绝对构型。

`id=18` 直接访问官网 `/api/query_bj_data_by_id?id=18` 返回的是另一种甾体结构、原名 `4`，与 benchmark CK1α/化合物 `12` 不同。相反，经结构＋靶标＋E3 找到的真实对应是 DATAID 320、网页 id 340。这直接否定“数字一样即可映射”的做法。

`DATAID=1016` 的详情接口返回 6 条跨文献记录，导出全表只有前 5 条；补充的第 6 条为网页 `id=1841`，靶标 `SALL4; IZKF1`、名称 `(S)-5HT`、CRBN/Q96SW2，SMILES 与 benchmark id1296 完全一致。拼写 `IZKF1` 按官网保留，本次只用明确的 SALL4 标签匹配。该行在 [supplemental_api_rows.json](local/source_mapping/supplemental_api_rows.json) 单独记录，原全表不改写。

## 公开获取路径与失败证据

[官网](https://www.molgluedb.com/) 前端公开 JS 使用 `/api` 作为接口前缀。下载页代码请求 `GET /api/export_bj_data`，实际返回 `application/gzip` 的 `MolGlueDB_full.tar.gz`，内部含 `MolGlueDB_full.csv`；页面文案虽写 CSV，响应本身是压缩包。

可复现请求头为 `Referer: https://www.molgluedb.com/browseDB`、`Origin: https://www.molgluedb.com`、`Accept: application/json, text/plain, */*` 和 `X-Requested-With: XMLHttpRequest`。未发送 Authorization、Cookie 或密钥；未调用下载计数更新的 POST。此处仅记录所用请求条件，不推断究竟哪一个头是必要条件。

使用了全表接口以及按页面代码公开的 `query_bj_data_by_id?id=...`、`query_bj_data_by_dataid?dataid=...` 查询。仅查询 6 个 DATAID 样本及一个错误数字 ID 对照，无逐条全站爬取。

初始不带上述同站请求头时，www/apex/HTTP 下的 API 请求重定向到首页，得到 1,686 字节 HTML；`/export_bj_data` 根路径也只返回 SPA HTML。带浏览器头的 `/api/export_bj_data/` 尾斜线试验返回 404。GitHub 公共树接口返回 403 rate limit；固定 commit 的 raw CSV 下载成功。OUP 正文页直接请求返回 403，浏览工具也遇到不可访问跳转；已改用 Europe PMC 的公开全文与附件服务。

下载日志 [retrieval_manifest.json](local/source_mapping/retrieval_manifest.json) 保存成功及失败请求、最终 URL、响应类型、字节数、哈希。初始一些失败响应沿用请求文件名后缀 `.csv`/`.json`，**实际内容为 HTML，不参与映射**；有效全表文件名为大写开头的 `MolGlueDB_full.csv`，有效 API 样本为 `molgluedb_id18_verified.json`、`molgluedb_dataid*.json`。

主要内容哈希：

- 全表 gzip：`8ec9b2d51cdaff471e183073731e3e3464684494adba025738b7843ac6b84f15`。
- 原始全表 CSV：`cf1d0d61b889539d56b250f5adeb7652ef1a25ebe5008110db86bd28328a1d48`。
- 固定 train：`2143e5c1dfa7a79c47be35fc24f650e78f2a0ff20f096b99d1d34bd6d1c9482d`。
- 固定 val：`57b22e3b60d7133403bbe6204c3d68bb20f27c3d0d8cdb5916bd8853b424fce8`。
- 固定 test：`ede542844a40cbbf6f9b8eda08b6e664febe3f17267504996b5d3e82edb52770`。

## MolGlueDB 论文及附件核查

[MolGlueDB 原论文，DOI 10.1093/nar/gkaf811](https://academic.oup.com/nar/article/54/D1/D1510/8239508) 描述全表导出功能和文献来源整理，但没有声明 MG2Act 的 `id` 与当前库 id 相同。

通过 [Europe PMC 全文 XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12807675/fullTextXML) 及[公开附件 ZIP](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12807675/supplementaryFiles) 完整取得论文与 `gkaf811_supplemental_file.docx`。附件包含 Table S1 字段说明、Figures S1–S3 和界面说明，没有条目级化合物—结构—DOI 全表，也无嵌入的数据文件；因此映射依据来自官网实际导出和公开详情接口，未把字段目录当成数据表。

本地重建入口为 `python -B local/source_mapping/build_provenance.py`，只读取已冻结文件、写 `local/source_mapping/`。抓取工具 `fetch_public.py` 及全部原始响应一并保留，不需要访问凭据。映射没有改写 benchmark 原始字段或旧提取结果。
