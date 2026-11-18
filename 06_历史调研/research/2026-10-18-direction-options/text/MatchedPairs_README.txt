GitHub - Jnelen/ChEMBL_MatchedPairsAnalysis: Code and datasets from the manuscript "Matched Pairs Demonstrate Robustness Against Inter-Assay Variability". · GitHub
Skip to content
Navigation Menu
Sign in
Appearance settings
Search
/
Sign in
Sign up
Appearance settings
You signed in with another tab or window.
Reload
to refresh your session.
You signed out in another tab or window.
Reload
to refresh your session.
You switched accounts on another tab or window.
Reload
to refresh your session.
Dismiss alert
Repository navigation
ChEMBL_MatchedPairsAnalysis
Public
forked from
rinikerlab
/
overlapping_assays
Notifications
You must be signed in to change notification settings
Fork
2
(
2
)
Star
5
(
5
)
You must be signed in to star a repository
About
Code and datasets from the manuscript "Matched Pairs Demonstrate Robustness Against Inter-Assay Variability".
doi.org/10.1186/s13321-025-00956-y
Resources
Readme
MIT license
Activity
Stars
5
stars
Watchers
0
watching
Forks
2
forks
Report repository
main
Branches
Tags
Go to file
Code
Open more actions menu
Latest commit
History
16 Commits
16 Commits
Folders and files
Name
Name
Last commit message
Last commit date
Figures
Figures
IC50_MaximalCuration
IC50_MaximalCuration
IC50_MinimalCuration
IC50_MinimalCuration
Ki_MaximalCuration_Pruned
Ki_MaximalCuration_Pruned
Ki_MaximalCuration_RefPruned
Ki_MaximalCuration_RefPruned
Ki_MaximalCuration_Unpruned
Ki_MaximalCuration_Unpruned
Ki_MinimalCuration_Pruned
Ki_MinimalCuration_Pruned
Ki_MinimalCuration_RefPruned
Ki_MinimalCuration_RefPruned
Ki_MinimalCuration_Unpruned
Ki_MinimalCuration_Unpruned
MediumCuration
MediumCuration
ChEMBL32_MatchedPairsAnalysis.ipynb
ChEMBL32_MatchedPairsAnalysis.ipynb
LICENSE
LICENSE
README.md
README.md
environment.yml
environment.yml
View all files
Repository files navigation
Matched Pairs Prove Robust Against Inter-Assay Noise
Abstract
Machine learning models for chemistry require large datasets, often compiled by combining data from multiple assays. However, combining data without careful curation can introduce significant noise. While absolute values from different assays are rarely comparable, trends or differences between compounds are often assumed to be consistent. This study evaluates that assumption by analyzing potency differences between matched compound pairs across assays and assessing the impact of assay metadata curation on error reduction. We find that potency differences between matched pairs exhibit less variability than individual compound measurements, suggesting systematic assay differences may partially cancel out in paired data. Metadata curation further improves inter-assay agreement, albeit at the cost of dataset size. For minimally curated compound pairs, agreement within 0.3 pChEMBL units was found to be 44-46% for K
i
and IC
50
values respectively, which improved to 66-79% after curation. Similarly, the percentage of pairs with differences exceeding 1 pChEMBL unit dropped from 12-15% to 6-8% with extensive curation. These results establish a benchmark for expected noise in matched molecular pair data from the ChEMBL database, offering practical metrics for data quality assessment.
Code
You can replicate the analysis and generate the figures from the paper using the
ChEMBL32_MatchedPairsAnalysis.ipynb
notebook. For the
gather_data
step, you need access to a copy of the ChEMBL32 database via
PostgreSQL
. You can find the database here:
ChEMBL32 database
. Download the
chembl_32_postgresql.tar.gz
, which includes basic setup instructions. After, you should fill in the connection_string, at the top of the gather_data function. If you have setup the chembl_32 database locally, the connection_string should have the following format:
connection_string
=
f"postgresql://username:password@localhost:5432/chembl_32"
This step is optional because the relevant data is cached and provided with this repository. However, without access to the database, you won't be able to experiment with custom data curation settings.
Installation Instructions
Create the conda environment:
conda env create -f environment.yml
Activate the conda environment:
conda activate chembl_matchedpairs
Launch the Jupyter Notebook:
jupyter-notebook ChEMBL32_MatchedPairsAnalysis.ipynb
If you have a
PostgreSQL
database setup for ChEMBL32, update the
connection_string
on line 8 of Cell 1.1 with your database link.
If you do not have the database setup, skip running Cell 1.1 and any cells using the
gather_data
function. All other cells should work as intended.
Citation
If you use our work, please cite it as follows:
@article
{
nelen_matched_2025
,
author
=
{
Nelen, Jochem and Pérez-Sánchez, Horacio and De Winter, Hans and Van Rompaey, Dries
}
,
title
=
{
Matched pairs demonstrate robustness against inter-assay variability
}
,
journal
=
{
Journal of Cheminformatics
}
,
year
=
{
2025
}
,
volume
=
{
17
}
,
pages
=
{
8
}
,
doi
=
{
10.1186/s13321-025-00956-y
}
}
This work builds upon earlier research by Greg Landrum, which can be cited as:
@article
{
landrum_combining_2024
,
author
=
{
Landrum, Gregory A. and Riniker, Sereina
}
,
title
=
{
Combining IC50 or Ki Values from Different Sources Is a Source of Significant Noise
}
,
journal
=
{
Journal of Chemical Information and Modeling
}
,
year
=
{
2024
}
,
volume
=
{
64
}
,
pages
=
{
1560--1567
}
,
doi
=
{
10.1021/acs.jcim.4c00049
}
}
About
Code and datasets from the manuscript "Matched Pairs Demonstrate Robustness Against Inter-Assay Variability".
doi.org/10.1186/s13321-025-00956-y
Resources
Readme
MIT license
Activity
Stars
5
stars
Watchers
0
watching
Forks
2
forks
Report repository
Releases
Packages
Contributors
Languages
Footer
© 2026 GitHub, Inc.
You can’t perform that action at this time.