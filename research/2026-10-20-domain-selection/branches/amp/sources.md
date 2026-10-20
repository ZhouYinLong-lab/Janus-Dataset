# 证据定位记录

核查日期：2026-10-20。最终采用以下 5 个证据源；同一论文的官方 XML 为访问替代，不另计来源。不保存整篇全文，不下载 PDF。

## S1 原始实验全文：BP100 与比较肽

- [出版社全文](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full)，DOI 10.3389/fcimb.2021.609542，2021。
- [Table 1](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full#T1)：TAT = GRKKRRQRRRPPQ；不同末端修饰须保留。
- [Table 2](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full#T2)：TAT 行，新结果列依次是 E. coli DSM 498 >500、E. helveticus 500、K. rhizophila 125；单位 μM。脚注 a 是本研究新结果，b 是既往文献结果。
- [脚注 e](https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full#fnT2_5) 的简短原文：“No effect was found for the highest tested concentration.” 仅支持测试范围内无效。
- 同一表 HC10 列：MAG2 >100，TAT >>100；脚注 c 定义 10% 溶血浓度。保留不等号，不能填成精确值或溶血率零。
- 方法定位：Materials and Methods → Minimum Inhibitory Concentration (MIC) Assay。LB 是前培养；1% TSB 是测定条件；50 μL 菌悬液为 10^6 CFU/mL，总体积 100 μL；37°C 过夜；三次实验，至少两次抑制生长的最低浓度为报告值。最终 5×10^5 CFU/mL 为计算值。
- 方法定位：Hemolysis Assay；结果定位：Results → Hemolysis 与 Figure 2 图注。人红细胞最终 0.25%（v/v），37°C、20 min、540 nm；吸光重复三次，不能当成独立供者三次。没有从曲线读精确百分比。
- 版权位置：文末 Copyright，CC BY。
- 未读补充材料；未核实该实验键是否已被 DBAASP/DRAMP/用户 Excel 收录。表中边界原样保留，未用储备液反算替换。

## S2 DBAASP v3 原始数据库论文

- [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7778994/)，DOI 10.1093/nar/gkaa991；2020 在线发表，2021 卷期。
- PMC HTML 本次遇验证页；实际读取同文 [Europe PMC 官方全文 XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7778994/fullTextXML)。
- 位置：Data collection → 人工阅读原始文章，整理序列、修饰、靶标、活性与细胞毒性。
- 位置：Database structure → Ranking search page → 已包含 assay medium、CFU 等条件；API page → 提供单条及查询集合的 REST 访问。
- 位置：Discussion → Distinction from other databases of the general type → 明确收录实测活跃和不活跃肽。由此可排除“DBAASP 没有实测阴性”的前提。
- 位置：permissions → CC BY-NC 4.0，针对论文；数据库当前数据政策见 S3。
- 限制：这些资源说明没有提供本项目抽样文献的漏收率；不得把作者当年的数据库比较直接用作当前 DRAMP 缺口。

## S3 DBAASP 当前数据政策

- [官方 Terms and Conditions](https://dbaasp.org/terms-and-conditions)。
- 位置：Data Access Policy → 允许访问、下载、复制、使用、改编和再分发，条件是公开材料署名 DBAASP。
- 位置：Attribution Requirement → 修改、合并、再分发后仍要求来源署名。
- 位置：External Links → 外链来源版权/许可需要分别核查。
- 此政策与 S2 论文的 CC BY-NC 不能混为一谈；网页无显式修订日期，记录为核查日观察到的政策。

## S4 DRAMP 官方字段帮助

- [Help](https://dramp.cpu-bioinfor.org/static/help.php)。
- 位置：General Data → Fields → Activity Information → Target Organism：靶标、文献及 MIC。
- 位置：同节 Hemolytic Activity：示例为 Ref.22029824，对人红细胞至 50 μg/mL 无溶血。这是官方字段示例，不是本次独立核验的原始实验。
- 同页还列末端修饰、立体化学、文献；Stable Data 描述血清/蛋白酶、稳定性、方法。
- 帮助页保留 4.0 内容；既不能凭未列某字段推断数据库没有，也不能凭一个示例推断抗菌阴性全部收齐。

## S5 DRAMP 官网当前状态与许可

- [官网](https://dramp.cpu-bioinfor.org/)。
- 位置：Welcome to DRAMP Database → 当前自述 V5.0；序列与结构整合包括 SMILES/FASTS。故本报告不将 4.0 当当前版本。
- 位置：NEWS & EVENTS → 2026-02-28 Target Organism 从文本改为结构化表；2026-04-08 扩展活性相关下载；2026-10-19 更新 general data。
- 位置：Commitment → 最近更新 2026-10-19。
- 位置：Welcome 下方数据许可段与页尾 → CC BY 4.0，可下载/提取，要求引用原作者及 DRAMP；patent AMPs 另提示授权。首轮排除专利数据。
- 限制：当前官网/历史帮助存在版本差异；未建立当前导出字段完整性与逐实验收录完整性，不能当作“缺口已证”。
