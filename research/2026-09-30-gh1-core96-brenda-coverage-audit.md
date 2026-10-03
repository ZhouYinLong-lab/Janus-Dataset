# GH1 NIMS 核心候选池扩展至 96 个蛋白的 BRENDA 覆盖核验

**日期：** 2026-09-30  
**关联度：** 3/3（直接检验候选阴性池能否在既有酶数据库中找到蛋白实体与底物记录）  
**本轮问题：** 对完整的 expression-binary-one GH1 `<0.1` 候选池做蛋白序列级 BRENDA 交叉匹配，并检查精确匹配蛋白的酶学记录页，而不是从小样本推算全池。

## 结果

Heins 等 GH1 NIMS 补充表中，expression-binary-one 核心池包含 **1,803 个低于报告背景阈值的源单元格**，来自 **96 个蛋白、277 个酶–底物配对**；它们不是1,803个互相独立的实验对象。对这96个源蛋白名逐一尝试 NCBI 交叉核验后，86个有可用的版本化 GenBank accession，另10个是未能解析为 accession 的样本/宏基因组标签。NCBI E-utilities记录与FASTA均保留在本目录；NCBI文档说明 EFetch 支持 accession.version 列表请求：[NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/)。

下载 BRENDA 四个由 NCBI EC qualifier 指向的 EC 序列集合（3.2.1.21、3.2.1.23、3.2.1.85、3.2.1.86）并做完整氨基酸序列精确比较后：

- 86个有 accession 的蛋白中，**64个**在这四类 BRENDA FASTA 中有精确序列匹配，对应核心池 **1,176/1,803 个**源 `<0.1` 单元格；
- **33个**同时命中相同 EC 类别，对应 **597个**源单元格；
- 其余31个精确序列匹配仅在不同 EC 集合中出现，另有22个 accession 在这四个已下载集合里无精确命中；10个无 accession 标签仍无法做同等级匹配。

“无精确命中”只指本次下载的四个 EC FASTA 集合；它不排除其他 EC、别名、其他 BRENDA 页面或原始文献中存在该蛋白。BRENDA 官方的序列搜索入口见[Sequence Search](https://www.brenda-enzymes.org/sequences.php)。**序列命中表示蛋白实体可见，不表示 NIMS 测量或阴性结论已经入库。**

对匹配记录按其 BRENDA UniProt × EC × organism 组合逐页运行动态页面并确认页面身份，最终 **76/76 页均完成身份核验**（64个不同样本蛋白在不同 EC 条目下可对应多个页面）。其中70页的 Substrates/Products、Natural Substrates、References 三个可见表计数均为0；**6页有至少一类非零记录**。这些是“页面存在酶学/文献记录”，不能据此断定存在目标阴性观察。

逐行检查这6个非空页后，筛出 **9条**“精确样本蛋白 UniProt ID + 候选池底物名称”重合记录；9条都属于 *Phanerodontia chrysosporium* GH1 蛋白 Q25BW5（样本 accession BAE87008.1）的 cellobiose，分别出现在普通底物表与天然底物表。原始 NIMS 补充表对该 accession 有 **6个** cellobiose `<0.1` 单元格（pH 5/8 × 60/80/90°C；pH 5/8、40°C处未列 cellobiose 值）。关键的是，BRENDA 的一条记录评论明确写着 **“substrate of isozyme BGL1B, but not of isozyme BGL1A”**；BRENDA将Q25BW5标注为BGL1A、Q25BW4标注为BGL1B，引用 679851 对应的原始结构研究也报告 BGL1B 能有效水解 cellobiose，而 BGL1A 不能。[BRENDA 引用记录 679851](https://www.brenda-enzymes.org/literature.php?e=3.2.1.21&r=679851)、[记录 678852](https://www.brenda-enzymes.org/literature.php?e=3.2.1.21&r=678852)、[Nijikken et al. 2007](https://doi.org/10.1016/j.febslet.2007.03.009)。由于 BRENDA 该底物表把多个同物种异构酶 UniProt ID 放在同一聚合记录中，必须读评论和源文献才能正确把否定限定到 BGL1A；只看“cellobiose”底物行会产生错误的阳性理解。

这构成本轮一个经过边界控制的**既有阴性记录先例**：BRENDA 的正文式 commentary 能保存“对特定 isozyme 非底物”的自然语言阴性信息。该评论可追到 Nijikken 等 2007 年论文；PubMed 摘要直接说 BGL1A 不水解 cellobiose，而 BGL1B 能水解。[PubMed PMID 17376440](https://pubmed.ncbi.nlm.nih.gov/17376440/)。Heins 2014 NIMS 表中同一精确蛋白的6个 cellobiose `<0.1` 测量与此方向一致，但这不是逐观测复刻：BRENDA 没有在当前记录里给出对应 NIMS 的 pH、温度、检测阈值或Heins来源链接。出版社全文PDF在本次核验中返回403，因此未据摘要补写2007实验条件。这个发现既**收窄了**“既有酶数据库完全没有底物阴性陈述”的主张，也没有解决“历史文献中测量级阴性观察能否被系统恢复、保留条件和来源并验证覆盖增量”的问题。逐行结果见 [`brenda_core96_substrate_overlap_rows.csv`](pilots/gh1-nims/brenda_core96_substrate_overlap_rows.csv)，source-to-source 边界表见 [`brenda_core96_source_traceability.csv`](pilots/gh1-nims/brenda_core96_source_traceability.csv)。

我又对6个非空精确页的所有展开表格行做了小范围 negative/qualifier 词项扫描，而不是只查候选池三个底物：得到 **4条**可能相关评论，其中 **1条**为上面的 BGL1A/cellobiose 精确底物重合；其余包括对4-nitrophenyl xylopyranoside的“low activity”或“no activity”评论，属于 assay/人工底物证据，不等同于本池的 xylobiose。故扫描器的命中仍须按蛋白异构体、底物结构和文献逐项人工判读；不能把词面相似自动计作目标阴性观察。查询结果见 [`brenda_core96_negative_comment_candidates.csv`](pilots/gh1-nims/brenda_core96_negative_comment_candidates.csv)，复现脚本为 [`audit_brenda_core96_negative_comments.py`](pilots/gh1-nims/audit_brenda_core96_negative_comments.py)。

## 对主课题的意义

本轮把此前只基于 GH1 100-row pilot 所涉及的34个 accession 做的 BRENDA 检查，扩展到了96蛋白核心池，并显示：**至少64个核心池蛋白作为序列实体出现在所查 BRENDA 序列集合中；在一个蛋白–底物重合案例中，BRENDA commentary 已保存异构酶限定的明确非底物陈述，但仍没有据此证明 Heins 论文中的特定 `<0.1` NIMS 观察已被逐观测收录。** 这把下一步从泛泛的“有没有数据库记录”收窄为记录级对照：蛋白、底物、assay、条件、观测方向和引文是否一一对应。

这还**不是**历史文献抽取的性能评估，也不是全 BRENDA、全数据库或全分子科学覆盖率估计；不能据此声称数据库独有率，也不能支持阴性数据改善模型的因果结论。单篇 GH1 NIMS study 的密集数据适合做结构化抽取/上下文保真试点，不足以代表分散文献的文本挖掘难度。模型效用仍需固定测试集、分组切分与负例类型匹配后单独检验。

## 可复现材料

- 核心池与分组审计：[`2026-09-30-gh1-nims-pool-granularity-audit.md`](2026-09-30-gh1-nims-pool-granularity-audit.md)、[`gh1_nims_negative_candidates_all_2076.csv`](pilots/gh1-nims/gh1_nims_negative_candidates_all_2076.csv)
- NCBI核对：[`audit_core96_ncbi_crosswalk.py`](pilots/gh1-nims/audit_core96_ncbi_crosswalk.py)、[`gh1_nims_core96_ncbi_crosswalk.csv`](pilots/gh1-nims/gh1_nims_core96_ncbi_crosswalk.csv)、[`gh1_nims_core96_ncbi_sequences.fasta`](pilots/gh1-nims/gh1_nims_core96_ncbi_sequences.fasta)
- BRENDA序列覆盖：[`audit_brenda_core96_sequence_coverage.py`](pilots/gh1-nims/audit_brenda_core96_sequence_coverage.py)、[`brenda_ec_sequence_core96_audit.csv`](pilots/gh1-nims/brenda_ec_sequence_core96_audit.csv)、四类 FASTA 保存在 [`research/sources/brenda-gh1-ec-fasta/`](sources/brenda-gh1-ec-fasta/)
- 动态精确页及底物重合：[`audit_brenda_core96_activity_views.py`](pilots/gh1-nims/audit_brenda_core96_activity_views.py)、[`brenda_core96_exact_activity_views.csv`](pilots/gh1-nims/brenda_core96_exact_activity_views.csv)、[`audit_brenda_core96_substrate_overlaps.py`](pilots/gh1-nims/audit_brenda_core96_substrate_overlaps.py)、[`brenda_core96_substrate_overlap_rows.csv`](pilots/gh1-nims/brenda_core96_substrate_overlap_rows.csv)
- BRENDA有限页面自由文本筛查：[`audit_brenda_core96_negative_comments.py`](pilots/gh1-nims/audit_brenda_core96_negative_comments.py)、[`brenda_core96_negative_comment_candidates.csv`](pilots/gh1-nims/brenda_core96_negative_comment_candidates.csv)
- 精确 source-to-source 核验：[`brenda_core96_source_traceability.csv`](pilots/gh1-nims/brenda_core96_source_traceability.csv)
- 阴性语义的源论文：Heins et al. 2014, [DOI 10.1021/cb500244v](https://doi.org/10.1021/cb500244v), [PMC全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC4168791/)
