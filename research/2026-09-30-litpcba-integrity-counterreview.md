# LIT-PCBA 基准完整性审计及反向核查

**核查日期：** 2026-09-30  
**关联度：** 3/3。LIT-PCBA 将实验确认的 active/inactive 筛选结果用于虚拟筛选评价；其负例含义和拆分质量直接影响我们能否用该资源检验阴性数据的模型价值。  
**证据级别：** 预印本方法与作者代码已查；技术反驳为作者博客，不能与独立同行评审研究等同；当前无法运行完整复现，因为官方拆分包链接返回 404。

## 结论先行

LIT-PCBA 适合继续作为“实验 inactive 可获得且可与具体筛选 assay 对应”的数据来源候选；目前不应把它默认当作干净的模型泛化 benchmark，也不能照单全收“整套 benchmark 已失效”的单方结论。2025 年 arXiv 审计发现的部分“完全重复”是在忽略立体化学的 2D 表示下成立；后续技术评论报告保留立体化学后 exact isomeric-SMILES 跨集合重合归零，但也指出多数传统 2D 指纹默认不感知手性，因此相同 2D 表示、同标签的立体异构体仍可能奖励 stereo-agnostic 模型记忆。结论必须区分精确分子身份、2D 表示相同、近似物重合和真正的 scaffold/OOD 泛化。

**对主课题的具体影响：** LIT-PCBA 中的实测 inactive 可证明“负例存在并可用于筛选 benchmark”，但其常规 split 上的模型分数不足以单独证明“阴性数据带来独立收益”。后续收益实验应回到 AID 995 的 assay 级记录，以 CID/SID 和实验状态为单位构造去重/匹配对照；并对立体化学、analog proximity、split、类别基线分别控制。

## 审计预印本报告了什么

Huang、Knight 与 Naprienko 的 arXiv v2（2025-08-07）审查 LIT-PCBA 的 query、training、validation 三部分。作者报告：跨 target 有 2,491 个 stereo-agnostic 2D-identical inactive 出现在 train 和 validation；训练/验证集内部也有 inactive 重复；ALDH1 有 323 对 active train–validation 分子在 ECFP4 Tanimoto ≥0.6；作者还报告 query/train/validation 之间出现 query 重合。作者以无可学习参数的 ECFP4 相似度基线，在原始数据设置下取得 median raw EF1% 4.15，接近其对比的 CHEESE 3D encoder，并指出 raw EF 对筛选库大小和类别比例敏感。[arXiv v2](https://arxiv.org/abs/2507.21404) · [审计代码仓库](https://github.com/sievestack/LIT-PCBA-audit)

作者自己的 v2 将去除立体化学描述为诊断 stereo-agnostic identity leakage 的操作，而非要求所有模型都忽略 stereochemistry。其 baseline notebook 用 RDKit Morgan radius 2 / 4096-bit 指纹；代码未启用 chirality 参数，因此这一 baseline 针对的是不感知手性的 2D 表示。作者的主张和单方结论应按其具体 representation 与目标泛化任务解释。

## 反向核查：哪些发现稳固，哪些结论需要收窄

| 论断 | 支持证据 | 反向核查 / 限定 | 当前可采纳结论 |
|---|---|---|---|
| “2,491 个 inactive 是 train–validation 完全相同的分子” | 预印本及其公开 README 报告该数；作者按 non-isomeric canonical SMILES 计 2D identity | Lžičař 的后续技术博客报告复跑：这些 stereo-stripped identity overlap 在原始 isomeric SMILES 下均为不同立体形式，保留 stereochemistry 后 exact identity overlap 归零；属于技术博客而非独立同行评审论文，仍值得按公开代码复核 | 应称“achiral/2D representation 下完全相同的结构”，不能不加限定地称为相同立体化学分子跨 split 泄漏 |
| 该重合是否仍会影响模型 | 许多 Morgan/ECFP 基线默认不编码手性；audit baseline 本身也如此 | 3D 方法、启用 chirality 的 2D 方法可能区分这些结构；相同 2D 表示对 stereo-blind 模型是现实挑战，但不是对所有表示都构成相同强度的泄漏 | 将 2D stereo-blind 与 stereo-aware / 3D 模型分层比较；不能由 2D overlap 推断所有 3D 模型被同等破坏 |
| 323 对高相似 active 足以证明 train–test leakage | 预印本按 ECFP4 Tanimoto ≥0.6 报告 ALDH1 train–validation active analog pairs | 近似分子跨随机 split 既可能是记忆捷径，也可能是实际 ligand-based screening 的插值任务；0.6 是宽松的相似度阈值，影响强度取决于阈值分布、任务目标和化学簇边界 | 支持“原 split 不能代表未见 scaffold 泛化”的担忧；须报告分子相似度分布/分层指标，而非把任何近邻跨 split 都称作数据泄漏 |
| 简单基线匹配 3D 模型说明 benchmark 一概无效 | 作者报告其 baseline median raw EF1% 4.15，且与 CHEESE 多 query 设置作比较 | raw EF 对 target size 和类别比例不稳；作者也报告 nEF；CHEESE 对照是否严格复现依赖相同 query 处理、库定义和指标实现；arXiv 预印本结论未经此处独立复跑 | 这是强烈的 benchmark 警报，不是本轮已独立证明“全部历史结果失效” |
| LIT-PCBA 应停止使用 | 预印本作者主张现有 benchmark systemic flaws 不适合泛化评测 | 同一数据仍然含有按 PubChem assay 整理的实验 active/inactive；对不同任务可保留为标签来源或筛选deck，不等于其随机/AVE split 能支持新颖性泛化结论 | 保留其数据/来源价值；限制其作为未经审计模型价值证明的用途 |

技术反驳来源：Miroslav Lžičař, “Do Stereoisomers Cause Leakage? A Closer Look at the LIT-PCBA Audit”, 2025-08-08。[原文](https://www.mireklzicar.com/blog/stereoisomers/)。该文承认 v2 已回应“为何忽略立体化学”的质疑，并认为 stereochemistry-consistent/discordant 分层、手性敏感性对照和按任务解释更合适。其观点属技术评述，未替代我们自行复算。

## 可复现性现状

1. GitHub 审计仓库公开了 notebook 和 query ligand mapping 表，但未托管用于 train/validation 审计的 split archive 或校验和。`lit-pcba.ipynb` 运行时下载 `http://drugdesign.unistra.fr/LIT-PCBA/Files/AVE_unbiased.tgz`；该链接现在重定向至新域后返回 404。
2. 官网当前列出的 `LIT-PCBA_AVE_unbiased.tar.gz` 和 `LIT-PCBA_full.tar.gz` 下载链接本轮 HEAD 检查也都重定向后 404。此前工作区中的本地 `LIT-PCBA_full/...` 有 active/inactive 文件，但无 audit notebook 所需的 `active_T.smi`、`inactive_T.smi`、`active_V.smi`、`inactive_V.smi`，且本地 inactive 计数 62,629 与官网 61,567 不同；它不是可直接替代的同版本拆分包。
3. 因此本轮核验停在：阅读 arXiv v2、核对作者 notebook 表示参数/下载路径、交叉检查技术反驳；**没有声称复现了 2,491、323 或 EF1% 结果**。可安全继续的办法是寻找可校验的同版 AVE split 镜像或从官方 2020 论文/补充文件重建拆分，然后保留原始与 stereo-aware / stereo-blind 两套结构键，按 MAPK1 单独复算。

## 对主课题的决策

- **保留** LIT-PCBA/AID 995 作为真实 inactive 和 assay provenance 对照资源；原始 inactive 是 assay-specific，不应脱离 AID 995 迁移到别的靶点。
- **暂停** 将 LIT-PCBA 通用 split 上的表现作为“负数据改善泛化”的主要实验证据。
- **模型可行性实验前置检查：** exact isomeric identity duplicates、stereo-stripped identity、近邻分布、assay/source provenance、class ratio 和 split generation 全部记录；报告 stereo-blind 与 stereo-aware 指纹基线、scaffold/temporal split、PR-AUC / ROC-AUC / calibration 以及按 target 分布的 normalized enrichment，而非仅 raw EF1%。
- 本方向关联度仍为 **3/3**，因为它直接决定负标签模型收益是否被重复、近邻和表示选择混淆；但它不是“阴性数据是否存在”的证据，也不能替代文献恢复率 pilot。
