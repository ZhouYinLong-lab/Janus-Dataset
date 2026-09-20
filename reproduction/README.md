# PU learning 论文最小复现

目标论文：

Song et al., *Inferring protein sequence-function relationships with large-scale positive-unlabeled learning*, Cell Systems (2021).

上游材料：

- `pudms-upstream/`：作者发布的 PUlasso 分析包；
- `pu-learning-paper-analysis-upstream/`：作者发布的论文分析仓库（第一次浅克隆因网络中断未完成，保留目录仅作下载痕迹）；
- `run_author_example.R`：调用作者自带 Rocker 示例的复现脚本；
- `results/author_example/`：运行日志和输出结果；
- `reports/`：复现说明与结果解释。

## 复现边界

本阶段不是声称完整复现论文全部十个数据集，而是完成三步：

1. 验证作者公开代码和示例数据能够在当前 Windows + R 环境运行；
2. 保存作者示例的交叉验证 ROC、最优 `py` 和模型参数；
3. 再增加一个独立的“已知真值”模拟实验，比较把未标注样本错误当负例与 PU 方法的差异。

论文原始结果涉及十个深度突变扫描数据集、原始测序文件和较大的预处理过程；完整复现需要继续下载 SRA 数据并核对 Supplemental Table 1，不能用一个小例子替代。
