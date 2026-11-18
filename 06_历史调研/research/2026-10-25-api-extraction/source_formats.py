"""Conservative source adapters; no inference, OCR, network or credentials.

JSON inputs are corpus-shaped document snapshots. Their original source must
still exist and match source_sha256; loading preserves unit identities.
"""
import copy
import hashlib
import re
from pathlib import Path

from corpus import parse_source, read, sha

FORMAT_PARSER_VERSION = 1
MAX_BYTES = 20_000_000
HEADINGS = re.compile(
    r'^(?:\d+(?:\.\d+)*[.\s]+)?(introduction|background|results(?: and discussion)?|'
    r'discussion|conclusions?|materials and methods|methods|experimental(?: procedures| section)?|'
    r'references|bibliography|acknowledg(?:e)?ments?|abstract)\s*$', re.I)
EXCLUDED = re.compile(r'abstract|references|bibliography|acknowledg|supplementary', re.I)


def _document(path, paper_id, kind):
    return {'paper_id': paper_id, 'source_path': str(path.resolve()),
            'source_sha256': sha(path), 'source_bytes': path.stat().st_size,
            'parser_version': 2, 'format_parser_version': FORMAT_PARSER_VERSION,
            'source_format': kind, 'units': [], 'status': 'input_gap',
            'coverage': '', 'input_gaps': []}


def _add(doc, kind, locator, content, section='', **extra):
    content = ' '.join(content.split())
    if not content:
        return
    digest = hashlib.sha256(
        f'{doc["paper_id"]}:{kind}:{locator}:{content}'.encode()).hexdigest()[:16]
    doc['units'].append({'unit_id': doc['paper_id'] + ':' + digest,
                         'kind': kind, 'locator': locator, 'section': section,
                         'text': content, **extra})


def _snapshot(path, paper_id):
    doc = read(path)
    required = {'paper_id', 'source_sha256', 'source_path', 'units', 'status',
                'coverage', 'parser_version'}
    if not isinstance(doc, dict) or not required <= doc.keys():
        raise ValueError('Invalid document snapshot schema')
    if doc['paper_id'] != paper_id or not isinstance(doc['parser_version'], int):
        raise ValueError('Snapshot identity/parser_version mismatch')
    if not isinstance(doc['source_path'], str) or not re.fullmatch(
            r'[0-9a-f]{64}', str(doc['source_sha256'])):
        raise ValueError('Invalid snapshot source identity')
    source = Path(doc['source_path'])
    if not source.is_absolute():
        source = path.parent / source
    if source.resolve() == path.resolve() or not source.is_file():
        raise ValueError('Snapshot original source missing or self-referential')
    if sha(source) != doc['source_sha256']:
        raise ValueError('Snapshot source hash mismatch')
    if not isinstance(doc['units'], list):
        raise ValueError('Snapshot units must be a list')
    ids = set()
    for unit in doc['units']:
        if not isinstance(unit, dict) or any(
                not isinstance(unit.get(key), str)
                for key in ('unit_id', 'kind', 'locator', 'section', 'text')):
            raise ValueError('Invalid snapshot unit')
        if unit['unit_id'] in ids or not unit['unit_id'].startswith(paper_id + ':'):
            raise ValueError('Snapshot unit identity mismatch')
        ids.add(unit['unit_id'])
    result = copy.deepcopy(doc)
    result['source_path'] = str(source.resolve())
    result['snapshot_path'] = str(path.resolve())
    result['snapshot_sha256'] = sha(path)
    return result


def _html(path, paper_id):
    from bs4 import BeautifulSoup
    doc = _document(path, paper_id, 'html')
    soup = BeautifulSoup(path.read_bytes(), 'html.parser')
    root = soup.find('article') or soup.find('main')
    if root is None:
        doc['input_gaps'] = ['no_confirmed_article_or_main_container']
        doc['coverage'] = 'No confirmed HTML article body; no units emitted.'
        return doc
    # Keep DOM order, remove whole excluded sections (including their p tags).
    for node in list(root.find_all(True)):
        if node.parent is None:
            continue
        label = ' '.join([node.get('id', ''), *node.get('class', []),
                          node.get('role', ''), node.get('aria-label', '')])
        if node.name in {'nav', 'header', 'footer', 'aside', 'script', 'style', 'form'} or re.search(
                r'\b(abstract|references|ref-list|bibliography|navigation|supplementary)\b', label, re.I):
            node.decompose()
    section = ''
    caption_selector = '.figure-caption, .figcaption, .fig-caption, .caption'
    captions = {id(node) for node in root.select(caption_selector)}
    for index, node in enumerate(root.find_all(
            lambda node: node.name in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                      'p', 'table', 'figcaption', 'caption'} or id(node) in captions)):
        if node.name.startswith('h'):
            section = node.get_text(' ', strip=True)
            continue
        if EXCLUDED.search(section):
            continue
        if any(parent.name in {'table', 'figcaption', 'caption'} or id(parent) in captions
               for parent in node.parents):
            continue
        kind = ('table' if node.name == 'table' else
                'figure_caption' if node.name in {'figcaption', 'caption'} or id(node) in captions
                else 'body_paragraph')
        # Nested figure/table paragraphs belong exclusively to their own unit.
        content = copy.copy(node)
        if node.name == 'p':
            for nested in content.find_all(['table', 'figure', 'figcaption']):
                nested.decompose()
        locator = f'html:{index + 1}' + (f'#{node["id"]}' if node.get('id') else '')
        _add(doc, kind, locator, content.get_text(' ', strip=True), section)
    body = any(u['kind'] == 'body_paragraph' for u in doc['units'])
    doc['status'] = 'readable' if body else 'input_gap'
    doc['input_gaps'] = ['figure_pixels_and_independent_supplements_not_parsed']
    if not any(u['section'] for u in doc['units']):
        doc['input_gaps'].append('section_headings_missing')
    doc['coverage'] = ('HTML article/main paragraphs, tables and captions in DOM order; '
                       'excluded abstract, navigation and references; completeness unverified; '
                       'no figure pixels or independent supplementary files.')
    return doc


def _pdf(path, paper_id):
    import fitz
    doc = _document(path, paper_id, 'pdf')
    section = ''
    stopped = False
    gaps = []
    with fitz.open(path) as pdf:
        if pdf.needs_pass:
            doc['coverage'] = 'Encrypted PDF; no text parsed.'
            doc['input_gaps'] = ['encrypted_pdf']
            return doc
        for page_index, page in enumerate(pdf):
            blocks = [b for b in page.get_text('blocks', sort=True) if b[6] == 0 and b[4].strip()]
            page_number = page_index + 1
            if sum(len(b[4].strip()) for b in blocks) < 40:
                gaps.append(f'page:{page_number}:scanned_or_insufficient_text')
                section = ''
                continue
            # Side-by-side text blocks, or two persistent line columns, have
            # ambiguous reading order. Skip the page rather than interleave it.
            lines = [line for block in page.get_text('dict')['blocks'] if block['type'] == 0
                     for line in block.get('lines', []) if line.get('spans')]
            mid = page.rect.width / 2
            left = [line for line in lines if line['bbox'][0] < mid * .8
                    and line['bbox'][2] < mid * 1.12]
            right = [line for line in lines if line['bbox'][0] > mid * .88]
            paired = sum(any(abs(l['bbox'][1] - r['bbox'][1]) < 15 for r in right) for l in left)
            overlap = any(a[0] < b[0] and a[2] <= b[0] + 5 and
                          min(a[3], b[3]) - max(a[1], b[1]) > 15
                          for a in blocks for b in blocks if a is not b)
            if overlap or paired >= 3:
                gaps.append(f'page:{page_number}:ambiguous_columns_or_order')
                section = ''
                continue
            for block_index, block in enumerate(blocks):
                if stopped:
                    break
                # Blocks may contain a heading and following text on new lines.
                paragraph = []

                def flush():
                    if paragraph and section and not EXCLUDED.search(section):
                        content = ' '.join(paragraph)
                        if re.match(r'^(?:fig(?:ure)?|table)\s*[\dS]', content, re.I):
                            gaps.append(f'page:{page_number}:caption_or_table_omitted')
                        else:
                            _add(doc, 'body_paragraph',
                                 f'pdf:page:{page_number}:block:{block_index + 1}:part:{len(doc["units"]) + 1}',
                                 content, section, page=page_number,
                                 bbox=[round(float(v), 3) for v in block[:4]])
                    paragraph.clear()

                for line in block[4].splitlines():
                    line = line.strip()
                    heading = HEADINGS.fullmatch(line)
                    if heading:
                        flush()
                        section = heading.group(1)
                        if re.match(r'references|bibliography', section, re.I):
                            stopped = True
                            break
                    elif line and not re.fullmatch(r'\d+', line):
                        paragraph.append(line)
                flush()
    doc['input_gaps'] = sorted(set(gaps)) + ['pdf_tables_figures_supplements_not_reconstructed']
    doc['status'] = 'readable_partial' if doc['units'] else 'input_gap'
    doc['coverage'] = ('Partial PDF text: confirmed named sections on pages with unambiguous single-column '
                       'order only; page and block coordinates retained. Scans/ambiguous pages skipped; '
                       'tables, figure pixels, supplements and full-body completeness unverified.')
    return doc


def parse_document(path, paper_id):
    """Return corpus-compatible units; gap statuses never imply full coverage."""
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Source exceeds 20 MB')
    suffix = path.suffix.lower()
    if suffix == '.json':
        return _snapshot(path, paper_id)
    if suffix in {'.xml', '.nxml'}:
        return parse_source(path, paper_id)
    if suffix in {'.html', '.htm'}:
        return _html(path, paper_id)
    if suffix == '.pdf':
        return _pdf(path, paper_id)
    raise ValueError(f'Unsupported document format: {suffix}')
