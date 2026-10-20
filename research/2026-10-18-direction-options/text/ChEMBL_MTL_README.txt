GitHub - rinikerlab/ChEMBL_MTL: Evaluation of data curation strategies for bioactivity prediction using ChEMBL data · GitHub
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
ChEMBL_MTL
Public
Notifications
You must be signed in to change notification settings
Fork
0
(
0
)
Star
0
(
0
)
You must be signed in to star a repository
About
Evaluation of data curation strategies for bioactivity prediction using ChEMBL data
Resources
Readme
MIT license
Activity
Custom properties
Stars
0
stars
Watchers
0
watching
Forks
0
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
4 Commits
4 Commits
Folders and files
Name
Name
Last commit message
Last commit date
src
src
.gitignore
.gitignore
001_Grab_Assays_ChEMBL34.ipynb
001_Grab_Assays_ChEMBL34.ipynb
002A_Run_GNNs_script.py
002A_Run_GNNs_script.py
002B_Run_RFs_script.py
002B_Run_RFs_script.py
003_Analysis.ipynb
003_Analysis.ipynb
LICENSE
LICENSE
README.md
README.md
environment.yml
environment.yml
example_command.txt
example_command.txt
View all files
Repository files navigation
ChEMBL MTL
Code
Code to extract data using ACH and Target curation from ChEMBL as described in the manuscript:
001_Grab_Assays_ChEMBL34.ipynb
.
Example code to run GNN regressors on these data splits:
002A_Run_GNNs_script.py
Example code to run RF regressors on these data splits:
002B_Run_RFs_script.py
Script to visualize the results:
003_Analysis.ipynb
. Data required to run this notebook is available on the ETH Research Collection (
https://doi.org/10.3929/ethz-c-000798140
)
Note that the example scripts write out to results to undescriptive filenames (such as 'results.pkl'), to be changed to appropriate names by the user.
The aggregated results CSVs (as used in
003_Analysis.ipynb
) were created by aggregating statistics as written to
stats.pkl
.
To obtain these dataframes, one can run the models over all the provided data sets and aggregate the performance metrics into CSVs.
The datasets used to train and evaluate the models are available on the ETH Research Collection (
https://doi.org/10.3929/ethz-c-000801800
) as CSVs and PyTorch graphs.
Directories
src: scripts to support running of the models and visualization of the performance results
Environment
mamba
env
create
-
f
environment
.
yml
About
Evaluation of data curation strategies for bioactivity prediction using ChEMBL data
Resources
Readme
MIT license
Activity
Custom properties
Stars
0
stars
Watchers
0
watching
Forks
0
forks
Report repository
Releases
Packages
Contributors
Languages
Footer
© 2026 GitHub, Inc.
You can’t perform that action at this time.