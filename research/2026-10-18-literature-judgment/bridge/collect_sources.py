"""Cache primary research sources; convert their text for read-only inspection.

No model/API inference, no scientific labeling, no experimental work.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import requests
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / 'sources'
TEXT = ROOT / 'text'
TARGETS = [
    ('Toniato2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12164950/fullTextXML'),
    ('Lee2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12717135/fullTextXML'),
    ('Lee2025.pdf', 'https://escholarship.org/content/qt7b20j2q5/qt7b20j2q5_noSplash_2e721e9639669307da60c086970fc895.pdf'),
    ('Gao2026.html', 'https://www.maxapress.com/article/doi/10.48130/gcomm-0026-0010'),
    ('Gao2026.pdf', 'https://maxapress.com/data/article/gcomm/preview/pdf/gcomm-0026-0010.pdf'),
    ('OpenChemIE2024.pdf', 'https://arxiv.org/pdf/2404.01462'),
    ('Oxidation2023.pdf', 'https://arxiv.org/pdf/2308.00389'),
    ('BioMiner2026.html', 'https://arxiv.org/html/2604.21508v1'),
    ('BioMiner2026.pdf', 'https://arxiv.org/pdf/2604.21508v1'),
    ('ESP2023.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10185530/fullTextXML'),
    ('InertDB2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11983867/fullTextXML'),
    ('Robots2026.html', 'https://advanced.onlinelibrary.wiley.com/doi/10.1002/advs.77474'),
    ('Leakage2026.html', 'https://www.biorxiv.org/content/10.64898/2026.02.26.708291v1.full'),
    ('Leakage2026.pdf', 'https://www.biorxiv.org/content/10.64898/2026.02.26.708291v1.full.pdf'),
    ('Cruse2024.pdf', 'https://ceder.berkeley.edu/publications/2023_Kevin_BiFeO3.pdf'),
    ('Nullary_research.html', 'https://nullary.ai/research'),
    ('Okuno2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12712682/fullTextXML'),
    ('BioNOT2011.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3225379/fullTextXML'),
    ('NegBERT2020.pdf', 'https://aclanthology.org/2020.lrec-1.704.pdf'),
    ('NADE2021.pdf', 'https://aclanthology.org/2021.wnut-1.26.pdf'),
    ('Scaboro2022.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9791307/fullTextXML'),
    ('Thway2024.html', 'https://pubs.rsc.org/en/content/articlehtml/2024/dd/d3dd00202k'),
    ('Thway2024.pdf', 'https://pubs.rsc.org/en/content/articlepdf/2024/dd/d3dd00202k'),
    ('EnzyExtract2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12355964/fullTextXML'),
    ('EnzymeCoScientist2025.pdf', 'https://www.biorxiv.org/content/10.1101/2025.03.03.641178v1.full.pdf'),
    ('zERExtractor2025.pdf', 'https://arxiv.org/pdf/2508.09995'),
    ('EnzChemRED2024.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11384730/fullTextXML'),
    ('FuncFetch2025.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11734755/fullTextXML'),
    ('Robots2026.xml', 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13564181/fullTextXML'),
    ('EZSpecificity2025.pdf', 'https://zhaogroup.chbe.illinois.edu/publications/HZ472.pdf'),
    ('VIPER2024.pdf', 'https://www.biorxiv.org/content/10.1101/2024.06.21.599972v1.full.pdf'),
    ('Goldman2022.html', 'https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1009853'),
]

def collect(target):
    name, url = target
    path = SOURCES / name
    record = {'name': name, 'url': url}
    try:
        if path.exists():
            data = path.read_bytes()
            record['download_state'] = 'cached'
        else:
            r = requests.get(url, timeout=45, headers={'User-Agent': 'Janus-literature-review/1.0'})
            r.raise_for_status()
            data = r.content
            if name.endswith('.pdf') and not data.startswith(b'%PDF'):
                raise ValueError('Response is not a PDF')
            if name.endswith('.xml'):
                ET.fromstring(data)
            path.write_bytes(data)
            record['download_state'] = 'downloaded'
            record['resolved_url'] = r.url
        record.update(bytes=len(data), sha256=sha256(data).hexdigest())
        if name.endswith('.xml'):
            root = ET.fromstring(data)
            pieces = []
            for n in root.iter():
                if n.tag in ('article-title', 'abstract', 'sec', 'table-wrap'):
                    if n.tag == 'sec':
                        title = n.find('title')
                        pieces.append('\n## ' + (''.join(title.itertext()) if title is not None else 'section'))
                        for child in n:
                            if child.tag not in ('sec', 'title'):
                                pieces.append(' '.join(''.join(child.itertext()).split()))
                    elif n.tag != 'table-wrap':
                        pieces.append(' '.join(''.join(n.itertext()).split()))
            (TEXT / (Path(name).stem + '.txt')).write_text('\n\n'.join(pieces), encoding='utf-8')
        elif name.endswith('.pdf'):
            import fitz
            doc = fitz.open(stream=data, filetype='pdf')
            record['pages'] = len(doc)
            (TEXT / (Path(name).stem + '_pdf.txt')).write_text(
                '\n\n'.join(f'## PDF page {i+1}\n{p.get_text(sort=True)}' for i, p in enumerate(doc)), encoding='utf-8')
        elif name.endswith('.html'):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(data, 'html.parser')
            for n in soup(['script', 'style', 'nav']):
                n.decompose()
            (TEXT / (Path(name).stem + '.txt')).write_text(soup.get_text('\n', strip=True), encoding='utf-8')
        record['status'] = 'ok'
    except Exception as e:
        record.update(status='error', error=str(e))
    return record

def main():
    SOURCES.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    chosen = [t for t in TARGETS if not sys.argv[1:] or t[0] in sys.argv[1:]]
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(collect, chosen))
    manifest = {'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'sources': records}
    old_manifest = ROOT / 'source_manifest.json'
    if old_manifest.exists():
        previous = json.loads(old_manifest.read_text(encoding='utf-8'))
        by_name = {r['name']:r for r in previous['sources']}
        by_name.update({r['name']:r for r in records})
        manifest['sources'] = list(by_name.values())
    (ROOT / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    for r in records:
        print(r['name'], r['status'], r.get('bytes', ''), r.get('error', ''))

if __name__ == '__main__':
    main()
