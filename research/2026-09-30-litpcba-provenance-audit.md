# LIT-PCBA / PubChem 样例来源审计

**日期：** 2026-09-30  
**关联主课题：** 阴性证据必须绑定具体 assay、靶点、观测与来源；不能把同一化合物在另一 assay 的 inactive 结果移作本任务阴性。

## 审计结论

现有笔记 [`notes/lit_pcba_pubchem_bioassay_comparison.md`](notes/lit_pcba_pubchem_bioassay_comparison.md) 的两个示例都不是 LIT-PCBA MAPK1 对应的 PubChem AID 995 记录：

| SID / CID | 笔记所引 PubChem assay | PubChem 核验结果 | 对 MAPK1 对照的意义 |
|---|---|---|---|
| 440151760 / 129284334 | AID 1785989 | KDR（VEGFR2）kinase panel，结果为 inactive | 只能说明该化合物在所引 KDR assay 的状态；不能作为 MAPK1 assay 的结果 |
| 440230063 / 24959105 | AID 1788980 | EGFR kinase activity assay，结果为 inactive；AID 描述指向 EGFR（P00533），来源标为 ChEMBL | 只能说明该化合物在所引 EGFR assay 的状态；不能作为 MAPK1 assay 的结果 |

PubChem 对 AID 995 的描述是 MAPK1（ERK signaling）筛选 assay。对本地 `MAPK1/actives.smi` 与 `MAPK1/inactives.smi` 按 SID/CID 精确检索，上述两个样例均未命中。因此，原笔记能说明“单个化合物可在不同靶点 assay 中出现 inactive 记录”，但尚不能证明 MAPK1 benchmark 相对 AID 995 上游记录压掉了这些示例所列的测量值、效度标记或实验语境。

作为早期正确匹配的可行性检查，我曾从本地 MAPK1 文件各取 3 个 SID，向 PubChem AID 995 按 SID 精确请求记录，6/6 标签一致。**本轮已将检查扩展到 AID 995 的官方 PUG REST concise CSV 全部记录，以下完整 join 结果取代“仅 6 个样本”这一阶段性结论。**

## AID 995 全量 concise 结果与本地 MAPK1 清单 join

2026-09-30 通过 PubChem PUG REST `/assay/aid/995/concise/CSV` 获取到 72,004 行、72,004 个唯一 SID 的摘要结果。Outcome 为 Active 711、Inactive 66,078、Inconclusive 5,215。将这些 SID 与本地 `MAPK1/actives.smi`、`MAPK1/inactives.smi` 精确匹配：本地 308 个 active 和 62,629 个 inactive 共 62,937 个 SID **全部命中** AID 995；本地 active 全部标为 Active，本地 inactive 全部标为 Inactive，且未发现同一 SID 多行或标签冲突。这使得本地文件标签来源于该 AID（至少在 SID 和 outcome 层面）有了全量支持，而不是抽样推测。

AID 995 中未被本地 MAPK1 **Full** 清单收录的其余记录为 9,067 个：403 Active、3,449 Inactive、5,215 Inconclusive。原始 LIT-PCBA 补充信息（Table S3）给出 MAPK1 inactive 的逐阶段汇总：66,078 → 65,908（Step 1）→ 62,652（Step 3）→ 62,629（Step 4）。因此相对 AID 995 原始 inactive 的 3,449 条总差额，可精确拆成 Step 1 无机分子 170 条、Step 3 极端分子性质 3,256 条、Step 4 3D 转换/电离失败 23 条；这些类别计数之和与未进入 Full 的 inactive 总数完全一致，但 SI 没有逐 SID exclusion-reason 表，仍不能声称已逐条确认每个 SID 的筛除原因。先前看似冲突的 62,629 与 61,567 已由官方链接包的实际成员文件解释：官方 `LIT-PCBA_full.tar.gz` 中 MAPK1 `inactives.smi` 有 62,629 个唯一 SID；官方 `LIT-PCBA_AVE_unbiased.tar.gz` 中 `inactive_T.smi` 有 46,317 行、`inactive_V.smi` 有 15,250 行，合计正好 61,567。AVE 两文件相对 Full inactive 清单恰少 1,062 个 SID；active split 为 231+77=308，完整覆盖 308 个 active。维护页/论文 61,567 对应 AVE split 的 train+validation 数，Full package 62,629 对应完整筛选清单；两者不是同一层级的计数。2023 SI 的 62,629 before docking、62,525 after docking另有其 docking 阶段口径。

官方页面当前链接的完整包 (53,808,785 bytes) 与本地 `MAPK1/actives.smi`、`inactives.smi` 的 SID 集完全一致；两个文件逐字节 SHA-256 也相同。下载的官方 AVE 包 (57,399,933 bytes) 计数和拆分亦符合页面表格。Full archive SHA-256: `81F361FB5BD2C219CD72F1B580DBC8980311911703DF53598134163A8282DF34`; AVE archive SHA-256: `1F50EF6BF66B8E987F056A2D2528F1D5A9031AD542DDC97F8EE2FBFD651C8DE3`; MAPK1 full inactive file SHA-256: `AEA6DEC0F0A71A3A978812089D3C8E2A5A71FC71A0FCA6A062F12DF2F4650876`; AVE `inactive_T` / `inactive_V` SHA-256: `0261EEE8A24EED50963495D4F75410C4677439BA4CED18FB7985F1E435F85E24` / `DB2B17A000EA2D0E752FBDCC30F23AC4F3AEE1A817EE1E500E4523DE64D6900C`. 1,062 full-list inactives are outside the AVE train+validation files; this is a split-membership fact, not evidence they were never measured or removed from the full benchmark.

本次下载的是 concise outcome 表，足以审计 SID 与 Active/Inactive/Inconclusive 的对应，但不包含每条记录完整的剂量反应曲线、所有原始 readouts 或 QC 细节；此前 6 个样本检查到的扩展字段不能外推为全量字段已获取。官方 assay 描述将 AID 995 表述为细胞 ERK 磷酸化通路读数（HEK293 细胞、vasopressin 刺激、AlphaScreen），因此这里的 inactive 是**该 assay 条件下未达活性标准的 assay outcome**，不等同于纯化蛋白实验中对 MAPK1 的直接结合阴性，也不应无条件泛化到其他靶点/实验。

## 未进入 LIT-PCBA 清单记录的 full assay-data 复核

官方 PUG REST 对单次完整 assay 请求设有 10,000 个 SID 上限，并允许通过 POST body 提交 SID 列表。本轮将 AID 995 concise 表中的 9,067 个未出现在本地 active/inactive 清单的 SID 一次性 POST 到 `/assay/aid/995/CSV`；PubChem 返回 9,067 行、9,067 个唯一 SID（原始响应 2,475,112 字符）。其中 Outcome 再次确认 Active 403、Inactive 3,449、Inconclusive 5,215，与 concise API 计数吻合。

这些原始行还保留了 `Phenotype`、AC50/Efficacy、curve description、Hill slope、R²、curve class、每个浓度点的 activity readout 和 compound QC。未收录部分的部分描述性分布如下：

| 字段 | 未进入清单的 AID 995 记录数 | 解读边界 |
|---|---:|---|
| Outcome = Inconclusive | 5,215 | 不能并入 active 或 inactive 二元标签；这是 9,067 条差额的多数 |
| Outcome = Active / Inactive | 403 / 3,449 | 已有二元 assay outcome，但未进入本地 benchmark；具体排除原因没有随 AID outcome 字段给出 |
| Phenotype = Inhibitor / Inactive / Activator | 5,618 / 3,316 / 133 | 是 assay 的 phenotype 字段，不能和 Outcome 字段互换或直接用作 benchmark label |
| `Fit_CurveClass` = 4 / -3 | 3,316 / 2,181 | 曲线拟合分类的描述分布；仅凭这些数尚不能确认各 LIT-PCBA 过滤步骤怎样逐条作用 |
| Curve description 为空 / 单点活性 / partial efficacy | 3,316 / 2,208 / 2,255 | 表明原始 assay 记录包含远多于最终二元列表的曲线质量/观测状态信息 |

LIT-PCBA 构建论文报告从 PubChem 筛选中去除假阳性、assay artifacts 和理化偏差，并使用 AVE 划分；其创建团队的 2020 年数据集综述列出无机结构、异常 Hill slope（<0.5 或 >2）、跨 assay hit 频率 >0.26、已知 aggregator/luciferase inhibitor/autofluorescent、极端分子性质以及 3D 转换/电离失败等过滤环节。[LIT-PCBA 原始论文](https://doi.org/10.1021/acs.jcim.0c00155)、[创建团队的数据集综述](https://doi.org/10.3390/ijms21124380)。后续方法论文对该标签定义的概述指出：true inactive 是对应 PubChem assay 中未检出 hit、且仍通过 LIT-PCBA 的有机/性质等过滤条件。[Berenger & Tsuda 2024](https://doi.org/10.1002/jcc.27478)

**因此当前能下的结论是：**5,215 条 inconclusive 不应被强行纳入 LIT-PCBA 二元标签；所有 3,449 条 omitted inactive 与 Table S3 的三个过滤差额闭合，所有 403 条 omitted active 与 Table S2 六个过滤差额闭合。PubChem full assay rows 提供观测与 QC 字段，但原始 SI 只提供每步总数而没有 SID-to-step 列表。故 active/inactive 的总量来源过滤已闭合，逐条排除原因仍未核验。

## 原始 LIT-PCBA 补充信息：逐阶段总数对账

从 ACS Figshare 官方补充信息记录下载并保存 PDF：[`sources/LIT-PCBA_2020_Supporting_Information.pdf`](sources/LIT-PCBA_2020_Supporting_Information.pdf)。Figshare API 给出的 MD5 与本地文件一致：`47079F11F0D026E47A43A28484F1A0DE`。Table S3 对 AID 995 / MAPK1 的 inactive 数列为：Start 66,078；Step 1 65,908；Step 3 62,652；Step 4 / Final 62,629。差分计算为：

| 过滤步骤 | 该步前 | 该步后 | 移除数 | SI 中的过滤类别 |
|---|---:|---:|---:|---|
| Step 1 | 66,078 | 65,908 | 170 | 无机分子 |
| Step 3 | 65,908 | 62,652 | 3,256 | 极端分子性质 |
| Step 4 | 62,652 | 62,629 | 23 | 3D 转换/电离处理失败 |
| 合计 | 66,078 | 62,629 | 3,449 | 与 PubChem AID 995 inactive 差额完全相等 |

active 也可按 Table S2 对账：711 → 707 → 414 → 402 → 322 → 308 → 308，逐步移除 4、293、12、80、14、0 条，合计 403，与 AID 995 中未进入 Full 的 active 数完全一致。5,215 条 Inconclusive 不属于 SI 的 confirmed active/inactive 清单构建口径，不应将其当成被二元过滤链排除的 active 或 inactive。

Table S2 的 Step 2a–2c 只用于 confirmed actives；Table S3 的 inactive 过滤链只有 Step 1、Step 3、Step 4。过滤步骤名称/定义应引用原论文 SI，不能把后来综述的概述误作原始证据。两张表解决的是**active/inactive 类别总数的算术对账**，不是逐条化学结构复核或过滤代码复现。

### 规则定义与逐 SID 复现可行性

原作者 Tran-Nguyen 的博士论文第 3 章（与 LIT-PCBA 论文对应）给出详细规则：Step 1 排除含 H/C/N/O/P/S/F/Cl/Br/I 以外原子的结构；Step 3 要求 `150 < MW < 800 Da`、`−3.0 < AlogP < 5.0`、rotatable bonds `<15`、H-bond acceptor/donor 均 `<10`、总 formal charge `−2 < q < +2`；Step 4 用 CORINA 3.4 将 2D SDF 转 3D，再由 Filter 2.5.1.4 做标准化和生理 pH 电离，所有 preparation failures 移除。性质由 Pipeline Pilot 19.1 计算。**来源：**[作者博士论文第 3 章 PDF](https://publication-theses.unistra.fr/public/theses_doctorat/2020/Tran_Nguyen_Viet_Khoa_2020_ED222.pdf)，方法段落约 PDF 第 142–144 页；论文与 SI 仍是数据集本身的主来源。

这使重建具有部分可行性：化学元素与大多数描述符可用现代开源工具近似复算；但 AlogP 实现、结构标准化/互变异构处理和 CORINA/Filter 版本可能造成边界记录不一致。逐 SID 归因需保存规则实现与软件版本，并把结果标成“exact reproduction / open-tool approximation / unresolved”，不能假装复现了当年的专有管线。Step 4 的 23 条 aggregate loss 可能只有拿到原始输入结构与相同准备工具才可 exact match。

### 公开 CID 属性的试算（近似，不是历史管线复现）

已从 PubChem 当前 Full assay CSV 取回 9,067 个未进入 LIT-PCBA Full 的有效 SID 明细，并针对其中 3,449 条 inactive 的 3,251 个 unique CIDs 获取当前公式及性质。Step 1 优先用 assay CSV 的 `PUBCHEM_EXT_DATASOURCE_SMILES`（3,413/3,449 条有值）检查元素，CID molecular formula 作对照；两者对可同时检查的记录在“是否含非许可元素”上无分歧，均识别 234 条。Step 3 用 PubChem `XLogP`（明确不是历史 `AlogP`）和 MW/HBD/HBA/rotatable-bond/charge 作为近似阈值。结果：234 条候选 Step 1、2,515 条候选 Step 3、168 条性质字段缺失、496 条通过近似规则但仍在 Full 外、36 条无可用 CID 属性；这些计数与 SI 的 170/3,256/23 不一致。来源 SMILES 检查没有消除 Step 1 差额，因此差异原因仍未识别。

**解释边界：** 不能把 234/2,515/496 映射成真实历史筛选步骤。差异可能涉及 SID↔CID/当前结构版本、PubChem 缺失属性、XLogP≠AlogP、软件版本及结构准备；目前还没有证据分解各因素贡献。原始输入数据保存在 `data/`，近似规则脚本为 [`audit_omitted_inactive.py`](audit_omitted_inactive.py)，输出为 [`AID995_omitted_inactive_candidate_reasons_2026-09-30.csv`](data/AID995_omitted_inactive_candidate_reasons_2026-09-30.csv)。这次失败的对照本身有方法学价值：精确类别总数不能替代记录级证据链，开源替代描述符尤其不能用于伪造逐条因果解释。

### 记录日期核查：排除“晚近新增 assay 结果”作为主要解释

为判断未入选记录是否可能只是 assay 后期新增，下载 PubChem 官方 assay history dump 中 AID 995 的记录，并通过 PUG REST Record Dates 接口查询 3,449 个 omitted-inactive SIDs 的沉积/修改日期。AID 995 的官方 history 行显示：assay 沉积于 2007-12-28，test result change 日期为 2010-07-06；3,449 个 inactive SID 的沉积年份为 2005 年 1,080 条、2006 年 1,519 条、2007 年 850 条，修改年份为 2005 年 539 条、2006 年 1,512 条、2007 年 848 条、2012 年 541 条、2014 年 9 条。没有 SID 在 2014 年后修改。

**解读：** omitted inactive 不是 2020 年 LIT-PCBA 之后才新提交的记录，因此“后来新增 assay 结果”不太可能解释这 3,449 条差额；但 SID 的 ModificationDate 不能说明修改的是结构、元数据还是其他字段，也不能证明 2012/2014 年修改涉及结构或 outcome。AID 的 test-result-change 日期是 assay 级日期，不能替代每条 SID 的变更历史。日期证据因此缩小了一个假说范围，却没有提供逐 SID 的 LIT-PCBA 过滤理由，也不改变 234/2,515 等近似分类与历史 aggregate 不吻合的结论。

来源：[PubChem Record Dates](https://pubchem.ncbi.nlm.nih.gov/docs/record-dates)、[PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)、[官方 assay history dump](https://ftp.ncbi.nlm.nih.gov/pubchem/Bioassay/assay.ftpdump.history)。本地保留查询结果和校验值，见下表。

## 保留的数据工件与校验值

| 文件 | 内容/有效记录 | SHA-256 |
|---|---|---|
| [`AID995_concise_2026-09-30.csv`](data/AID995_concise_2026-09-30.csv) | AID 995 concise 全量，72,004 个 SID | `6CDC8B68D31BEDDD5AD14B61364ECB5BF8E4A270FC07E6EE566B01CB0A0E05E0` |
| [`AID995_not_in_LITPCBA_Full_2026-09-30.csv`](data/AID995_not_in_LITPCBA_Full_2026-09-30.csv) | 与 Full 清单差集，9,067 个有效 SID | `B96C3A726D66514AA60F400012BCF810B2F017FED3AA764F08A5801F95B0A063` |
| [`AID995_not_in_LITPCBA_Full_assay_rows_2026-09-30.csv`](data/AID995_not_in_LITPCBA_Full_assay_rows_2026-09-30.csv) | full assay fields；9,067 个非空 SID 行，另有 5 个 PubChem 空白行 | `A2C23B26032EC66D1CB8577ADABADEAF39673C833ED631E6CC38CF9EF9B7205E` |
| [`AID995_omitted_binary_CID_properties_2026-09-30.csv`](data/AID995_omitted_binary_CID_properties_2026-09-30.csv) | omitted Active/Inactive 的 CID 属性，3,647 个 CID | `CCD1BF2DEAC2A0DB171652AE6CA405EA4414482600B6DA93BB902BD40FA03F55` |
| [`AID995_omitted_inactive_candidate_reasons_2026-09-30.csv`](data/AID995_omitted_inactive_candidate_reasons_2026-09-30.csv) | 3,449 个 inactive SID 的近似分类结果 | `1A94127DDFAC2EE9C7F0301C12FC604C8FCBCD2429FA44050442ECFC9D581F34` |
| [`AID995_omitted_inactive_SID_dates_2026-09-30.json`](data/AID995_omitted_inactive_SID_dates_2026-09-30.json) | PubChem Record Dates 接口返回的 3,449 个 omitted inactive SID 日期 | `66080DC7E1CB2E1C8545F5815522F2D1A9B299F1C56BEF8BD96E3D9199BEB2E2` |
| [`AID995_assay_ftp_history_2026-09-30.csv`](data/AID995_assay_ftp_history_2026-09-30.csv) | PubChem history dump 中 AID 995 的单行记录 | `D1F6ECACB8C84A28282F1742C63DB611364F3A2AA7DCBF2C068E41FC1A0E80DA` |

数据源分别为 [PubChem AID 995 concise endpoint](https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/995/concise/CSV)、[PUG REST full assay endpoint](https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/995/CSV)（POST 指定 SID）和 [PUG REST compound properties](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)。Full assay 导出中的 5 条空白 CSV 行已与有效 SID 行区分，不能计为 assay observations。

## 文件计数差异

本地 MAPK1 full files 行数与唯一 SID 均为 active 308、inactive 62,629；它们与当前官方 `LIT-PCBA_full.tar.gz` 中相应文件逐字节哈希一致。AVE archive 中 MAPK1 split 为 active_T/V=231/77、inactive_T/V=46,317/15,250。inactive_T 与 inactive_V 无重复，合计 61,567；相对于完整 inactive 文件的 1,062 个差异项全部只出现在 full list，不在 AVE train/validation split。该结果将官方维护页/2024论文报告 61,567 与 full archive 62,629 的差异解释为不同处理层级的计数，而非未解释的 package mismatch。原始论文明确说 training/validation ligand sets 经 asymmetric validation embedding (AVE) procedure 去偏。[维护中项目页](https://lab.drugdesign.unistra.fr/datasets/lit-pcba/)、[原始论文 DOI](https://doi.org/10.1021/acs.jcim.0c00155)、[Shen et al. DOI](https://doi.org/10.1039/D3SC02044D)、[官方补充表 S4](https://www.rsc.org/suppdata/d3/sc/d3sc02044d/d3sc02044d4.pdf)。Shen et al. 的 62,629 before docking/62,525 after docking 属另一处理阶段，暂不将其解释成 AVE 差集。官方压缩包下载链接本轮可访问且本地文件得到字节级核验；此前 `/LIT-PCBA/...` 路径 404 是错误/旧链接，不代表正式 downloads 路径不可用。

## 对研究主线的判断

这次核查与主课题的关联度为 **3/3**：它直接暴露了一个核心方法要求——阴性标签不能脱离靶点和 assay 上下文做化合物级传播。若未来从论文、数据库或筛选表恢复阴性观察，最小记录单元应至少保留 molecule、target、assay/source、outcome、measurement/value/relation、质量标记及稳定出处；否则把“某处测得 inactive”错误并入另一任务，会制造伪阴性。

它**没有**证明文献挖掘能补充 LIT-PCBA，也没有证明保留上下文可以改善模型。此前“Level 1–3 表示是否有增益”的设想仍需基于正确配对的数据和严格对照实验。

## 下一步核查

> **更新（2026-09-30，取代下方第 1 项的“总量原因未明”表述）：** 3,449 条 inactive 和 403 条 active 的聚合过滤数均已由原始 SI 对账；后续不是再找 aggregate explanation，而是尝试逐 SID 重建过滤步骤 reason ledger。旧段落其余内容保留作研究过程记录。

1. 核对 3,852 条有 Active/Inactive outcome 但未进入本地清单的具体原因；候选规则已由论文/综述列出，仍需取得筛选代码或可校验基准包，逐 SID 还原过滤链，不把“未纳入”自动解释成未知或阴性。
2. 用官方 full/AVE 包复核其他 14 个 target 的 raw-vs-AVE counts，并确认总的 1,062 MAPK1 SID 在 AVE 排除中的分布是否可由公开 AVE split 结构解释；不要把未在 AVE split 中出现的 compounds 写成未测/全数据集排除。
3. AID 995 的 9,067 条未收录观察已取得 full assay-data；若要量化完整上下文损失，还需按相同接口取得本地 62,937 条对应 full records，并对齐过滤前后可用字段。concise CSV 仅解决标签匹配，不代表完整上下文。
4. 将 MAPK1 这条线限定为细胞通路 assay 标签的 provenance/benchmark 案例；不要将其称为 MAPK1 直接结合阴性，也不以该数据单独证明文献挖掘增益。

## 来源

- LIT-PCBA 官方页面与数据计数：[项目主页](https://lab.drugdesign.unistra.fr/datasets/lit-pcba/)
- LIT-PCBA 原始论文：[Tran-Nguyen et al., 2020, DOI 10.1021/acs.jcim.0c00155](https://doi.org/10.1021/acs.jcim.0c00155)
- LIT-PCBA 原始补充信息（Table S2/S3）：[ACS Figshare 记录](https://acs.figshare.com/articles/journal_contribution/LIT-PCBA_An_Unbiased_Data_Set_for_Machine_Learning_and_Virtual_Screening/12179940)、[补充材料 DOI](https://doi.org/10.1021/acs.jcim.0c00155.s002)；本地副本 [`sources/LIT-PCBA_2020_Supporting_Information.pdf`](sources/LIT-PCBA_2020_Supporting_Information.pdf)
- PubChem AID 995（MAPK1）：[assay 页面](https://pubchem.ncbi.nlm.nih.gov/bioassay/995)
- PubChem AID 995 concise assay outcome：[PUG REST CSV endpoint](https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/995/concise/CSV)
- PubChem PUG REST 参数、10,000 SID 限额与 POST 输入说明：[官方文档](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)
- PubChem AID 1785989（KDR）：[assay 页面](https://pubchem.ncbi.nlm.nih.gov/bioassay/1785989)
- PubChem AID 1788980（EGFR）：[assay 页面](https://pubchem.ncbi.nlm.nih.gov/bioassay/1788980)
- 本地数据文件：`LIT-PCBA_full/LIT-PCBA_full/MAPK1/actives.smi`、`inactives.smi`（仅用于本轮本地精确 SID 检查；下载包版本仍待追溯）。
