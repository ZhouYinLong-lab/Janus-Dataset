"""Retain bounded primary sources; reuse the existing source collector.

Only downloads and text conversion. No inference or training.
"""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
helper = ROOT.parent / '2026-10-18-literature-judgment/bridge/collect_sources.py'
spec = importlib.util.spec_from_file_location('source_collector', helper)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
collector.ROOT = ROOT
collector.SOURCES = ROOT / 'sources'
collector.TEXT = ROOT / 'text'
collector.TARGETS = [
    ('NpaBGS2012.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3403894/fullTextXML'),
    ('HiBgl2016.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4897640/fullTextXML'),
    ('LpBgl52025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11978721/fullTextXML'),
    ('PROTAC_DB3.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11701630/fullTextXML'),
    ('TPDExtraction2026.html', 'https://arxiv.org/html/2605.11221v1'),
    ('BRENDA_fields.html', 'https://www.brenda.dsmz.de/datafields.php'),
    ('AssayCTX2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12264928/fullTextXML'),
    ('Negatome2014.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3965096/fullTextXML'),
    ('TPD_README.md', 'https://raw.githubusercontent.com/yaochenr/LLM-TPD-Extraction/under_review/README.md'),
    ('TPD_LICENSE.txt', 'https://raw.githubusercontent.com/yaochenr/LLM-TPD-Extraction/under_review/LICENSE'),
    ('TPD_GT_Glues.csv', 'https://raw.githubusercontent.com/yaochenr/LLM-TPD-Extraction/under_review/data/molecular_glues/ground_truth/GT_Glues.csv'),
    ('TPD_GT_PROTAC.csv', 'https://raw.githubusercontent.com/yaochenr/LLM-TPD-Extraction/under_review/data/protacs/ground_truth/PROTAC-GT.csv'),
    ('TPD_example2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12046021/fullTextXML'),
    ('DBAASP2021.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7778994/fullTextXML'),
    ('AMP_BP100_2021.html', 'https://www.frontiersin.org/journals/cellular-and-infection-microbiology/articles/10.3389/fcimb.2021.609542/full'),
    ('LNP_Storage2020.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7078456/fullTextXML'),
    ('LNP_Drying2023.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10062427/fullTextXML'),
    ('LNP_Atlas2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12858976/fullTextXML'),
    ('LipoAgent2026.html', 'https://arxiv.org/html/2605.25250v1'),
]

if __name__ == '__main__':
    collector.main()
