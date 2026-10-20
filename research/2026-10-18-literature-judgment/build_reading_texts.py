"""Convert locally retained sources to inspectable paragraphs and inventories."""
from pathlib import Path
from hashlib import sha256
import csv
import json
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
rows = []
for source in sorted(ROOT.rglob('sources/*')):
    if not source.is_file():
        continue
    raw = source.read_bytes()
    row = dict(path=source.relative_to(ROOT).as_posix(), bytes=len(raw),
               sha256=sha256(raw).hexdigest(), title='', identifiers='', validation='')
    pieces = []
    if source.suffix == '.xml':
        try:
            xml = ET.fromstring(raw)
            title = xml.find('.//article-title')
            row['title'] = ''.join(title.itertext()) if title is not None else ''
            row['identifiers'] = '; '.join(f"{n.get('pub-id-type')}:{n.text}" for n in xml.findall('.//article-id'))
            row['validation'] = 'parseable_article_xml'
            abstract = xml.find('.//abstract')
            if abstract is not None:
                pieces.append('# Abstract\n' + ' '.join(''.join(abstract.itertext()).split()))
            body = xml.find('body')
            if body is not None:
                for i, n in enumerate(body.iter()):
                    if n.tag == 'title':
                        pieces.append('\n## ' + ''.join(n.itertext()))
                    elif n.tag == 'p':
                        pieces.append(f'P{i:04d}: ' + ' '.join(''.join(n.itertext()).split()))
                    elif n.tag == 'table-wrap':
                        pieces.append('\nTABLE: ' + ' '.join(''.join(n.find('label').itertext()).split()) if n.find('label') is not None else '\nTABLE')
                        cap = n.find('caption')
                        if cap is not None:
                            pieces.append(' '.join(''.join(cap.itertext()).split()))
                        for tr in n.findall('.//tr'):
                            pieces.append(' | '.join(' '.join(''.join(c.itertext()).split()) for c in tr))
                        for foot in n.findall('.//table-wrap-foot'):
                            pieces.append('Footnote: ' + ' '.join(''.join(foot.itertext()).split()))
        except Exception as e:
            row['validation'] = 'xml_error:' + str(e)
    elif source.suffix == '.pdf':
        if raw.startswith(b'%PDF'):
            import fitz
            doc = fitz.open(source)
            row['validation'] = f'pdf_{len(doc)}pages'
            pieces = [f'## PDF page {i+1}\n{p.get_text(sort=True)}' for i,p in enumerate(doc)]
        else:
            row['validation'] = 'not_pdf'
    elif source.suffix == '.json':
        try:
            metadata = json.loads(raw)
            entries = metadata.get('resultList', {}).get('result', [])
            row['title'] = '; '.join(item.get('title', '') for item in entries)
            row['identifiers'] = '; '.join(item.get('doi', '') for item in entries)
            row['validation'] = 'metadata_and_abstract_not_fulltext' if entries else 'json_requires_content_check'
        except Exception as e:
            row['validation'] = 'json_error:' + str(e)
    elif source.suffix == '.html':
        soup = BeautifulSoup(raw, 'html.parser')
        row['title'] = soup.title.get_text() if soup.title else ''
        challenge = any(term in row['title'].lower() for term in ['captcha','browser','challenge','denied'])
        row['validation'] = 'html_access_challenge_not_article' if challenge else 'html_requires_content_check'
        for n in soup(['script','style','nav']):
            n.decompose()
        pieces = [soup.get_text('\n', strip=True)]
    if pieces:
        output_dir = source.parent.parent / 'reading_text'
        output_dir.mkdir(exist_ok=True)
        (output_dir / (source.stem + '.txt')).write_text('\n\n'.join(pieces), encoding='utf-8')
    rows.append(row)
with (ROOT / 'source_inventory.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['path'])
    writer.writeheader()
    writer.writerows(rows)
print('Inventoried',len(rows),'local sources; inventory is not a count of papers read.')
