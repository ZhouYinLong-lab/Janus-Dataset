# 文献阴性抽取小试验

先读[本轮抽取汇报](本轮抽取汇报.md)。它回答这次实际怎么挖、挖到了什么、哪里会错。

| 用途 | 文件 |
| --- | --- |
| 看一个完整操作例子 | [一次抽取是怎么完成的](一次抽取是怎么完成的.md) |
| 直接读取3条条件性阴性 | [negative_records.csv](negative_records.csv) |
| 重点证据及未决项 | [extracted_observations.csv](extracted_observations.csv)，共9项 |
| 全部候选的判读 | [原始候选](rule_candidates.csv)、[逐项决定](candidate_decisions.csv)，各32处 |
| 检查漏检和分歧 | [盲读参照](blind_reference.csv)、[读取边界](盲读取证说明.md)、[对照裁定](reference_adjudication.csv) |
| 查看六个问题的最新状态 | [gap跟踪表.csv](gap跟踪表.csv) |
| 看取得和未取得的论文 | [13篇获取表](paper_access.csv)、[全文资格](fulltext_eligibility.csv) |
| 查原始证据 | [sources/](sources/)，3篇PDF/XML、两份DOCX补充材料及Figure6原图；下载状态见[evidence_downloads.csv](evidence_downloads.csv) |
| 回查文本位置 | [paper_text/](paper_text/)、[source_blocks.csv](source_blocks.csv)；B编号由程序生成，不是原论文页码 |
| 复查规则、版本和校验值 | [事先约定](事先约定.md)、[获取清单](collection_manifest.json)、[检查结果](pilot_summary.json)、[原始来源校验值](source_checksums.json) |

在仓库根目录复跑：

```powershell
python research/2026-10-18-extraction-pilot/collect_and_scan.py
python research/2026-10-18-extraction-pilot/download_evidence.py
python research/2026-10-18-extraction-pilot/verify_and_summarize.py
```

前两个脚本下载/解析来源及生成候选，使用已有本地文件时不重新下载。第三个核对CSV、来源标识、表行完整度及人工填写的裁定，并生成阴性子表和汇总。下载需要requests，检查需要pandas；没有安装新依赖。

`extracted_observations.csv`和`candidate_decisions.csv`由助手逐条判读，脚本不能重建这些语义决定；它不是全自动标签系统。以后修改抽取规则，要另外保留新旧结果，不能把同一开发样本上的修改报告成外部测试。

初版19处候选和198个文本块保存在`*_initial.csv`及初版JSON中。修正版保留旧B编号，在文末追加嵌套表的独立行列；新结果为247个文本块、32处候选。没有将不同版本的候选ID混用。

盲读者完成取证时未读通补充文件；主助手随后从官方来源取得两份DOCX并检查相关说明，又视觉核对原始PDF和Figure6。两阶段的可读材料范围应分别理解，不能把后来的来源检查归功于最初的盲读。

本轮不包含模型训练、数据库新增量核验、Zotero导入或专家独立标注。原始观察的使用仍须遵循各来源许可。
