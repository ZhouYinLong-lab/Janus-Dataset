# Assay-Aware BindingDB：竞争性工作核查

**核查日期：** 2026-09-30  
**版本状态：** arXiv v1，提交日期 2026-09-27；预印本，尚不能按同行评审论文表述。另发现一个高度相关的公开 Hugging Face 数据工件，论文页面没有显式链接，上传者为匿名账号，二者关系应称“高度可能相关/配套”，而非已证实作者发布。  
**关联度：** 3/3（直接覆盖“从文献结构化实验上下文，并测试上下文是否改善分子模型”；不直接研究阴性结果）。

## 工作做了什么

Wu 等提出 Assay-Aware BindingDB：对 BindingDB 中四类亲和力 assay（ITC、SPR、RBA、FPA）的蛋白—配体记录，从关联原始论文抽取结构化实验上下文，再把上下文嵌入输入 Boltz-2 affinity module。作者称筛选 113,311 个候选 pair、检索到 5,991 篇可访问论文，最后得到 74,425 个带上下文的 pair。抽取评估从四类 assay 各抽 30 篇论文，报告字段存在性 F1 至少 0.947、语义内容准确率至少 0.913。模型按 PMID 做 paper-level split，10 次拆分比较完整模型、无上下文模型及 context-only 模型；论文报告组合测试集 65,169 条中，加入上下文后 MSE 由 1.27 降至 1.19、Pearson r 由 0.64 升至 0.67、c-index 由 0.73 升至 0.74，三项跨拆分差异均报告 p<0.001；ITC 的 MSE 反而变差，RBA 的 MSE 改善未达显著。结果是作者报告，未独立复现。[arXiv v1](https://arxiv.org/abs/2609.34001)

## 公开数据工件核查

Hugging Face 上存在同名的 [`anonymousapple/Assay-aware-BindingDB`](https://huggingface.co/datasets/anonymousapple/Assay-aware-BindingDB) 仓库。平台 API 显示其于 2026-05-07 创建、2026-07-31 更新；仓库公开且未设登录门槛，卡片未列明确 license，当前文件树中未发现 Python/R/notebook/shell/YAML 代码。该账号资料标为 anonymous，arXiv v1 正文/页面未给出这个仓库链接，因此不能确认账号身份或精确对应的论文版本。

平台数据服务当前报告 `default/full` 有 269,023 行，四个 assay 子集行数合计也是 269,023；合并所有配置和不同 seed 的切分后平台总计 1,200,886 行，这个总数包含重复出现在 default、assay-specific、train/validation/test 与多组 seeds 中的数据，不能当成 120 万条独立观察。**一个强关联证据**是四个 `*_seed_0` 配置的 train+validation+test 行数分别为 ITC 1,761、SPR 3,650、RBA 44,223、FPA 15,535，合计 65,169，恰与论文表 3 的合并测试队列计数一致；HF 卡片也称这些 seeded configurations reproduce 论文 downstream experiment data。这使其非常可能是论文配套工件，但不消除“论文未链接、匿名上传、版本与全量口径不同”的限制。

HF 卡片声明模型复现实验只纳入恰有一个正数值的 Kd/Ki/IC50 且关系符不是 `<` 或 `>` 的记录。full 数据仍保留了 `affinity_data.relation`、原始论文段落、`search_path`、补充材料路径及结构化条件。通过 viewer 的首 100 行示例中有 35 行为 `>` 截断值（这是展示顺序样本，不是总体比例估计），例如 `Kd > 50,000 nM`；这些是有 assay 语义的右删失定量结果，可能提示很弱结合/未达测量范围，但**不能不经判定直接重标为实验 inactive**。它们确实被保留在 full artifact，但排除在所述模型训练兼容切分之外。

## 与本课题的关系：哪些主张已不能单独作为创新

| 主张 | 该预印本的影响 | 仍需核查的边界 |
|---|---|---|
| 用 LLM/agent 从分子文献抽实验条件并转为结构化数据 | 已有直接先例；公开配套型工件还保留原始段落和结构化上下文 | 仅覆盖 ITC/SPR/RBA/FPA，且许多来源文献/补充材料取不到；HF 账号匿名且论文未显式指向，归属/版本需谨慎表述 |
| 结构化上下文能改善分子模型 | 作者报告了 paper-level held-out、10 次拆分、context/no-context/context-only 对照和若干模型指标 | 比此前理解的证据更强；但没有识别到 assay-type-only 或简单 context 基线，且独立复现/统计集群结构/模型实现仍需核验 |
| 构建“带上下文的分子数据集” | 74,425 条论文报告的带上下文 pair；一个可能配套 HF full 配置当前报告 269,023 行，并保留原文段落、标签关系与结构化上下文 | 论文表中 candidate/final 数与 HF `default/full` 行数差异很大（113,311 / 74,425 vs 269,023），口径/版本/重复与筛选关系未解释；不能按单一数据量等同 |
| 收集删失的弱亲和力观察 | HF full 数据示例保留 Kd `>` 等关系值和原文上下文 | 这构成与“低于检测能力/很弱结合”相关的直接先例；HF 卡片说模型 split 排除 `<`/`>`，是否用其明确表示阴性需 assay-specific 复核 |
| 抽取明确阴性结果/区分未测与实测无效 | 论文的主要任务是连续 Kd/Ki/IC50 亲和力和 assay-context；未见显式 inactive 状态分类目标 | arXiv 全文搜索未命中 `inactive`/`negative data`，但配套型 full 文本中可能包含负向文字或删失观察；必须抽样逐条审，不可推断“阴性都不存在” |

## 需要保留的谨慎点

1. 论文链接层面没有列数据/代码地址；同名 HF 仓库是真正可访问的数据工件，但 anonymous uploader、缺明确 license/代码、与论文无显式 cross-link。我们可核验 API 可见行数/样例，不等于验证完整语料来源、抽取正确性或作者身份。
2. 评估抽样是每种 assay type 30 篇论文；作者将字段存在性和语义准确性分别评价，不能将其中任一指标等同于“阴性证据抽取精确率”。
3. 74,425 是保留下来的 protein–ligand affinity pairs，不是 74,425 个互相独立的论文或实验，也不能与不同来源/不同定义的阴性数据集直接比总量。
4. 论文比较了上下文与无上下文、context-only，并按 PMID 切分；这比“未排除样本量/泄漏影响”的宽泛质疑更充分。仍未见仅加 assay type / 仅加来源简单特征的基线，也不能把其结果外推为改善 active/inactive、未检出识别、校准或 OOD 泛化。
5. 右删失 `>`/`<` 亲和力是重要边界样本：它可在某些 assay 和 cut-off 设定下支持“很弱/未达到可测结合”的判断，但关系符和 assay 方向本身不能构成跨任务的 inactive 标签。其训练集主动排除这些观测，给我们提出 censored-aware model 或 typed negative task 留下候选切口；切口价值仍未证实。

## 对主课题的直接修正

当前不能把拟议贡献写成“首次从分子文献挖掘实验上下文，并证明上下文改善分子模型”。较窄且仍可检验的差异应是：

- 将目标明确为论文/表格/补充材料中的 **assay-grounded negative observations**，而非泛化的 assay metadata；
- 区分实测 inactive、低于检测限/截断值、定性 no activity、相对弱活性、未测试、失败及推断负例；
- 与 BindingDB、PubChem、LIT-PCBA 等结构化资源做逐观测匹配，估计**新增且可追溯**的阴性证据比例；
- 先证明抽取精确率、上下文完整度和人工复核成本，再以相同训练样本规模/类别比例的对照测试阴性信息的独立价值；
- 将 paper-level / temporal / scaffold / unseen-assay 泛化、校准列为候选终点，而不是预设每个终点都会受益。

## 后续复核问题

1. HF `full` 269,023 行与论文表中 113,311 candidates / 74,425 retained 的映射是什么？查 data JSONL/SID reactant set 去重、四 assay 过滤及版本。
2. HF `*_seed_*` 切分是否包含训练所需 embeddings / 完整配置与代码？模型数据可访问但复现依赖的 Boltz-2、Qwen3.5、大型 GPU 及输出生成路径是否公开？
3. 从 HF `>`/`<` 及原文片段中抽样，人工判断哪些是真正可作为 negative/censored evidence，哪些是方法定义的测量关系，避免把高 Kd 直接重标 inactive。
4. 论文是否进行仅 assay type / 仅 paper-source / assay-cluster 简单基线？上下文贡献能否复现、按 assay-type 与独立论文估计不确定性？
5. 该预印本后续是否同行评审、HF 仓库是否明确认领/提供许可证和代码？持续追踪。
