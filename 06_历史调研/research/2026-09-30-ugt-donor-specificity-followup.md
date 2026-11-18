# UGT 供体特异性样本：GuUGAT 阴性标签来源复核

**日期：** 2026-09-30  
**主课题关联度：** 3/3（阴性标签来源、可追溯性及实验语境）；0/3（没有直接检验模型收益）  
**对应记录：** T106、E089、J061、Q115

## 问题

分层抽样中的 Xu et al. (2016) 记录把 GuUGAT 对 UDP-glucose 和 UDP-galactose 的反应标为阴性。本次检查关注：原始论文是否真的测试了这些供体，以及公开证据是否足以逐一核验每个供体—受体组合。

## 样本行核对

从 Zenodo UGT donor compilation 按 DOI `10.1111/nph.14039` 精确筛出6行：

| 受体 | UDP-Glc | UDP-Gal | UDP-GlcA（数据表 donor `Glu`） |
|---|---:|---:|---:|
| Glycyrrhetinic acid | 0 | 0 | 1 |
| Glycyrrhetic acid 3-O-glucuronide | 0 | 0 | 1 |

供体 `Glu` 的 CID 94715 指向 glucuronic acid；在该供体语境下，对应 UDP-glucuronic acid（UDP-GlcA），不是 UDP-glucose。表中0/1是汇编标签，不应在缺少测量定义时直接解释成统一阈值下的定量读数。

## 原文证据

Wiley 可检索到的论文全文方法/结果文字描述了 GuUGAT 的供体比较：除 UDP-GlcA 外，UDP-glucose、UDP-galactose 等其他 UDP 糖也被评估，论文据此概括该酶总体上对 UDP-GlcA 具有特异性；正文指向补充图 Fig. S14。受体相关实验包括 glycyrrhetinic acid 和其 3-O-glucuronide。

本次尝试访问 Wiley 的正文 PDF 与 SI 下载端点，均被访问挑战/403 拦截；PMC 记录页面可检索，但当前环境未能取得可读全文文件或 SI。因此未看到 S14 图像，也未核实两种替代供体在两个受体上的逐格色谱、数值、检测限和重复数。

## 判断与边界

这不是“只有汇编标签、原文连测试范围都无法确认”的案例：原文支持替代供体确实进入实验比较，并给出与零标签一致的组级供体特异性结论。证据等级应记为：

> **测试范围和组级阴性/特异性结论有原文支持；逐个供体—受体格子的阴性读数尚未能独立查看。**

因此，四个零标签可作为“来源支持的组级阴性”纳入证据矩阵，但不能说已恢复出四条带有数值、阈值和重复信息的逐格测量。也不能由这一篇文章估计文献阴性的总体可恢复率，或推出加入这些数据会改善机器学习。

与 T105 的 UGT92G1/G2 案例相比，本例证据更强：T105 的可访问原文未能证明 UDP-GlcA 是否进入测试；本例原文明确报告比较了替代 UDP 供体，但逐格读数仍不可见。两者共同说明，二次数据库可以把“有组级特异性结论”压成二元标签，却未必保留了可复核的逐项读数和实验语境。

## 来源

- Xu, G. et al. (2016). *A novel glucuronosyltransferase has an unprecedented ability to catalyse continuous two-step glucuronosylation of glycyrrhetinic acid to yield glycyrrhizin*. New Phytologist 212:123–135. [DOI](https://doi.org/10.1111/nph.14039)；[Wiley全文页](https://nph.onlinelibrary.wiley.com/doi/abs/10.1111/nph.14039)；[PMC记录](https://pmc.ncbi.nlm.nih.gov/articles/PMC7167757/)。
- [Zenodo UGT donor compilation](https://zenodo.org/records/16761161)，按 DOI 精确匹配的6行。
- PubChem CID 94715：[D-glucuronic acid](https://pubchem.ncbi.nlm.nih.gov/compound/94715)。
