# 公开来源与实际访问记录

核查日期：2026-10-20。共5组primary资源；同一论文的官方全文、repo、数据发行件归为同组。读取通过浏览器检索和公开HTTP进行，未调用收费模型API。全文/CSV均只在内存解析，最终仅写本目录三个报告文件。以下“可读”不表示已经逐图复核。

## S1 — Zhao等，2020，原始实验

- 题名：Long-term storage of lipid-like nanoparticles for mRNA delivery。
- [DOI/出版社](https://doi.org/10.1016/j.bioactmat.2020.03.001)；[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7078456/)。
- [实际成功读取的全文XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7078456/fullTextXML)。读到方法§2、结果§3、结论、图注、许可；原实验弱结果不是仅凭摘要推断。
- 主要证据：§2.2–2.3、§3.1/Fig.1B；§2.4/§3.2/Fig.2；§2.6–2.7/§3.4–3.5/Fig.4–5。
- XML标注CC BY-NC-ND 4.0。本文只记录标识，不推断其自动授权训练或衍生数据发布。
- XML列mmc1.docx，675,971 bytes。[附件链接](https://pmc.ncbi.nlm.nih.gov/articles/PMC7078456/bin/mmc1.docx)是由XML路径定位，未成功读取内容；[Europe PMC附件接口](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7078456/supplementaryFiles)本轮35秒超时。
- 本轮无作者原始逐重复数值文件；未人工数字化Fig.1–5。原文百分数按作者结果段转述。

## S2 — Meulewaeter等，2023，原始实验

- 题名：Continuous freeze-drying of messenger RNA lipid nanoparticles enables storage at higher temperatures。
- [DOI](https://doi.org/10.1016/j.jconrel.2023.03.039)；[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10062427/)。
- [实际成功读取的全文XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10062427/fullTextXML)。
- 读到方法中mRNA LNP production、Cell culture and transfection；结果§3.1/Fig.2、§3.3/Fig.4–5、体内结果/Fig.6；讨论与Data availability。
- 原始数据声明为按请求提供；不等于现成公开原始数据下载。
- XML许可是Elsevier COVID-19资源中心研究再用文字，含资源中心存续条件；没有将其误记为CC BY。
- SI为mmc1.docx，377,465 bytes，说明含Fig.S1–S3。[附件定位](https://pmc.ncbi.nlm.nih.gov/articles/PMC10062427/bin/mmc1.docx)；[实际尝试的附件接口](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10062427/supplementaryFiles)35秒超时。不能声称已阅读这些补图。report中涉及补图的内容只来自正文引用，不作为独立补图金标。

## S3 — LipoAgent / TransLipid，2026，已有模型与数据工作

- [固定版本arXiv全文](https://arxiv.org/html/2605.25250v1)，2026-05-24；[摘要及版本入口](https://arxiv.org/abs/2605.25250)。
- [ACL出版PDF](https://aclanthology.org/2026.findings-acl.1992.pdf)超过浏览器工具内容长度限制，本轮没有读到该PDF；本文分析基于已读arXiv v1，不能宣称审过ACL终稿差异。
- [官方repo](https://github.com/SAI-Lab-NYU/LipoAgent)；[README](https://raw.githubusercontent.com/SAI-Lab-NYU/LipoAgent/main/README.md)。
- [实际读取preprocess.py](https://raw.githubusercontent.com/SAI-Lab-NYU/LipoAgent/main/data/preprocess.py)；[实际读取build_dataset.py](https://raw.githubusercontent.com/SAI-Lab-NYU/LipoAgent/main/data/finetune/build_dataset.py)。代码只读，未执行。
- [virtual_library.xlsx](https://raw.githubusercontent.com/SAI-Lab-NYU/LipoAgent/main/data/virtual_library.xlsx)HTTP 200、484,811 bytes；仅核查响应，没有分析工作表内容。它是虚拟库，不能视为实验金标。
- 尝试data/finetune/train.jsonl返回404；这不是穷尽repo所有数据文件的结论。GitHub tree/repo API rate-limit报错，未得到完整树或版本固定SHA。
- 尝试根LICENSE、LICENSE.md均404，未核实到repo数据许可。arXiv v1 HTML显示CC Zero，不能自动转用于repo的上游实验数据。
- 已读范围：§3、§4数据说明与模型评价、Table 2–4、§4.4/Fig.6、§6；未从分子图恢复结构、未复核其全部上游实验论文。
- 判定：宽效率预测/排序路线已有prior；当前公开构建脚本含模型标签，不能直接充当人工实验金标；其性能不是我们的收益。

## S4 — LNP Atlas，2025，LLM全文抽取数据集

- [论文DOI](https://doi.org/10.1038/s41597-025-06456-w)；[实际成功读取全文XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12858976/fullTextXML)。
- [Zenodo概念DOI](https://doi.org/10.5281/zenodo.17243732)；[实际元数据API](https://zenodo.org/api/records/17243732)解析到版本记录17243733。
- [实际读取CSV文件](https://zenodo.org/api/records/17243733/files/LNP_Atlas_DB_202509_v1.csv/content)：LNP_Atlas_DB_202509_v1.csv，1,785,032 bytes；服务器元数据MD5 f77ec01fe88e16f558c09c41bcc10610（本轮没有另算校验和）。
- API标注发行日期2025-10-01、数据许可CC BY 4.0；论文XML为CC BY-NC-ND 4.0，二者分列。
- CSV实际解析1,092行、28字段。包含lnp_id、lipid_molar_ratio、synthesis_info、bioactivity_profile、paper_doi和4个SMILES列等。
- 按两个DOI片段2020.03.001/2023.03.039和原实验标题关键词匹配，0行命中。这是单版文件的有限检索，不是完整缺口审计。
- 抽查lnp_id=1的bioactivity_profile，含HeLa/C2C12、动物、route、dose与相对MC3表达；其“lower liver accumulation”不能当转染无效。未追读该行上游实验，故不将其作为新增实验阴性。
- Table 1、Methods/Data curation与Technical Validation说明Claude全文抽取、人工处理部分图以及子集专家复核。未发现该论文展示专门稳定性阴性金标的证据；不声称已穷尽其他发行件。

## S5 — LNPDB，2026，大规模已有数据资源

- [论文DOI](https://doi.org/10.1038/s41467-026-68818-1)；[全文XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12992592/fullTextXML)。
- [官方repo](https://github.com/evancollins1/LNPDB)；[实际读取CSV](https://raw.githubusercontent.com/evancollins1/LNPDB/main/data/LNPDB_for_LiON/LNPDB.csv)；[实际读取MIT LICENSE](https://raw.githubusercontent.com/evancollins1/LNPDB/main/LICENSE)。
- 论文CC BY 4.0；代码repo MIT；不能推定上游全部论文图也具有同样许可。
- 本轮实读CSV共19,797行；论文说明19,528配方与269商业脂质，合计与之相符，未把全部CSV行都当独立实验阴性。
- 已读取Data collection中图形数字化、上下文标准化、必要时对数变换的方法；已读取Data/Code availability。
- 10,754行Experiment_value以负号开头；只是当前CSV的符号计数，非阴性计数。实查LNP_0000081：AA_2008、HeLa、siRNA/FLuc、0.9 μg、luminescence_discretized_normalized、-0.366886147。没有追读该行上游实验，所以不作其绝对无效判定。
- 检查Publication_link中上述两篇实验DOI片段，0行命中；不能排除别名链接、其他版本或其他文件收录。
- XML可见41467_2026_68818_MOESM1_ESM.pdf（SI）、MOESM2（Reporting Summary）、MOESM3（同行评审），本轮只读附件元数据，未读PDF；另有source-data提供声明，未检验其每个附件内容。
- 论文中的MD bilayer stability与储存稳定性不同；本轮未运行任何分子模拟或模型。

## 限度

PMC网页多次出现验证码，Nature页面也有重定向/失败；最终成功的XML/CSV读取与网页失败分开记录。没有把搜索片段冒充全文，也没有因某路径404推断全repo不存在数据。没有使用额外综述作为本轮primary证据。主agent提供的TPD比较信息仅作为项目决策背景，未在本分支另行核查。
