# 2026-09-30 酶—分子模型中的阴性证据先例对照

## 核查目的

比较几项最接近当前课题的工作，厘清“有人用过模型负类”“模型从负类受益”和“从历史文献恢复实测非底物证据”是不是同一个问题。不是系统综述；结果用于界定主张，不估计整个领域的覆盖率。

## 先例横向比较

| 工作 | 阴性/非正类的语义 | 已经做到 | 尚未回答的主课题问题 | 对 Janus 的关联 |
|---|---|---|---|---|
| Pertusi et al. 2017, [SimAL](https://doi.org/10.1016/j.ymben.2017.09.016) | 从既有实验/原始文献中找回受测但 inactive 的酶–化合物对；另有主动学习后新增的实验标签 | 四个酶体系的 SVM 与主动学习；作者报告用约三分之一的化合物达到约 80% 最大准确率，并验证主动选择的化合物可解决训练数据冲突、增加化学多样性 | 小规模人工回收先例已经否定“没人从文献补回实测阴性”；没有通用抽取基准，也没有把“历史文献恢复阴性”的增量与同数据量/类别比例对照隔离 | 3/3：最直接的历史文献回收先例，收窄新颖性空间 |
| Visani et al. 2021, [EPP-HMCNF](https://doi.org/10.1093/bioinformatics/btab054) | BRENDA 已知 inhibitor 记录作为相对 substrate-prediction task 的 hard negatives；这不是被测后确认的 non-substrate | 在同一批已知 inhibitor 记录上比较两种处理：作为 similarity-weighted unlabeled，或显式 inhibitor supervision。realistic split/reduced data 下 EPP-HMCNF 的 AP 0.131→0.149，R-PREC 0.111→0.126，AUROC 0.849→0.857 | 提供了模型训练中负类监督有益的较直接证据；仍未检验从文献新恢复的 substrate no-detect 数据，且 inhibitor 不是同一标签本体 | 3/3：广义效用证据；2/3：对实测非底物特定主张 |
| Goldman et al. 2022, [dense-screen model benchmark](https://doi.org/10.1371/journal.pcbi.1009853) | 六个酶家族实验筛选中的 active/inactive；标签由原文阈值对已测 pair 二值化 | 标准化多酶×多底物数据矩阵，测试 enzyme discovery 和 substrate discovery；发现当前 joint CPI 模型未稳定胜过 enzyme-only 或 substrate-only 单任务基线 | 证明规整高通量文献表格中的实测 inactive 可整理为可训练/可评估资源；不测试分散叙述抽取，也没有 active-only vs add-measured-negative 消融 | 3/3：与结构化表格 pilot 强相关；对独立负类增益不构成直接因果证据 |
| EnzymARC 2026 preprint, [benchmark](https://doi.org/10.64898/2026.08.21.746242) | 通过催化残基及其邻域结构引导突变生成的 putative non-functional enzyme decoys | 测试 EC predictor 是否被序列同源性误导；作者报告低扰动下多个模型仍大量转移原 EC | 不是实验测量的失活结果，也不做历史文献回收；DeepEC 与其他模型不同，不能由模型间差异隔离负类监督的因果效应 | 3/3：高相关竞争性 benchmark 先例；但与 assay-level negative 数据集不同 |

## 目前可以站得住的判断

1. **“阴性数据从未用于酶模型”不成立。** 既有工作至少包括实测 inhibitor 作为 hard-negative supervision，以及多篇以实测 inactive、inhibitor 或计算 decoy 构造负类/benchmark 的研究。
2. **“实测 inhibitor supervision 在某一酶 promiscuity 预测设置下可能有独立训练价值”有直接先例。** Visani 等的同记录 unlabeled-vs-inhibitor 处理对照减少了单纯样本数增加这一解释，但结论不能等同于“历史论文中的实测非底物加入后会普遍提高模型”。
3. **“从论文恢复过一些实测酶底物阴性”也已有小规模先例。** Pertusi 等人工检索并使用了文献记录；因此可能的贡献不能只写成首次回收。
4. **更窄且仍待验证的问题是：** 对一个明确的酶/生化任务，系统恢复的、带来源与 assay 条件的实测 no-detect/non-substrate 记录，是否能在匹配样本量、阳性数、模型、测试集与训练预算下，优于把这些 pair 当作 unlabeled、随机/相似性负例或不加入？
5. **适合投稿的潜在贡献应该由三块共同构成：**（a）记录级抽取/证据分型与来源可追溯；（b）对既有数据库新增覆盖的可复现估计；（c）同任务、同测试集的负类类型消融。仅有一个数据表或一次模型性能提升，不足以解决 novelty 和 causality 两个问题。

## 当前建议的最小实验逻辑

| 比较臂 | 训练信息 | 要回答什么 |
|---|---|---|
| A | 阳性 + 既有已知负类/PU基线 | 当前任务基准 |
| B | A + 文献恢复的实测阴性 | 加回这些证据的总体增益 |
| C | A + 等量、类别/化学性质匹配的随机或合成负例 | B 的收益是否只是样本量/平衡 |
| D | 将 B 的新增观察隐藏标签、当作 unlabeled | 显式证据标签是否优于“知道 pair 存在但不知道结果” |

所有臂固定测试集、模型架构、调参预算和 split；按 source paper、enzyme、scaffold/chemical cluster 或时间分组，防止来源泄漏。根据任务报告 PR-AUC/AP、balanced accuracy、校准及重复划分区间；不要只用 accuracy。先用 NIMS pilot 验证样本有足够的分子/底物多样性和可比较的活性正例，再决定具体模型任务。

## 证据边界与来源

- SimAL 的约 80% accuracy / 约 33% fewer compounds 是作者报告的主动学习结果，不是“加入历史阴性导致准确率提升”的因果估计。
- EPP-HMCNF 的 inhibitor/no-inhibitor 比较是作者报告；该设置将同一批 inhibitor observations 从未标注重新赋予 inhibitor supervision，因而比跨模型比较更接近监督标签消融，但仍是特定算法、数据与 task。
- Goldman 等使用原论文阈值对测试过的 pairs 二值化；其核心目标是严谨的 enzyme/substrate generalization benchmark，不是自由文本阴性信息抽取。
- EnzymARC 截止本核查日是 bioRxiv 预印本； decoy 的非功能性是计算构造的 putative label，不代表每条序列已做湿实验验证。

## 文件与复核入口

- 统一追踪：[`research_tracker.md`](research_tracker.md)
- 文献矩阵：[`literature_matrix.csv`](literature_matrix.csv) J034、J018、J040、J041
- 证据台账：[`evidence_ledger.md`](evidence_ledger.md) E050–E051 及对应更早条目
- 检索记录：[`search_log.csv`](search_log.csv) Q076–Q077
- EPP 公开代码与数据：[HassounLab/EPP](https://github.com/HassounLab/EPP)
