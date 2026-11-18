# 本轮留存的原始来源

获取日期：2026-10-18。以下为来源服务返回的XML，不是助手生成的论文内容。全文XML可用浏览器、文本编辑器或XML解析器读取；题录摘要XML不能替代全文。

| 文件 | 内容 | 原始获取URL | SHA-256 |
| --- | --- | --- | --- |
| [EnzEngDB-2026.xml](EnzEngDB-2026.xml) | EnzEngDB正式论文全文；2025在线、2026卷 | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12807667/fullTextXML | `D3E4DFF4CD71AF7E77E12320D121D97EE74C43DF04EE3ECF8C297C711C3C2AE7` |
| [AssayCTX-2025.xml](AssayCTX-2025.xml) | AssayCTX正式论文全文 | https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12264928/fullTextXML | `948B4DB03E93A47823B0C3B3DC7FA4CC18A92BFA6C4A5554E59B58BC2AA4AF1F` |
| [three_papers_pubmed_records.xml](three_papers_pubmed_records.xml) | PMID32207174、33166469、33347927的书目和摘要，非全文 | https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=32207174,33166469,33347927&retmode=xml | `C996D19BEAD4FF9DB06704676195CA675B2A687E244306B63720E7CA6948B487` |

EnzEngDB的OSTI PDF链接本轮请求45秒超时，未留下PDF。三篇待读论文的正文获取失败路径见[逐篇记录](../三篇正文取证试做.md)；没有将403返回的HTML命名成PDF。

GH1试验沿用此前留存的[原始补充表](../../sources/gh1-2014/)；具体输入文件校验值在[运行清单](../run_manifest.json)中，原论文及补充数据的原有许可说明见[先前来源记录](../../2026-09-30-gh1-nims-extraction-pilot.md)。本轮没有重复下载或修改这些输入。
