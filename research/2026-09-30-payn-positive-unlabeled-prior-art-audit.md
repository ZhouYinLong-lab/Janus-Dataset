# PAYN：有机反应数据正—未标记学习补负例的直接先行工作

**日期：** 2026-09-30  
**关联度：** 3/3（直接涉及报告偏倚、缺失负例、负例补充和下游模型表现）  
**用途：** 收紧 Janus-Dataset 的跨领域新颖性判断；不是对 PAYN 代码的独立复现，也不是对模型实现的完整审稿。

## 工作概要

Boser、Spies 与 Glorius 于 2026 年在 *Journal of the American Chemical Society* 发表 PAYN（“Positivity is All You Need”），研究有机反应产率预测中成功反应偏多、低产率/失败结果不足的问题。作者使用 spy-based positive-unlabeled (PU) learning，从未标注反应池中筛出 reliable negatives，再将其加入正例用于反应产率回归。论文及开源仓库定位均把它作为处理有机反应“missing negative data”的框架。

作者用四个已有完整产率标签的高通量反应集合模拟报告偏倚：Ahneman Buchwald–Hartwig 3,955 条、Stevens Ni 催化硼化 779 条、Perera Suzuki–Miyaura 5,760 条，以及 Neves 非组合 Buchwald–Hartwig 数据。二分类筛选时将 yield `>20%` 定义为 positive；已知负向结果从标签可见集合中移除，剩余未展示真值的正、负结果组成 unlabeled pool。下游比较 positives-only、PAYN增强和全标签模型，作者报告前三个集合的误差差距分别缩小 61%、47%、33%；Ahneman 例中 MAE 从 11.1% 降至 6.8%，Perera 例中绝对降幅 1.6%。Neves 数据有 11,328 条实际反应、来自约 1,150 万候选空间；以同一 20% 阈值划分，positive 少于 29%，报告的 PAYN reliable-negative 集合可达到 97% 真负例比例。数值均为论文作者报告，当前审计未独立重跑。

## 与 Janus 主问题逐项对照

| 主张 | PAYN 已经做到什么 | 仍未做到/不可据此声称什么 |
|---|---|---|
| 阴性缺失是否影响分子模型 | 在有机反应产率任务中，用全标签 HTE 数据模拟只公布成功结果，再比较 positives-only 与 PU增强回归；作者报告增强模型 MAE 降低 | 这是特定领域与人为构造缺失机制的实验；不证明所有分子任务或蛋白生物活性任务均有同样效果，也不单独隔离负例数量、类别重平衡与PU策略各自贡献 |
| 能否从“未知池”补出负例 | 可由正例和未标记反应结构推断 reliable negatives，并在已知真值的 HTE 池评估 precision/recall | 被补出的 RN 是模型推断标签，并非从来源论文中抽取的作者明确阴性陈述；也不是为每条候选补回 DOI、证据句、表格坐标、assay 条件和阈值的观察级证据对象 |
| publication/reporting bias 是否已被定量测出 | 作者将“报告偏倚”作为问题动机，并用完整 HTE 标签构造偏倚模拟 | 关键性能试验是删除/隐藏完整 HTE 集中的负标签，不是利用有发表/未发表全历史的登记数据估计真实发表概率，也没有实测“某领域有多少失败实验未发表” |
| 是否已有可投稿的相邻框架 | 是：PAYN 是同行评审的 JACS 论文并公开 Python 框架；“首次将可靠负例补入反应产率模型”的宽泛贡献不能再作新颖性主张 | 其研究对象是反应记录，负例是PU推断标签；不等于小分子—蛋白 bioactivity 文献中已完成的历史阴性证据抽取、语义标注和数据库逐观察增量覆盖审计 |

## 对其证据的审慎解释

1. **标签定义由研究者设定。** `yield >20%` 为 positive 的门槛适合该 benchmark 设计，但 `yield ≤20%` 混合零产率和低但非零产率，不能自动等价于“反应失败”或所有领域通用的阴性标准。
2. **评估是完整标签数据上的删失模拟。** 这为已测反应提供已知真值，可检验PU算法能否恢复隐藏的标签；它比拿未标注文献直接验证更强于算法评估，但没有检验从原始论文恢复原作者已记录的失败结果。
3. **作者描述的 SCAR 假设需与真实文献选择过程区分。** PU推断依赖已标记正例能代表潜在正例的一组假设；论文同时承认文献/反应数据还受化学家按化学直觉、先例和成功可能性选择底物/条件的 selection bias 影响。故其模拟偏倚下的结果不应直接外推为已解决真实文献的全部选择机制。
4. **实验室数据与论文数据的证据粒度不同。** HTE 表格通常提供同一反应设计矩阵的实测产率；文献中的阴性证据可能为正文限定句、表格空白/破折号、阈值值、图中曲线或补充数据。模型推断一个低概率候选，不会自动产生上述来源证据或判明“未测/未报告/测了但无响应”。

## 对 Janus-Dataset 的影响

这篇论文**显著收窄跨领域定位**：若研究维持“覆盖所有分子科学，解决阴性数据缺失并验证模型价值”，反应科学已有非常接近的成体系工作；不能把“负例帮助模型”或“由正—未标记数据补充负例”单独包装为创新。

仍可检验的更窄问题是：

- 在生物活性/酶学论文中，作者**实际测量并报告**的 inactive、below-threshold、no-detect、weak/relative、未测或含糊结果，能否按 observation 级别恢复？
- 相对 ChEMBL、PubChem、BRENDA 等现有资源，这些来源链接记录能带来多少**精确且上下文更完整的新增观察**？
- 若把真实来源确认阴性、删失测量、PU推断RN、生成decoy分别纳入同一任务，在固定训练预算、类别比例与分组/时间切分下，各自是否有不同模型收益？

PAYN 应作为“模型侧推断补负例”的强先行基线，而不是与“历史实测阴性文本/表格挖掘”混成同一种方法。把二者拆开，反而能使后续贡献表述更清晰：**恢复来源已存在但结构化资源缺失/语境丢失的实测证据**，而非把未知样本预测成新的负例。

## 可复核来源

- Boser, F.; Spies, J. C.; Glorius, F. (2026). *Yield Prediction of Organic Reactions in Biased Data Sets via Positive-Unlabeled Learning*. JACS 148(14), 15066–15075. [DOI 10.1021/jacs.6c00127](https://doi.org/10.1021/jacs.6c00127); [PMC全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13088182/)。
- [作者公开 PAYN 代码仓库](https://github.com/GloriusGroup/PAYN)：可见模块包括 PU splitting、spy 注入、reliable-negative 识别与 regression；仓库 README 声明 MIT 许可、Python 3.12 与测试套件。该审计只核对公开仓库结构和 README，未安装、运行或验证这些测试。
- 前身预印本：[ChemRxiv DOI 10.26434/chemrxiv-2025-hq4rx](https://doi.org/10.26434/chemrxiv-2025-hq4rx)。本表按 2026 年同行评审版为准。

## 后续核验优先级

若开展复现，优先固定一个小型公开 HTE 数据集，确认其代码中 train/validation/test 分割、PU mask 是否只在训练集生成、调参是否接触真值标签、每折是否类别/反应组交叉；随后对比论文表值并加入匹配样本数的 positives-only 与随机/阈值负例基线。完成算法复现之后，再问它能否作为“推断负例”对照加入 Janus 的 bioactivity 文献恢复实验。该复现是优先的可行性工作，但不应替代实际文献抽取的金标准研究。

## 实现与复现边界复核（2026-10-01）

为判断“完整复现是否值得继续”，进一步检查了公开代码的固定快照 `e3f12fde506d1adfc0a178eb87b5f21a8f4a0ed8`，并在独立Python 3.12.13环境运行作者测试和一折烟测。

### 代码/数据核对

- 仓库根目录主程序 `run_spy.py` 读取 `config.yaml`，默认5折、每个Bayesian optimization 50次；数据工作簿指向 `Dreher_and_Doyle_input_data.xlsx` 的 `FullCV_01`。仓库跟踪的两个xlsx分别有3,955和5,760条数据行，规模与论文Ahneman、Perera集合相符；没有在仓库跟踪数据里发现论文的779条Stevens或11,328条Neves集合。因此公开主仓库中能直接定位的 benchmark 材料并非论文四组数据全套；仅据行数/文件名判断的映射仍需以数据原始来源核验。
- 根目录主流程先完成整表特征化，再用 `KFold(shuffle=True)` 做随机行拆分。超参数目标在验证集上计算；`test_data`传到最终训练函数，测试指标只在logger存在时记录。所查路径没有显示测试标签进入优化目标，故不报告测试泄漏。
- PU增强的负例在回归重组时统一赋一个固定产率标签；从科学问题角度，这表示被加入模型的是算法判定的RN并赋定值，而不是恢复到的逐反应实测产率。
- `Experiments/README.md` 将实验目录脚本标为 Legacy，并提醒其可能不反映当前API。论文数值复现前必须逐图表确认所用脚本、数据和配置，不能把当前根目录主程序自动等同于发表时完整实验流水线。

### 可执行性检查与一折烟测

- 在隔离环境中，`run_spy.py`可导入；用符合项目声明范围的MLflow 2.17.2及新建的独立file store运行作者测试，结果为 **130 passed, 16 warnings**。之前误用MLflow 3.x并复用工作目录的file store时，两个评测日志测试因store配置兼容失败；改为项目支持的2.x和fresh store后通过。测试通过只覆盖仓库测试本身，不等同于指标复现。
- pandas 3.0.6下，真实数据的PU拆分在将字符串角色值写入float dtype列时抛出`TypeError`，尽管单元测试通过。将隔离环境改为pandas 2.2.3后，同一路径可以继续执行，但会出现未来dtype兼容警告。没有修改作者克隆或Janus环境来“修补”这一点。
- 随后运行了Ahneman规模表的**一个随机外层fold**：3,955总行，train/validation/test分别为2,847/317/791；小型CatBoost（100棵树、不做Optuna搜索）识别342条RN，隐藏真标签评估precision为92.98%。下游单折MAE为positive-only 14.134、PAYN增强7.479，差值−6.655。该结果在符合项目MLflow 2.x范围的依赖环境下复跑一致。它说明核心程序路径在pandas 2.2.3下能执行，并与作者报告方向一致；它**不是**论文指标复现或独立效用证据：单fold、超参数设置缩水、RDKit/Optuna等版本未完全匹配、数据预处理/划分未与论文逐项确认，而且两组训练样本量与标签构成不同。
- 可复跑脚本和原始输出见[`reproductions/payn/README.md`](reproductions/payn/README.md)、[`run_payn_smoke.py`](reproductions/payn/run_payn_smoke.py)、[`smoke_result.json`](reproductions/payn/smoke_result.json)。

### 当前决策与关联性

PAYN不仅是概念上的强先例，其开源实现也已在一折缩小烟测中跑通，增加了“PU推断负例可带来反应产率模型收益”的本地可行性证据。完整5折/50次搜索仍未复现，且并非Janus主课题的直接终点。为了避免课题漂移，接下来更值得优先推进的是来源确认生物活性/酶学阴性：盲样本标注、记录级现有数据库重叠，以及在固定样本量/类别比例下检验负例证据类型的独立模型贡献。若后续把PAYN用于实验，应作为“模型推断RN”对照，而非用更多算力重做其反应领域结论。
