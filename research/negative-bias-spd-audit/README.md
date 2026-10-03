# SPD 公开数据的 inactive 覆盖核查

**核查日期：** 2026-09-30  
**主课题关联度：** 3/3（直接提供阴性结果在常用公开资源中覆盖不足的经验性证据）

## 来源

Sutherland, J. J., Yonchev, D., Fekete, A., & Urban, L. (2023). *A preclinical secondary pharmacology resource illuminates target-adverse drug reaction associations of marketed drugs*. Nature Communications, 14, 4323. [论文 DOI](https://doi.org/10.1038/s41467-023-40064-9) · [全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10356841/)

论文公开的 SPD 汇总数据来自 [Zenodo record 8103950](https://zenodo.org/records/8103950)，文件 `final_summarized_activity_data_pub.txt`。本地原始文件保留在本目录。

- 文件大小：16,060,609 bytes
- MD5：`621c6363ba55699d476637bc60558870`
- 数据行：121,097（不含表头）
- 处理代码：[Novartis/SPD](https://github.com/Novartis/SPD)，包括用于构建数据集的公开 notebook。

已检查 `make_all_prescribable_drug_activity_dataset.ipynb`。其中展示了用于药物/活性代谢物、结构匹配等级、首选 assay 与 assay group 的分层选择规则。这强化了“跨资源覆盖比较需要实体与 assay 对齐”的注意事项，但该 notebook 不是论文 95%/36% 比较统计的完整复算脚本。

随后也下载并核验了同一 Zenodo 记录中的 `Supplementary_Data.xlsx`（16,080,806 bytes，MD5 `abb210f3becfc8763641a976617d9b90`）。`S Data 1` 含 121,097 条汇总记录、跨资源 AC50 中位数、单浓度结果和代表 assay-group 标记，故比只用原始文本表做字段推断更适合核算覆盖率。

还检查了 Zenodo 同记录的 `Dataset_S1.xlsx`（12,203,915 bytes；MD5 `d3cfd99bf14778a8cee77e3227b2d30f`）。其 `Sheet1` 表头及 121,097 条记录与 `Supplementary_Data.xlsx` 的 `S Data 1` 逐行完全一致；这是同数据的另一份工作簿副本，未带来不同筛选口径，也未解释总体 95% 的差额。

## 论文报告

作者将 1,958 种药物对 200 个 assay 的 147,653 条浓度-反应曲线汇总为 121,097 个 drug-assay pair，并与 ChEMBL、DrugCentral 及订阅资源交叉比对。论文报告约 95% 的结果在这些比对来源中独有，且 inactive 结果的独有比例最高；对 `AC50 < 1 μM` 的活性结果，约 36% 独有。对于同时有 SPD 与 ChEMBL 数据的匹配记录，SPD `AC50 ≥ 10 μM` 的记录中，66% 在 ChEMBL 的中位 AC50 `< 10 μM`；而 SPD `AC50 < 0.1 μM` 的记录中，82% 在 ChEMBL 中也显示相近强度。作者认为这与发表/报告偏倚相符。

**解释边界：** “独有于 SPD 对照资源”不等价于“从未发表”。论文指出，某些记录可通过手动 PubMed/Google Scholar 检索找到。论文采用多个资源覆盖率作比较；测定平台、assay 构成、药物集合和活性确认流程差异也可能造成不一致。因此该研究直接支持“公共/常用汇编资源对 inactive 结果覆盖较低”，对“阴性结果因发表偏倚而未发表”的因果结论则是支持性而非决定性证据。

## 本地独立 sanity check

按补充表中的跨资源列对 121,097 行复算。将三种资源的 AC50 median 都缺失定义为“未见量化 AC50”；再做一个更宽的替代定义，将 ChEMBL/订阅资源单浓度结果也纳入“找到对照数据”的判定：

| SPD 结果分组 | 总数 | 未见对照资源记录 | 按此口径未见比例 |
|---|---:|---:|---:|
| 全部记录：三种资源 AC50 median 均缺失 | 121,097 | 8,659 | 92.85% |
| SPD AC50 `<1 μM`：三种资源 AC50 median 均缺失 | 3,069 | 1,117 | 36.40% |
| 全部记录：再把 ChEMBL/订阅资源单浓度数据纳入 | 121,097 | 9,043 | 92.53% |
| SPD AC50 `<1 μM`：再把单浓度数据纳入 | 3,069 | 1,962 | 36.07% |
| SPD AC50 `≥10 μM`：三资源 AC50 median 均缺失 | 112,800 | 107,616 | 95.40% |

活性组复算为 36.40%（仅 AC50 median）或 36.07%（加单浓度字段），与论文约 36% 相符；总体独有率为 92.85%/92.53%，低于作者报告的约 95%。因此目前是**部分复现**：公开 Supplementary Data 1 能重现活性组比例，但“总体 95%”的纳入、筛选或分母口径尚未解释。按上述三资源 AC50 列检查，SPD `AC50 ≥10 μM` 子集有 95.40% 未见对照 AC50 median；这不是论文所称 inactive 全类的完全同口径数值，不能替代作者统计。此前使用正向证据阈值的 94.81%/37.60% 仅是较粗的 sanity check，已被本次补充表核算取代。详细计数见 [`supplementary_recomputation.csv`](supplementary_recomputation.csv)。

## 对 Janus 的含义

这篇工作补强了“有证据表明 inactive 结果在常用汇编资源中的覆盖低于 active”这一问题存在性论据，也提供了可公开审计的数据与代码。但 SPD 是一组系统性预临床药理 panel，不是从历史论文全文抽取阴性结论的系统；它不提供 Janus 所需的一般化阴性文本抽取基准，也没有测量“抽取新增阴性后能否改善模型”的受控实验。因此它是强问题证据与数据覆盖参照，不是 Janus 全方案已被完成或未被完成的充分证明。

## 后续核对项

- 继续厘清总体约 95% 与补充表重算 92.5%–92.9% 的分母/代表记录/覆盖定义差异；活性约 36% 已由 Supplementary Data 1 近似复现。
- 单独查看表格中 SPD `>`/`<` 截断读数的处理，不把阈值型结果混作明确二元 inactive。
- 若进入实证 pilot，可将该资源作为已知活性证据覆盖的对照案例；在论文层面区分 source-resource undercoverage 与 true publication bias。
