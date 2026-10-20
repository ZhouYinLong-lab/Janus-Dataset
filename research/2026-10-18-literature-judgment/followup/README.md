# 第二轮：用更直接的对照回答两个问题

日期：2026-10-18。先读[两个判断](两个判断.md)；需要追查时看[逐篇核查](逐篇核查.md)与[本轮证据表](补充证据表.csv)。[上一轮及本轮总表](../证据总表.csv)已合并为50项工作和线索。

现有[文献中非结构化阴性证据的提取与使用：调研判断与后续尝试](研究路线评估报告_原文与文献依据.md)已按原始探索任务重写：保留提取可行性与使用价值两个判断，以正文括号链接引用论文，不用文献编号或表格，展开支持证据、反面证据与判断边界。[修改前版本](研究路线评估报告_修改前留档.md)另行留档，其中较强的否定措辞不代表修订版结论。

## 实际完成范围

- 本轮补查17项L34–L50，保留15份全文原件、2份题录摘要。阅读深度逐项记录，不是17篇全部精读。
- 与旧中央矩阵同DOI/URL的有L39/J034、L49/J041，明确作为复核；其余未匹配不证明此前完全没读过，也不证明文献首次发现。
- 新获得的主要区分是：普通模型的局部自动化与完整实验记录不同；实测标签与随机负类的训练作用需要直接比较；存在增益也存在替代、无额外改善和指标权衡。
- 本轮没有启动模型推理、训练或湿实验，没有安装工具、创建提交、推送或导入Zotero。

## 来源和原页

`sources/`保留公开PDF/XML及摘要元数据；`text/`和`reading_text/`是原文转换，不是人工金标准。`source_manifest.json`记录下载地址、状态、字节与SHA256；失败项也保留。`verification.json`只是文件完整性检查。

已渲染并实际视读Cáceres预印本第34页Table1、Assay Frames第7页Table4；Cáceres第10页只留渲染，未另作图像视读。没有把文字转换、下载成功或哈希一致说成专家验证。

## 本轮检索与选择

检索聚焦两类判别性证据，不做无限制主题扩张：

1. `confirmed inactive randomly selected compounds negative training`、`stochastic negative addition`、`inactive subset generation`、`negative positive ratio screening database size`；追到Cáceres、PADIF、Kurczab系列，并回查酶EPP对照。
2. `negative results biomedical relation extraction`、`event negation extraction`、`discourse-wide assay frames`、`DeepEventMine negation`；核查FNU、BioContext、DeepEventMine、全文框架、INDRA和Vapur的实际评价对象。
3. 另看PreSEPM作为缺标签的替代路线，Polak作为小模型过滤与人工总成本参照；不把模型新颖或成绩高当成阴性挖掘价值证据。

优先原始方法和对照，综述与二手搜索页只作追引。非穷尽检索，不声称系统综述。检索可见片段只支持其能看到的部分，不算完整阅读。

## 有界获取失败

- Pertusi：Europe PMC全文XML500，公开OSTI PDF超时；只保留正式摘要并读了索引可见段。
- Heikamp：ACS正文403，保留正式摘要，不报未经核对的结果方向和数值。
- RELATE PDF403、DeepEventMine补充PDF403、DORA-XGB正文403，未据片段报核心定量结论。
- Cáceres学位论文备用下载403，但目标论文的公开预印本已获取，不影响该版本的阅读；未假装已逐项比对正式版全文。

下载路径仅用公开论文/作者存储库/API，没有绕过付费或权限限制。

## 结构检查

```powershell
D:/Environment/Miniconda3/python.exe research/2026-10-18-literature-judgment/build_reading_texts.py
D:/Environment/Miniconda3/python.exe research/2026-10-18-literature-judgment/audit_review.py
D:/Environment/Miniconda3/python.exe research/2026-10-18-literature-judgment/followup/audit_followup.py
```

这三项分别生成转换文本/来源清单、检查总表与旧矩阵对应、生成本轮17项视图并检查下载哈希。均不运行科学实验、不产生阴性标签，也不验收研究结论。
