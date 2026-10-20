# 抗菌肽尝试垂域核查（2026-10-20）

结论：**AMP 可以保留为备选，不推荐替换主线 β-glucosidase 成为首次试做垂域。** 主 agent 补充主线已有 3 篇原始实验全文和 7 条人工试填，重视同一检测终点及证据 QA；本分支只核实 1 篇 AMP 实验，未证明 AMP 更省事或更有增量。若并行尝试 AMP，选择“公开全文中，肽—单一 E. coli 菌株的实测 MIC、最高测试浓度无效及检测范围删失的提取与条件补全”；首次只评 MIC，溶血留作后续独立端点。当前证据支持提取可行性，尚不支持数据库漏收或 LLM 收益已成立。

文献事实来自公开原始实验及官方资源，最终采用 5 个证据源，详见 [sources.md](sources.md) 和 [evidence.csv](evidence.csv)。β-glucosidase 的 3 篇全文及 7 条人工试填是主 agent 提供的项目状态，本分支未独立检查其内容，不能视作自动抽取指标。本次未读取或修改用户 Excel，以下“可补全”指原文可提供字段，不表示 Excel 中已确认缺失。

## 真实实验：一个表格能区分删失与高 MIC

原始研究为 2021 年 *Overlapping Properties of the Short Membrane-Active Peptide BP100 With (i) Polycationic TAT and (ii) α-helical Magainin Family Peptides*。已实际阅读全文 Materials and Methods 的 MIC / Hemolysis 两节，Results 的相应两节，表 1、表 2 与脚注及图 2 图注；没有仅凭摘要下结论，也没有将未读取的补充材料计作证据。[S1：原始实验全文](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full)

表 2 的 TAT 行含以下三个本研究新测结果（列组脚注 a）；脚注 e 解释最高测试浓度下未见效应：

| 实验对象 | 原始 MIC（μM） | 可保留的证据语义 |
| --- | --- | --- |
| TAT—E. coli DSM 498（K12） | >500，带脚注 e | 最高测试浓度未见效应；MIC 右删失，不是精确值 500 |
| TAT—Enterobacter helveticus DSM 18396 | 500，无脚注 e | 有限的高 MIC；不能自动改成 inactive |
| TAT—Kocuria rhizophila DSM 348 | 125，无脚注 e | 有限的高 MIC；不能自动改成 inactive |

位置：[表 2 及脚注 a/e](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full#T2)。TAT 是文中实际测过的细胞穿透肽比较对象，不是从未实验的随机序列；应标注 comparator 身份，不能据此将所有 CPP 当负例。表中其余四个细菌列属于脚注 b 的旧研究结果，不能套用本篇新实验条件或重复计算为新实验。

### 现有 Excel 记录能从哪里补字段

若现有行是“TAT / E. coli / MIC >500 μM”，可按下表回溯。字段补全和阴性证据发现应分别统计。

| 字段 | 原文位置及可恢复内容 | 处理规则 |
| --- | --- | --- |
| peptide_name / sequence | 表 1：TAT，GRKKRRQRRRPPQ，13 aa | 保留原文身份；不要与其他 TAT 截短体合并 |
| species / strain | MIC 方法节：E. coli DSM 498（K12） | DSM 498 与表中旧研究 DSM 1103 分开 |
| endpoint / relation / value / unit | 表 2：MIC / > / 500 / μM；脚注 e | 原始字符串与结构化字段并存；右删失标记独立保存 |
| evidence_scope | 表 2 脚注 a 与 e | 本研究实测；测试范围内无效，不外推永久无活性 |
| assay_medium | MIC 方法节：1% trypticase soy broth（TSB） | LB 是前培养基，不能误当 MIC 测定培养基 |
| inoculum | MIC 方法节：加入 50 μL、10^6 CFU/mL 菌悬液，总体积 100 μL | 最终 5×10^5 CFU/mL 是按稀释推算，须标 derived；原始值同时保留 |
| temperature / duration | MIC 方法节：37°C、overnight | 时间保留 overnight，不能猜为 18/24 h |
| assay_format / decision_rule | MIC 方法节：96 孔、二倍稀释、每肽三次；至少两次抑制生长的最低浓度 | 不改写成平均 MIC |
| controls | MIC 方法节：无肽的生长对照、未接种对照 | 未接种 negative control 不是“阴性肽” |
| pH / salt / plate_material | 所读 MIC 方法未给出明确数值或材质 | 留空或 not_reported；不借用溶血实验条件 |

表 1 定位：[肽身份](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full#T1)。方法定位：全文中 “Minimum Inhibitory Concentration (MIC) Assay”。500 μM 边界按表格原样记录；本次没有从储备液信息独立重建完整浓度序列，不把方法推算值覆盖原表。

同篇表 2 的 MAG2 为 HC10 >100 μM，TAT 为 HC10 >>100 μM；Results/Hemolysis 与图 2 图注说明 TAT 在测试范围几乎不溶血。应保留 `>>100` 原记号；若系统只能存单个比较符，可另存保守下界 >100，并标“归一化丢失程度信息”。这不等于溶血百分比为零，也不等于临床安全。Hemolysis Assay 能补出人红细胞、最终 0.25%（v/v）、37°C、20 min、Tris 缓冲体系 pH 7.6、540 nm 读出及 Triton X-100 完全裂解对照。文中三次吸光读数不能擅自改称三个独立供者。[S1：表 2 与方法](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full#T2)

## 数据库核查：已有基础相当强，缺口尚未证

**DBAASP 已有实测不活跃数据和条件。** v3 原始数据库论文的 “Distinction from other databases of the general type” 明确说明收录不依赖肽被判为 active 或 inactive；“Ranking search page” 明列 assay medium 与 CFU 条件；“Data collection” 说明人工读文献提取结构、活性和毒性；“API page” 说明可按 URL 获取单条和查询集合。因此，“现有库只有正例”“库没有实验条件”都不能成立。论文关于其他数据库的比较是当年的陈述，不能外推为 2026 年 DRAMP 现状。[S2：DBAASP v3](https://pmc.ncbi.nlm.nih.gov/articles/PMC7778994/)

**DRAMP 至少已有条件化无溶血的明确表达。** 官方 Help 的 General Data → Activity Information 中，Target Organism 包括靶标与 MIC；Hemolytic Activity 示例是人红细胞至 50 μg/mL 无溶血，附原始文献号。该页面也列出末端修饰、立体化学和文献字段。这证明“无溶血及浓度范围”已在其表达能力中；帮助页示例不等于本次逐条确认其现行记录完整性，也没有证明 DRAMP 系统收全抗菌无效结果。[S4：DRAMP Help](https://dramp.cpu-bioinfor.org/static/help.php)

**不能按旧帮助页认定当前 DRAMP 缺乏结构化字段。** 2026-10-20 所见官网标为 V5.0，更新日志记载 2026-02-28 将 Target Organism 从文本改为结构化表，2026-04-08 扩展可下载活性信息，最近更新为 2026-10-19。Help 仍有 4.0 措辞，存在文档版本差异；本报告不将旧版字段列表当作当前导出模式。[S5：DRAMP 官网及更新日志](https://dramp.cpu-bioinfor.org/)

本次**没有**完成 TAT—DSM 498—该 DOI—MIC >500 这一实验键与两库当前条目的对账，也没有比较现有 Excel 行，故无法声称发现了一条数据库/Excel 漏收阴性。数据库官方介绍证明的是已有能力，不能证明覆盖率、遗漏率或本项目净增量。后续应以 DOI＋序列/修饰＋菌株＋端点＋条件逐条对齐，分别记录“新实验行”“已有行补字段”“冲突”“已完整收录”；库中未检索到的结果仍不是实验阴性。

## 公开可用性和许可

| 资源 | 本次核实的许可与访问事实 | 实际选材建议 |
| --- | --- | --- |
| S1 实验全文 | 文章尾部列 CC BY；全文表格和方法直接可读 | 优先此类有明确开放许可、可定位表格的原始实验 |
| DBAASP 数据 | 当前官方 Terms 的 Data Access Policy 明确允许访问、下载、复制、使用、改编、再分发，要求署名 DBAASP；外链原文权利另行适用 | 保存该政策链接、查询日期和来源署名；不把论文许可当数据许可 |
| DBAASP v3 论文 | 论文为 CC BY-NC 4.0 | 与上行数据库数据政策分开记录；论文文本再利用须按其自身许可 |
| DRAMP 数据 | 当前官网写明 CC BY 4.0、可下载/提取；要求引用原作者及库论文，并对 patent AMPs 提及授权 | 首轮仅用一般学术文献及对应 general 数据；不混入专利条目 |

许可来源：[S1 文章版权说明](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full)、[S2 论文版权说明](https://pmc.ncbi.nlm.nih.gov/articles/PMC7778994/)、[S3 DBAASP 当前政策](https://dbaasp.org/terms-and-conditions)、[S5 DRAMP 官网](https://dramp.cpu-bioinfor.org/)。本次仅核查访问和声明，未批量下载或再分发数据库与全文。

## 明确排他性选择

针对首次试做的直接比较：

| 判断维度 | β-glucosidase 主线（主 agent 提供） | AMP 本分支（实际核查） | 选择含义 |
| --- | --- | --- | --- |
| 现成可检查材料 | 3 篇实验全文，7 条人工试填 | 1 篇原始实验全文，定位到实测删失 MIC；无人工逐行试填集 | 主线具备更具体的现成 QA 起点；数量本身不是抽取效果指标 |
| 同一终点 | 主线要求以同一检测终点组织；是否已经完全对齐未由本分支核验 | MIC 可单独组织；溶血是另一终点；表内还混有旧研究列 | AMP 不宜首轮同时做 MIC 与溶血；不能因同为肽活性而混合 |
| 证据 QA 工作 | 已有人工行可作为待审参考；质量仍须核验 | 需建立表头—脚注—方法链接，保留菌株、比较符、条件及旧研究归属 | AMP 尚未表现出更低 QA 成本 |
| 新增价值 | 本分支未核查 | DBAASP 已有实测阴性及条件；DRAMP 已有无溶血表达；尚未对账 | 大数据库只提供基线和来源，不能支持优先改域 |

据此，**第一次 API 提取试做继续 β-glucosidase；AMP 作为备用的删失与跨段条件补全用例**。这项排序依据项目准备程度和当前证据边界，不是两个领域抽取难度或收益的实验比较。若之后 AMP 能提供与主线相同规模、同一 MIC 终点的人工金标准并证实新增实验/字段，再重新比较。

AMP 内部取舍如下：

| 方案 | 判断 | 原因 |
| --- | --- | --- |
| 肽—单一 E. coli 菌株 MIC，保留删失并补条件 | 若试 AMP，仅选此项为首次任务 | S1 有可直接定位的真实表格结果，方法可回填，且能在同一肽内检查高 MIC 与无效的区别 |
| 同肽人红细胞溶血 | 后续独立端点，首次不混评 | 可关联效力/毒性证据；其“无效”方向与抗菌端点不同，不能共用阴性标签 |
| 全菌种混合 MIC / 肽级 AMP–non-AMP 二分类 | 不选为首轮 | 丢失菌株、条件和删失语义；已有成熟数据库，泛标签提取难表明新增价值 |
| 生物膜、协同、多肽混合物或泛细胞毒性 | 本轮排除 | 超出限定任务；会引入不同端点和实验对象，当前证据未建立统一提取规则 |

相对“泛 AMP 标签抽取”，推荐的是实验粒度恢复；相对“重新做一个阴性肽库”，推荐的是对现有库和 Excel 的可审计增补。若对账发现既有记录及条件已经齐全，应将此域定位为提取校验/格式对齐试点，而不是继续声称阴性发现优势。以上为基于现有证据的取舍，没有编制分数。

## 两个 LLM 下游：仅为设计，尚无已证收益

导师设定的提取路径应为“提供 API 的通用大模型读取方法＋结果＋表格/脚注，输出带位置的结构化实验记录，人工复核”；本次未调用收费模型。补充材料只有实际读到且有独立定位时才纳入；本例不声称用过补充材料。

- **RAG 可回答的问题：**“在这篇 BP100 研究中，TAT 对 E. coli DSM 498 是否在最高测试浓度下抑制生长？这能否推成对所有细菌无活性？”期望答案检索到表 2、脚注 e 和 MIC 方法，答 >500 μM 的范围内无效；同表另两菌存在有限 MIC，因此不能泛化。上下文同时返回菌株、培养基、时间和出处。
- **小参数语言基座模型能学习的任务形式：**给定表格行、脚注和方法片段，输出带 evidence locator 的 JSON，包括 peptide、strain、endpoint、raw_value、relation、unit、censoring、conditions、asserted/inferred/not_reported；缺条件时输出 null。同一原文中有限高 MIC 与 > 上界作为真实对照。训练方式保持未定，不擅自指定微调、蒸馏或继续预训练。
- **待验证指标设计：**人工核对实测阴性召回、删失/单位准确率、字段证据支持率、无依据补全率；RAG 比较已有记录与增补记录的带引文答题差异；小模型若实施训练，再检验结构化提取与范围外推错误。按论文与肽家族隔离评测，避免表格行泄漏。没有训练或收益数值；RF、AdaBoost 等分类结果不能作为语言模型或 RAG 的效果证据。

首轮继续条件是：用小批开放全文及现有 Excel/数据库配对人工金标准，确实找到可复核的新实验记录或条件增量。这里是后续设计，当前只完成公开证据核查与方案收束，未执行对账、训练或模型评估。
