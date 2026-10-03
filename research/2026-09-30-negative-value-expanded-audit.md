# 实测阴性数据的模型价值：已有对照研究扩展核查

**更新：2026-09-30**  
**主问题关联度：3/3**（直接比较分子活性模型的标签/训练集构造策略）

## 本轮结论

“阴性数据是否有价值”已有不止一个有比较设计的分子建模先例；目前不能把问题说成无人研究。Mervin et al. (2015) 报告 negative-inclusive target prediction 优于 active-only 基线，但训练负类混合了 PubChem assay inactive 与 ChEMBL sphere-exclusion 推定负例，且测试标签并非全部实验确认。Pogodin et al. (2018) 则在 152 个激酶上直接比较靶点特异的实测 active/inactive 与跨靶点合并训练方案：总体上，靶点特异实测集合的分类及早期识别表现更好；不过 13 个激酶在早期识别上从引入其他激酶化合物的合并训练方案中获益。InertDB (2025) 还比较了不同负例来源：curated inactive (CIC) / generated inactive (GIC) 相对随机 PubChem/ZINC 抽样和 DeepCoy decoy 在若干设置更好；但以基准内实测 inactive 作同 split 替换对照时，LIT-PCBA 无显著提升，MUV 仅 CIC 子集有小幅显著提升。

两项研究共同说明，训练中放入一批被标成“negative”的样本并不保证收益；样本是否在目标 assay 实际测试、其标签如何产生、目标是否适合跨靶点迁移都很关键。它们仍没有干净回答：“在同一目标、同一批实测阳性、固定测试集与样本规模下，额外加入经核验的实测阴性，是否比匹配数量的未标注/推定负例带来独立收益？”这仍是窄而可实证检验的问题。

## 新增直接先例：Pogodin et al. (2018)

- **论文：** Pogodin et al., “How to Achieve Better Results Using PASS-Based Virtual Screening: Case Study for Kinase Inhibitors,” *Frontiers in Chemistry* (2018), [DOI 10.3389/fchem.2018.00133](https://doi.org/10.3389/fchem.2018.00133).
- **数据与标签：** 从 ChEMBL 20 处理 152 个 human kinases，最终 173,275 个 kinase-compound 活性点（62,309 active、110,966 inactive），覆盖 55,162 个化合物；用 1 μM / 50% inhibition 规则归并活性类别。外部验证使用 ChEMBL 23 中的新 compound-target pairs。
- **三种训练方案：** I-set 是每个激酶单独的实测 active/inactive；MAI-set 将不同激酶数据合并，除真实 active 外，把没有针对特定激酶活性记录的化合物设为“conditionally inactive”；MA-set 仅合并 actives。作者明确承认“conditionally inactive”可能包含未发现的真实活性物。
- **结果：** 五折和外部测试整体上 I-set 优于 MAI/MA；BEDROC 早期识别排序为 I-set > MAI-set > MA-set。按激酶分层后，13 个激酶在至少三个 BEDROC α 水平上由 MA 或 MAI 更好；作者提出目标间样本选择偏差、跨激酶共有抑制剂和化学空间差异可能解释异质性。类别比例会影响 Precision/F1，作者认为 AUC 与 balanced accuracy 对比例更稳健。
- **对 Janus 的含义：** 这是“不要把未测/无记录自动当成阴性”的直接下游模型证据，也支持按 assay/target 保留测量语境；它不是增加实测阴性的随机化消融，因为不同训练方案改变了数据来源、靶点合并方式和负类语义。
- **证据边界：** 研究使用 PASS 的 MNA 表征和其专有/专门工作流，数据过滤及标签汇总具有研究者选择；外部数据虽然是 ChEMBL 新记录，但不等于按时间登记的前瞻性预测。该论文结论不能简单推广成“实测阴性在所有分子模型中必然更好”。

## 相关证据地图（当前核验到的价值比较）

| 工作 | 对照回答了什么 | 主要结果 | 对“实测阴性独立价值”的识别程度 | 主课题关联 |
|---|---|---|---|---:|
| Mervin et al. 2015 | negative-inclusive vs active-only target prediction | 外部 WOMBAT PR-AUC 0.56 vs 0.45；BEDROC 0.85 vs 0.76 | 低至中：负例混合实验 inactive 与 sphere-exclusion presumed negatives；训练数据规模/来源不匹配；测试未注释对被视为 inactive | 3 |
| Pogodin et al. 2018 | target-specific measured active/inactive vs cross-target merged sets with untested-as-conditional-inactive; plus active-only merged set | 总体 I-set 分类与早期识别更好；13 个 kinase 的早期识别偏好 MA/MAI | 中：对“目标上未测被赋负标签”的影响有直接证据；未隔离同一 assay 内新增实测 negatives 的增量效应 | 3 |
| An et al. 2025 (InertDB) | CIC/GIC vs PubChem/ZINC random negatives and DeepCoy decoys; plus same-split replacement against benchmark verified inactives | CIC/GIC outperform random-source negatives/DeepCoy in some settings; replacement yields no significant LIT-PCBA change (CIC p=.52; GIC p=.85), while MUV CIC gives a small significant gain (p=.0032) | 中：显示负例来源/测试化学空间匹配重要；未证明生成 GIC 是实验阴性，也未证明新恢复的 assay-specific negatives 的价值 | 3 |
| Czarnecki et al. 2015 | Same target/fingerprint/classifier families evaluated on ChEMBL threshold-inactives, DUD decoys, and a mixed negative class across seven targets | Best-fingerprint BAC was ~0.875–0.919 for true-inactive sets, ~0.899–0.967 for mixed sets, and ~0.996–1.000 for DUD sets | 中：直接表明decoy任务比assay-specific measured-inactive任务容易得多；但类比例、数据量和化学空间未匹配，研究目的不是负类来源消融，不能证明实测阴性增量收益 | 3 |
| Gómez-Sacristán et al. 2024 (PD-L1) | Same patent actives trained with PubChem assay true inactives, DeepCoy or random ZINC decoys, or active-only; evaluated against true-inactive or DeepCoy test sets | Inactive-enriched models strongly outperform active-only; among inactive-enriched models, true-inactive training did not significantly outperform much larger random-decoy training | 中：直接检验阴性富集和来源；训练负例数量/总样本差异很大，且是单靶点 docking-based structure scoring | 3 |
| LIT-PCBA / MUV 等实测筛选基准 | benchmark 中以真实 assay outcomes 区分 active/inactive 并评估方法 | 支持真测阴性可用于可靠 benchmark；数据集构建和评价本身不构成加入阴性相对不加入阴性的因果比较 | 低：可评估辨别能力，不能单独识别训练收益 | 2–3 |

## 下一轮可执行的检索与复核

1. 追溯 Pogodin 文中关于 active-only、negative selection、inactive quality 的引用，区分同 assay 实测 inactive、跨靶点未测化合物、人工 decoy、sphere-exclusion 与 confirmed inactive。
2. 定向搜索“same assay/target fixed positives + measured inactives vs unlabeled/pseudo-negatives”的 controlled ablation，优先看外部/时间拆分、PR-AUC 与校准，而不只看随机 CV 或 accuracy。
3. 若找不到更干净的文献比较，把论文空白限定为“独立收益识别不足”，不能写成“阴性价值没有研究”。
4. 未来实验至少包含：固定测试集；同一批 actives；固定训练样本数和类别比例；实测 inactive、未标注/PU、匹配随机负例、decoy 分开；按 scaffold/时间/assay 外推评测；做相同特征与超参数的重复试验。

## 来源

- Pogodin et al. 2018 primary paper: [full text](https://www.frontiersin.org/journals/chemistry/articles/10.3389/fchem.2018.00133/full), [DOI](https://doi.org/10.3389/fchem.2018.00133).
- Mervin et al. 2015: [DOI](https://doi.org/10.1186/s13321-015-0098-y); detailed limitations are recorded in [`2026-09-30-negative-bioactivity-value-prior-art.md`](2026-09-30-negative-bioactivity-value-prior-art.md).
- Decoy and measured-inactive benchmark design review: [Frontiers in Pharmacology (2018)](https://doi.org/10.3389/fphar.2018.00011).
- An et al. 2025, InertDB: [journal article](https://doi.org/10.1186/s13321-025-00999-1); matched verified-inactive replacement results and training/test design were checked in full text.
- Czarnecki et al. 2015: [primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC6332304/); Tables 1 and 5 compare ChEMBL threshold-defined true inactives, DUD decoys, and their mixture across seven targets.

## InertDB 的设计与解释边界

InertDB 是主课题必须正面讨论的强先例，不宜只引用摘要中的“提升性能”。它报告 3,205 个 PubChem curated inactive (CIC) 和 64,368 个 generated inactive (GIC)。作者以 LIT-PCBA/MUV 中 verified actives 训练，并从 CIC/GIC、PubChem、ZINC 或 DeepCoy decoys 中抽取负例，固定原 benchmark verified active/inactive hold-out test set，比较 100 次随机切分。CIC/GIC 在部分模型来源比较中显著优于随机来源/DeepCoy；但同一论文另设“用 CIC/GIC 替换原 benchmark 内 verified inactives”的对照，结果为 LIT-PCBA CIC p=0.52、GIC p=0.85，MUV CIC p=0.0032（作者称轻微提升，可能与 MUV 训练集更小有关）。

因此最准确的总结是：**InertDB 证明经筛选的广谱负例比任意随机/生成 decoy 更适合某些 ligand-based benchmark；它没有普遍证明追加更多负类标签优于已有同 assay 实测 inactive。** GIC 是模型生成候选，不能作为真实测量阴性；CIC 是跨多个 PubChem assay 进行保守筛选的化合物资源，也不等同于每个目标 assay 都逐对实测为 inactive。其主要模型是 ECFP4 + random forest，指标以 AUROC 为主（另报告 MCC、balanced accuracy）；这限制其对 assay OOD、时间泛化和校准收益的推断。

## PD-L1 docking-based scoring 的直接对照

Gómez-Sacristán et al. (2024) 从两项专利整理 PD-L1 dimerizer actives，用 PubChem AID 2316 的筛选结果构建实测 true-inactive 集，并与 DeepCoy property-matched decoys、ZINC 随机 property-unmatched decoys、active-only 训练相比较。AID 2316 原始筛选 28,781 个化合物，仅检出一个 active；经 docking 后，文中测试集包含 297 个 actives 与 18,550 个 true-inactive docking instances。训练集固定 371 个 actives，但负例数和来源不同；随机 ZINC decoy 训练规模比 DeepCoy 约大 23 倍，比例可达每个 active 配 35–909 个 inactive。

作者报告，不含 inactive-enriched 训练样本时模型表现大幅下降（classification PR-AUC 不超过 .04）；但在 inactive-enriched 方案间，训练用实测 true-inactives 并未显著优于数量大很多的 random decoys；更大数量的 random decoys 能改善在 true-inactive test set 上的 SBVS。由此可以支持“对这个 PD-L1 docking-scoring 任务，负类/化学空间训练信息非常重要”，但不能分离阴性标签作用、负例数量、特征与训练采样的影响。其 classification active-only 对照还将高/低 potency 分作两类以满足二分类要求，并非与 inactive class 完全同构；regression 对照更接近只用 actives。它是单靶点、结构打分、回顾性 benchmark，不能直接外推到通用配体—靶点分类或文献阴性抽取。

- Gómez-Sacristán et al. 2024: [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11725107/), [DOI 10.1016/j.jare.2024.01.024](https://doi.org/10.1016/j.jare.2024.01.024).
