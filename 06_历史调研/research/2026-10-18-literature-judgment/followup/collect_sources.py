"""Download a bounded second reading set; reuse the existing source collector.

Only retrieves public primary sources and converts text. No model experiments.
"""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('source_collector', ROOT.parent / 'bridge' / 'collect_sources.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
collector.ROOT = ROOT
collector.SOURCES = ROOT / 'sources'
collector.TEXT = ROOT / 'text'
collector.TARGETS = [
    ('NegSize2014.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4061540/fullTextXML'),
    ('NegSource2013.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3626618/fullTextXML'),
    ('Pertusi2017.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7055960/fullTextXML'),
    ('MPro2023.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10323144/fullTextXML'),
    ('PADIF2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12577370/fullTextXML'),
    ('Caceres2020.pdf', 'https://www.biorxiv.org/content/10.1101/2020.05.21.107748v1.full.pdf'),
    ('Caceres_thesis.pdf', 'https://escholarship.org/content/qt8716h0m5/qt8716h0m5.pdf'),
    ('RELATE2025.pdf', 'https://openreview.net/pdf?id=gcG8dmAUNh'),
    ('PreSEPM2026.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13563996/fullTextXML'),
    ('FNU2020.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7362944/fullTextXML'),
    ('BioContext2012.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3413385/fullTextXML'),
    ('DeepEventMine2020.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7750964/fullTextXML'),
    ('INDRA2023.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10167483/fullTextXML'),
    ('AssayFrames2017.pdf', 'https://acl-bg.org/proceedings/2017/RANLP_W4%202017/pdf/BioNLP003.pdf'),
    ('Vapur2020.pdf', 'https://aclanthology.org/2020.nlpcovid19-2.21.pdf'),
    ('Polak2024.pdf', 'https://arxiv.org/pdf/2302.04914'),
    ('NegRatio2017.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5383296/fullTextXML'),
    ('Pertusi2017.pdf', 'https://www.osti.gov/servlets/purl/1427497'),
    ('EPP2021.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8337005/fullTextXML'),
    ('DeepEventMine2020_supp.pdf', 'https://pmc.ncbi.nlm.nih.gov/articles/instance/7750964/bin/btaa540_supplementary_data.pdf'),
    ('DORAXGB2025.html', 'https://pubs.rsc.org/en/content/articlehtml/2025/me/d4me00118d'),
    ('Heikamp2013_metadata.json', 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:23799269%20AND%20SRC:MED&format=json&resultType=core'),
    ('Pertusi2017_metadata.json', 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:29030274%20AND%20SRC:MED&format=json&resultType=core'),
]

if __name__ == '__main__':
    collector.main()
