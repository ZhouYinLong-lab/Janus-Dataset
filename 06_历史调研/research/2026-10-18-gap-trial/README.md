# 2026-10-18 有限调研与试做

先读[这轮调查与试做汇报](这轮调查与试做汇报.md)。它解释实际多做了什么、结果意味着什么，以及目前仍不能回答什么。

| 需要什么 | 文件 |
| --- | --- |
| 六个问题的状态和依据 | [gap跟踪表.csv](gap跟踪表.csv) |
| 最接近的文献抽取工作 | [抽取相关工作核查](抽取相关工作核查.md) |
| 阴性来源及条件的模型证据 | [模型价值相关工作核查](模型价值相关工作核查.md) |
| 三篇按序论文的获取与证据尝试 | [逐篇记录](三篇正文取证试做.md)、[证据表](正文证据试做.csv) |
| GH1试验的固定规则 | [实验事先约定](实验事先约定.md) |
| 每条输入及来源 | [源单元格审计](source_cell_audit.csv)、[模型输入](model_observations.csv)、[配对条件汇总](pair_condition_audit.csv) |
| 模型结果 | [均值与范围](metrics_summary.csv)、[逐次指标](metrics_by_seed.csv)、[配对差值](paired_real_minus_no_context.csv)、[比较图](context_comparison.png) |
| 复核和复跑 | [折外预测](out_of_fold_predictions.csv)、[划分检查](split_checks.csv)、[运行清单](run_manifest.json)、[脚本](run_context_trial.py) |
| 留存的原始证据 | [sources目录](sources/) |

复跑命令，在仓库根目录执行：

```powershell
python research/2026-10-18-gap-trial/run_context_trial.py
```

需要现有的 numpy、pandas、scikit-learn、openpyxl、matplotlib；实际版本已记录在运行清单中。沿用既有两份原始工作簿、蛋白序列和序列核查表，不下载大型模型。复跑会重写本目录中的派生CSV、JSON和比较图，不修改原始数据或事先约定。

此次完成一次固定试验，不进行参数搜索，也没有把五次共享数据的重复划分称作五个独立生物实验。原始PDF未全部取得；全文XML、书目摘要XML和获取失败应按不同证据等级使用。

维护时还修复了既有文献矩阵J013行的CSV格式：给含逗号的两个字段补引号，并保留原来缺失的限制列为空。该行文字没有改写；此前的格式会使标准CSV读取把它拆成22列。
