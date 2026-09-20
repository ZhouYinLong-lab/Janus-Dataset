# Song et al. PU learning：第一阶段复现记录

## 目标

复现作者 `pudms` 包自带的 Rocker 示例，确认作者代码、R 依赖和示例数据在当前 Windows 环境中可以运行，并保存一个可重复的模型输出。

这不是论文十个数据集的完整复现。论文原始分析还涉及多个深度突变扫描数据集、原始测序文件、Bowtie2 映射和补充表格；本阶段只验证公开代码链路。

论文与上游材料：

- [论文全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7856229/)
- [作者 PU 包](https://github.com/RomeroLab/pudms)
- [作者分析仓库](https://github.com/RomeroLab/PU-learning-paper-analysis)

## 环境

- Windows
- R 4.6.1
- Python 3.13.12
- `pudms` 1.1（作者仓库版本）
- `PUlasso` 3.2.6
- `PRROC` 1.4
- `ggplot2` 4.0.3

## 运行方式

在仓库根目录执行：

```powershell
Rscript reproduction/run_author_example.R reproduction/results/author_example
```

## 已完成结果

作者示例使用 Rocker 的正向筛选序列和未筛选序列，进行 10 个 `py` 值、5 折交叉验证。当前运行得到：

- 交叉验证校正 ROC AUC：约 `0.817`；
- 选择的未标注集合阳性比例 `py`：约 `0.003979`；
- 生成 `author_cv_fit.rds`、`py_grid.csv`、`Rocker_CV_ROC.png` 和 `run.log`。

由于作者示例脚本未固定随机种子，不能把这一数值直接当作论文表格的精确复刻；本项目脚本已经固定为 `20260921`，后续可以检查不同随机种子的稳定性。

## 初步判断

1. 公开代码链路可运行，说明第一阶段环境复现成功。
2. `pudms` 的实际计算并不依赖高端 GPU；本次运行使用 R 的 CPU/多进程完成。
3. 这一步只证明“作者示例可以运行”，还没有证明 PU 方法在真实任务中普遍优于其他方法。
4. 下一步必须加入普通监督基线、已知真值模拟和至少一个独立数据集，才能讨论方法效果。

## 已知真值模拟 sanity check

另运行了 `run_pu_synthetic.py`，在“只有随机一部分真实阳性被标记，其余样本全部未标注”的模拟机制下重复 20 个随机种子。这个实验不是 Song 等人 PUlasso 的复现，而是验证一个基础逻辑：把未标注样本直接当作阴性会导致概率校准偏差。

20 次平均结果：

| 指标 | 直接把未标注当阴性 | PU 校正 |
|---|---:|---:|
| ROC-AUC | 0.869 | 0.869 |
| Average Precision | 0.849 | 0.849 |
| Brier score | 0.280 | 0.160 |
| Log loss | 0.779 | 0.681 |

解释：在这个随机标记假设下，PU 校正主要改善概率尺度和校准，排序指标不一定改善，因为除以一个正常数不会改变排序。这一点很重要：不能看到“加入阴性/PU 方法”就默认 AUROC 一定上升，必须事先说明要改善的是排序、分类阈值、概率校准还是外推泛化。

该模拟的结果文件位于 `../results/synthetic_pu/`，包括每个随机种子的指标和汇总表。

## 相关产物

- `../run_author_example.R`
- `../results/author_example/run.log`
- `../results/author_example/author_cv_fit.rds`
- `../results/author_example/Rocker_CV_ROC.png`
- `../run_pu_synthetic.py`
- `../results/synthetic_pu/`
