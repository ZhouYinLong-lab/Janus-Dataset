GitHub - RekerLab/DeltaClassifier: DeltaClassifier is a machine learning method to directly train upon and learn molecular changes to classify molecular improvements in potency using inexact regression data. · GitHub
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
DeltaClassifier
Public
Notifications
You must be signed in to change notification settings
Fork
0
(
0
)
Star
5
(
5
)
You must be signed in to star a repository
About
DeltaClassifier is a machine learning method to directly train upon and learn molecular changes to classify molecular improvements in potency using inexact regression data.
Resources
Readme
Activity
Custom properties
Stars
5
stars
Watchers
1
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
47 Commits
47 Commits
Folders and files
Name
Name
Last commit message
Last commit date
Code
Code
Command_Line_Implementation
Command_Line_Implementation
Datasets
Datasets
Results
Results
README.md
README.md
View all files
Repository files navigation
Overview
A substantial amount of inhibition data is bounded and inaccessible to traditional regression algorithms, but pairing regression datapoints and comparing potency values can leverage this bounded data for classification. We present DeltaClassifier, a novel molecular pairing approach to process this data. This creates a new classification task of predicting which one of two paired molecules is more potent. This novel classification task can be accurately solved by various, established molecular machine learning algorithms, including XGBoost and Chemprop. Across 230 ChEMBL IC50 datasets, both tree-based and neural network-based “DeltaClassifiers” show improvements over traditional regression approaches in correctly classifying molecular potency improvements.
For more information, please refer to the
associated publication
If you use this data or code, please kindly cite: Fralish, Z., Skaluba, P., & Reker, D. (2024). Leveraging bounded datapoints to classify molecular potency improvements. RSC Med Chem. 15, 2474-2482.
We would like to thank the Chemprop, XGBoost, and the Scikit-learn developers for making their machine learning algorithms publicly available.
Requirements
RDKit
scikit-learn
numpy
pandas
Machine Learning Models
Random Forest
Chemprop v1.5.2
XGBoost
Given the larger size of delta datasets, we recommend using a GPU for significantly faster training.
To use Chemprop with GPUs, you will need:
cuda >= 8.0
cuDNN
Descriptions of Folders
Code
Python code for evaluating DeltaClassifers and traditional models based on their ability to classify potency differences between two molecules.
Command_Line_Implementation
Provides shell scripts to run directly from the command line.
Datasets
230 curated training sets for potency prediction from
ChEMBL
.
Results
Results from 3x10-fold cross-validation and 80-20 scaffold split.
License
The copyrights of the software are owned by Duke University. As such, two licenses for this software are offered:
An open-source license under the GPLv2 license for non-commercial academic use.
A custom license with Duke University, for commercial use or uses without the GPLv2 license restrictions.
About
DeltaClassifier is a machine learning method to directly train upon and learn molecular changes to classify molecular improvements in potency using inexact regression data.
Resources
Readme
Activity
Custom properties
Stars
5
stars
Watchers
1
watching
Forks
0
forks
Report repository
Releases
Packages
Used by
Contributors
Languages
Footer
© 2026 GitHub, Inc.
You can’t perform that action at this time.