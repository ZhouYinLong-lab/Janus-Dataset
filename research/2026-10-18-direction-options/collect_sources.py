"""Cache bounded primary sources for comparing concrete research directions.

No training, inference, or execution of downloaded project code.
"""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('source_collector', ROOT.parent / '2026-10-18-literature-judgment/bridge/collect_sources.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
collector.ROOT = ROOT
collector.SOURCES = ROOT / 'sources'
collector.TEXT = ROOT / 'text'
collector.TARGETS = [
    ('UQ4DD2025.pdf', 'https://research.chalmers.se/publication/545243/file/545243_Fulltext.pdf'),
    ('UQ4DD_README.html', 'https://github.com/MolecularAI/uq4dd'),
    ('CensorADMET_README.html', 'https://github.com/eva-mitropoulou/censorADMET'),
    ('CensorADMET_tree.json', 'https://api.github.com/repos/eva-mitropoulou/censorADMET/git/trees/main?recursive=1'),
    ('CensorADMET_citation.txt', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/CITATION.cff'),
    ('MoleculeACE2022.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9749029/fullTextXML'),
    ('ChEMBLCuration2015.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4607714/fullTextXML'),
    ('CliffCuration2016.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5657146/fullTextXML'),
    ('CARA2024.html', 'https://www.nature.com/articles/s42004-024-01204-4'),
    ('BindingDBContext2026.html', 'https://arxiv.org/html/2609.34001v1'),
    ('BindingDBContext2026.pdf', 'https://arxiv.org/pdf/2609.34001v1'),
    ('CensorADMET_config.json', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/configs/manuscript-v1.0.0.json'),
    ('CensorADMET_zenodo.json', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/.zenodo.json'),
    ('CensorADMET_LICENSE_DATA.txt', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/LICENSE_DATA'),
    ('CensorADMET_data_readme.txt', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/data/README.md'),
    ('CensorADMET_data.py', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/src/censoradmet/data.py'),
    ('CARA2024.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11150475/fullTextXML'),
    ('CARA_README.html', 'https://github.com/tiantz17/CARA'),
    ('MoleculeACE_README.html', 'https://github.com/molML/MoleculeACE'),
    ('CARA_zenodo_metadata.json', 'https://zenodo.org/api/records/11063965'),
    ('CensorADMET_datacite_metadata.json', 'https://api.datacite.org/dois/10.5281/zenodo.21417709'),
    ('CensorADMET_zenodo_metadata.json', 'https://zenodo.org/api/records/21417709'),
    ('MoleculeACE_CHEMBL2034_Ki.csv', 'https://raw.githubusercontent.com/molML/MoleculeACE/main/MoleculeACE/Data/benchmark_data/CHEMBL2034_Ki.csv'),
    ('OverlappingAssays2024.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10934815/fullTextXML'),
    ('MatchedPairs2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11748845/fullTextXML'),
    ('CurationQuantity2026.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13370779/fullTextXML'),
    ('DeltaClassifier2024.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11253865/fullTextXML'),
    ('DeltaClassifier_README.html', 'https://github.com/RekerLab/DeltaClassifier'),
    ('ChEMBL_MTL_README.html', 'https://github.com/rinikerlab/ChEMBL_MTL'),
    ('MatchedPairs_README.html', 'https://github.com/Jnelen/ChEMBL_MatchedPairsAnalysis'),
]

if __name__ == '__main__':
    collector.main()
