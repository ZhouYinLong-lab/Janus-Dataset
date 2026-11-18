# 主张三：恢复的数据是否改善模型

## 主张

与只使用成功/阳性记录或人工构造负例相比，加入来源明确、带实验条件的阴性观察，能够在严格外部分割下改善预测、校准、排序或实验决策。

## 当前判断

`supported_in_specific_tasks`。

这条主张不是空白，但结果不是“阴性越多越好”。Raccuglia 等把失败合成记录用于材料发现；Mervin 等在靶点预测中报告 negative-inclusive 模型优于 active-only，但负类混有推定负例且对照组成不匹配；Pogodin 等发现靶点特异的实测 active/inactive 标签总体优于把未测当作条件性阴性，但不同靶点存在例外；InertDB 相对随机负例或 DeepCoy decoy 在一些设置有收益，却没有一致优于 benchmark 自带实测 inactive 的替换对照。Visani 等在酶 promiscuity 任务中把同一批已知 inhibitor 记录分别作为显式 hard negatives 或 similarity-weighted unlabeled，EPP-HMCNF 在 realistic split 下数项指标提高，是较直接的同记录监督对照；但 inhibitor 不是实验确认的 non-substrate。Czarnecki 等在七个靶点比较实测 inactive、DUD decoy与混合集，DUD上的 balanced accuracy接近1、实测inactive上明显更低，说明负例来源会改变benchmark难度，而不是证明实测阴性增量有益。Toniato 等的反应论文也显示失败数据在特定反应任务中有用，但不能直接外推到生物活性模型。详细比较见 [`evidence.csv`](evidence.csv)、[`../../2026-09-30-negative-value-expanded-audit.md`](../../2026-09-30-negative-value-expanded-audit.md) 和 [`../../2026-09-30-enzyme-negative-label-prior-art-comparison.md`](../../2026-09-30-enzyme-negative-label-prior-art-comparison.md)。

真正尚未解决的是更严格的问题：从文献恢复的、带来源证据与 assay 上下文的实测非底物/no-detect 观察，是否比等量、同分布且标签语义明确的数据库实测 inactive、已知 inhibitor 或合理未标注/PU 基线提供额外收益；这种收益能否在 scaffold、时间、assay 或实验室外测试中成立。Visani 等已证明同一批已知 inhibitor 的显式监督相较 unlabeled 处理可改善某个酶任务，但不能代替对文献恢复的 measured non-substrate 做检验。目前的证据不是空白，也没有直接解决 Janus 的严格主张。

## 建议的因果式消融

固定模型、阳性训练集、总训练预算和数据切分，只改变阴性数据来源：

1. `P`：仅阳性数据；
2. `P + random`：随机或未标注样本作负例；
3. `P + decoy`：性质匹配的构造负例；
4. `P + database inactive`：数据库现有阴性标签；
5. `P + Janus context-free`：恢复记录但移除上下文；
6. `P + Janus full`：恢复记录并保留证据、条件与置信度。

主结果不能只报告随机切分 AUROC。至少加入时间切分或 assay/项目外切分，并报告 PR-AUC、校准误差、top-k 命中、适用域/拒答质量，以及按每条专家复核记录计算的增益。

## 风险

- 模型收益可能来自样本量、任务提示或标签清洗，而非“阴性”本身。
- 文献阴性记录往往经过选择性报道，不代表真实实验失败分布。
- 错误阴性比漏掉一条阴性更危险，尤其在活性和安全性任务中。
- 单任务收益不能支持“统一数据集改善所有分子模型”的结论。

## 可投稿的最低证据

至少两个性质不同的任务，各自包含真实外部分割；`Janus full` 相对强负例基线有可重复增益；误差条和统计检验完整；进一步证明上下文字段或证据置信度对结果有贡献。若只有一个任务，应把论文定位为该领域的高质量数据与方法工作，而不是全分子科学统一结论。
