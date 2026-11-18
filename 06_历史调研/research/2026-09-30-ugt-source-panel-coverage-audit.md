# UGT donor 面板与汇编缺格审计：RyUGT3A / RyUGT12

**日期：** 2026-09-30  
**主课题关联度：** 3/3（源测量覆盖、阴性来源和缺失标签）；0/3（没有直接测试机器学习效用）  
**对应记录：** T107、E090、J054、Q116

## 汇编记录

从 Zenodo UGT donor compilation 按 DOI `10.1039/D0QO00579G` 精确匹配出7行，均以 6-hydroxyrubiadin 为 acceptor：

| Enzyme | UDP-Glc | UDP-Gal | UDP-GlcA | UDP-GlcNAc |
|---|---:|---:|---:|---:|
| RyUGT3A | 1 | 0 | 1 | 1 |
| RyUGT12 | 1 | 0 | 0 | 未收录 |

## 原文/SI可核范围

RSC 官方SI搜索索引中的 Figure S9 图注明确说，RyUGT3A 和 RyUGT12 都以 6-hydroxyrubiadin 为受体，分别测试 UDP-glucose、UDP-glucuronic acid、UDP-N-acetylglucosamine 和 UDP-galactose，并使用色谱与 LC-MS/MS 分析产物。因此图注描述的是 2×4=8 个酶—供体组合；汇编只收录7格，缺 RyUGT12/UDP-GlcNAc。

直接打开官方SI PDF时，本环境收到404；RSC全文页也被403限制。本次能核验官方SI的图注文本，不能视觉查看 Figure S9 的色谱面板。因此：

- 三条汇编零（RyUGT3A/UDP-Gal、RyUGT12/UDP-Gal、RyUGT12/UDP-GlcA）均能确认在源实验范围内，但不能仅凭图注确认其结果确为 no product。
- 缺失的 RyUGT12/UDP-GlcNAc 组合属于源文图注声称测试过、但二次汇编未收录的配对；其结果目前未知。不得补成0或1。

## 对课题的意义及边界

这是“已测但未收录”和“汇编有0但逐格读数不可见”同时出现的具体例子。它提醒我们至少要把以下状态分开保存：源中是否测试、源中报告何种结果、二次汇编是否收录、数值/阈值/重复是否可见。单个来源只证明这种覆盖落差存在于一个具体表格案例中，不能推出领域普遍程度，也不能说明补回该格会改善模型。

## 来源

- Yi, S. et al. (2020). *Discovery and characterization of four glycosyltransferases involved in anthraquinone glycoside biosynthesis in Rubia yunnanensis*. Organic Chemistry Frontiers 7, 2442–2448. [DOI / RSC article page](https://doi.org/10.1039/D0QO00579G)。
- [RSC official SI PDF (indexed Figure S9 caption)](https://www.rsc.org/suppdata/d0/qo/d0qo00579g/d0qo00579g1.pdf)。
- [Zenodo UGT donor compilation](https://zenodo.org/records/16761161)，7 exact-DOI rows.
