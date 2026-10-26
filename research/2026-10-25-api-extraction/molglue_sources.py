"""MolGlueDB source inventory and bounded public full-text retrieval.

Public interfaces: inventory(export_path, out_dir, legacy_manifest=None) and
fetch_sources(inventory_dir, limit=None). All full text is saved beneath local/.
inventory is offline. fetch uses public EuropePMC endpoints and links explicitly
marked open access by EuropePMC or by the publisher's license/metadata. No keys,
generation endpoints, cookies, retries or paywall workarounds are used.
"""
import csv
import hashlib
import io
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from corpus import LEGACY, ROOT, read, save, sha
from source_formats import parse_document

VERSION = 1
TIMEOUT = 20
MIN_INTERVAL = 1.0
MAX_BYTES = 20_000_000
EUROPEPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
PREFERENCE = {'xml': 0, 'html': 1, 'pdf': 2, 'json': 3}
DOI = re.compile(r'10\.\d{4,9}/[^\s<>"\[\]]+', re.I)
PAPER_SCOPE = {'publication_doi': '10.1093/nar/gkaf811',
               'reported_publications': 241, 'reported_window': 'January 2001–May 2025',
               'basis': 'MolGlueDB paper abstract and data-collection methods',
               'comparison': 'Export-linked distinct DOI sources versus paper collection scope; '
                             'the export is not the complete 241-item bibliography.'}


def _now():
    return datetime.now(timezone.utc).isoformat()


def normalize_doi(value):
    value = str(value or '').strip()
    parts = urlsplit(value)
    if parts.scheme.lower() in {'http', 'https'}:
        value = parts.path
    match = DOI.search(unquote(value))
    return match.group(0).rstrip('.,;').lower() if match else None


def normalize_url(value):
    value = str(value or '').strip()
    doi = normalize_doi(value)
    if doi and (re.match(r'^(doi:|10\.)', value, re.I) or
                (urlsplit(value).hostname or '').lower() in {'doi.org', 'dx.doi.org'}):
        return 'https://doi.org/' + doi
    parts = urlsplit(value)
    if parts.scheme.lower() not in {'http', 'https'} or not parts.hostname:
        return None
    if parts.username or parts.password:
        return None
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/') or '/', query, ''))


def _kind(path):
    suffix = Path(path).suffix.lower()
    return {'.nxml': 'xml', '.htm': 'html'}.get(suffix, suffix.lstrip('.'))


def _legacy_sources(manifest):
    result = []
    if not manifest.is_file():
        return result
    for row in read(manifest):
        paths = []
        if row.get('path'):
            given = Path(row['path'])
            if given.is_absolute():
                paths.append(given)
            else:
                paths.extend([manifest.parent / given, ROOT / given])
        pid = row['paper_id']
        paths.extend(sorted((manifest.parent / 'sources').glob(pid + '_*')))
        paths = sorted({p.resolve() for p in paths if p.is_file() and _kind(p) in PREFERENCE},
                       key=lambda p: (PREFERENCE[_kind(p)], str(p)))
        result.append((row, paths))
    return result


def _write_csv(path, rows):
    fields = ['paper_id', 'source_id', 'doi', 'title', 'url', 'path', 'source_kind',
              'publication_kind', 'source_format', 'availability', 'legacy_paper_id',
              'entry_count', 'export_sha256']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    temporary = path.with_suffix('.csv.tmp')
    temporary.write_text(stream.getvalue(), encoding='utf-8-sig')
    temporary.replace(path)


def _persist(folder, papers, summary):
    summary['availability_counts'] = dict(sorted(Counter(p['availability'] for p in papers).items()))
    summary['with_local_source'] = sum(p.get('path') is not None for p in papers)
    save(folder / 'papers.json', papers)
    _write_csv(folder / 'source_inventory.csv', papers)
    save(folder / 'source_inventory.json', summary)
    return summary


def inventory(export_path, out_dir, legacy_manifest=None):
    """Create a fresh inventory; refuse overwriting an existing/fetched list.

    Source IDs hash the canonical DOI (or normalized URL). Row positions plus
    row hashes preserve associations even when DATAID repeats. Missing sources
    stay in papers.json with path=None. current193 counts DOI and URL sources.
    """
    export_path, folder = Path(export_path).resolve(), Path(out_dir).resolve()
    if (folder / 'papers.json').exists() or (folder / 'source_inventory.json').exists():
        raise FileExistsError('Inventory exists; use fetch_sources to resume')
    export_sha = sha(export_path)
    with export_path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if 'SourceAddress_Website' not in (reader.fieldnames or []):
            raise ValueError('Expected raw MolGlueDB CSV with SourceAddress_Website')
        rows = list(reader)
    manifest = Path(legacy_manifest) if legacy_manifest is not None else LEGACY / 'source_manifest.json'
    legacy = _legacy_sources(manifest)
    groups, unmatched = {}, []
    for index, row in enumerate(rows, 1):
        raw = row.get('SourceAddress_Website', '')
        doi = normalize_doi(raw)
        url = normalize_url(raw)
        entry = {'row_number': index, 'data_id': row.get('DATAID'),
                 'row_sha256': hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                                       separators=(',', ':')).encode()).hexdigest(),
                 'raw_source': raw}
        if not url:
            unmatched.append(entry)
            continue
        key = 'doi:' + doi if doi else 'url:' + url
        group = groups.setdefault(key, {'doi': doi, 'url': 'https://doi.org/' + doi if doi else url,
                                        'entries': [], 'urls': set()})
        group['entries'].append(entry)
        group['urls'].add(url)
    papers = []
    used_ids = set()
    for key, group in sorted(groups.items()):
        sid = 'src_' + hashlib.sha256(key.encode()).hexdigest()[:24]
        matches = [(m, files) for m, files in legacy if
                   (group['doi'] and normalize_doi(m.get('doi')) == group['doi']) or
                   (normalize_url(m.get('url')) in group['urls'])]
        matches.sort(key=lambda pair: (not bool(pair[1]), pair[0]['paper_id']))
        with_files = [(m, files) for m, files in matches if files]
        selected = with_files[0][0] if with_files else (matches[0][0] if matches else {})
        pid = selected.get('paper_id') if with_files else 'MG_' + sid[4:]
        if pid in used_ids:
            raise ValueError(f'Conflicting legacy paper identity: {pid}')
        used_ids.add(pid)
        sources = []
        for m, files in matches:
            for path in files:
                digest = sha(path)
                sources.append({'path': str(path), 'source_sha256': digest,
                                'source_kind': _kind(path), 'origin': 'legacy',
                                'legacy_paper_id': m['paper_id'], 'url': m.get('url'),
                                'availability': 'local', 'source_license': m.get('source_license'),
                                'legacy_hash_matches': digest == m['sha256'] if m.get('sha256') else None})
        sources.sort(key=lambda s: (PREFERENCE[s['source_kind']], s['path']))
        chosen = sources[0] if sources else {}
        papers.append({'paper_id': pid, 'source_id': sid, 'canonical_identity': key,
                       'doi': group['doi'], 'title': selected.get('title') or None,
                       'url': group['url'], 'urls': sorted(group['urls']),
                       'path': chosen.get('path'), 'source_sha256': chosen.get('source_sha256'),
                       'source_kind': chosen.get('source_kind'),
                       'source_format': chosen.get('source_kind'),
                       'publication_kind': 'paper' if group['doi'] else 'corporate_material',
                       'availability': 'local' if sources else 'not_fetched',
                       'legacy_paper_id': selected.get('paper_id'),
                       'legacy_paper_ids': sorted({m['paper_id'] for m, _ in matches}),
                       'sources': sources, 'fetch_attempts': [], 'entries': group['entries'],
                       'entry_count': len(group['entries']),
                       'data_ids': sorted({e['data_id'] for e in group['entries'] if e['data_id']}),
                       'export_sha256': export_sha,
                       'scope_basis': 'Current MolGlueDB export source association; domain membership unreviewed'})
    doi_count = sum(p['doi'] is not None for p in papers)
    summary = {'schema_version': VERSION, 'created_utc': _now(), 'export_path': str(export_path),
               'export_sha256': export_sha, 'export_rows': len(rows),
               'distinct_data_ids': len({r.get('DATAID') for r in rows}),
               'source_count': len(papers), 'doi_sources': doi_count,
               'url_only_sources': len(papers) - doi_count,
               'unresolved_source_rows': unmatched,
               'associated_rows': sum(p['entry_count'] for p in papers),
               'legacy_manifest': str(manifest.resolve()),
               'legacy_manifest_sha256': sha(manifest) if manifest.is_file() else None,
               'legacy_reused_papers': sum(any(s['origin'] == 'legacy' for s in p['sources']) for p in papers),
               'raw_distinct_source_strings': len({r.get('SourceAddress_Website') for r in rows}),
               'current193': {'definition': 'Distinct DOI/URL sources after normalization, including URL-only sources',
                              'observed': len(papers), 'reference_count': 193,
                              'doi_sources': doi_count, 'url_only_sources': len(papers) - doi_count,
                              'matches_reference': len(papers) == 193},
               'reported241': {**PAPER_SCOPE, 'reported_minus_export_doi_count': 241 - doi_count,
                               'reported_minus_export_source_count': 241 - len(papers),
                               'missing_publication_identities': 'unresolved; full 241-item list not supplied',
                               'set_difference_verified': False},
               'fetch_policy': {'timeout_seconds': TIMEOUT, 'min_interval_seconds': MIN_INTERVAL,
                                'preference': ['xml', 'html', 'pdf'], 'automatic_retries': 0}}
    folder.mkdir(parents=True, exist_ok=True)
    return _persist(folder, papers, summary)


class PublicClient:
    """One serial client, global request spacing, bounded reads and redirects."""
    def __init__(self):
        self.last_request = None

    def get(self, url):
        if normalize_url(url) is None:
            raise ValueError('Only public HTTP(S) URLs accepted')
        if self.last_request is not None:
            time.sleep(max(0, MIN_INTERVAL - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = Request(url, headers={'User-Agent': 'Janus-SourceInventory/1.0 (public literature metadata)',
                                       'Accept': 'application/xml,text/html,application/pdf,application/json'})
        with urlopen(request, timeout=TIMEOUT) as response:
            if normalize_url(response.geturl()) is None:
                raise ValueError('Unsupported redirect')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('Public response exceeds 20 MB')
            return data, response.geturl(), response.headers.get('Content-Type', '')


def _request(client, paper, url, purpose):
    attempt = {'url': url, 'purpose': purpose, 'started_utc': _now(), 'status': 'in_flight'}
    paper['fetch_attempts'].append(attempt)
    checkpoint = getattr(client, 'checkpoint', None)
    if checkpoint:
        checkpoint()
    try:
        data, final, content_type = client.get(url)
        attempt.update(status='received', final_url=final, content_type=content_type,
                       bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        return data, final, content_type, attempt
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        code = getattr(exc, 'code', None)
        attempt.update(status='access_denied' if code in {401, 402, 403} else
                       'rate_limited' if code == 429 else
                       'not_found' if code == 404 else 'request_failed',
                       http_status=code, error=f'{type(exc).__name__}: {exc}')
        return None


def _search(client, paper):
    if not paper.get('doi'):
        return []
    url = EUROPEPMC + '/search?' + urlencode({'query': f'DOI:"{paper["doi"]}"',
                                             'format': 'json', 'resultType': 'core', 'pageSize': 10})
    response = _request(client, paper, url, 'europepmc_search')
    if response is None:
        return []
    try:
        records = json.loads(response[0])['resultList']['result']
        if not isinstance(records, list):
            raise ValueError('Unexpected EuropePMC result list')
    except (ValueError, KeyError, TypeError):
        response[3]['status'] = 'invalid_metadata'
        return []
    candidates = []
    for record in records:
        if normalize_doi(record.get('doi')) != paper['doi']:
            continue
        if not paper.get('title'):
            paper['title'] = record.get('title')
        pmcid = record.get('pmcid', '')
        if record.get('isOpenAccess') == 'Y' and re.fullmatch(r'PMC\d+', pmcid):
            candidates.append({'url': EUROPEPMC + '/' + pmcid + '/fullTextXML',
                               'kind': 'xml', 'basis': 'EuropePMC isOpenAccess=Y', 'origin': 'europepmc'})
        for item in record.get('fullTextUrlList', {}).get('fullTextUrl', []):
            kind = str(item.get('documentStyle', '')).lower()
            if kind in PREFERENCE and item.get('availabilityCode') == 'OA' and normalize_url(item.get('url')):
                candidates.append({'url': item['url'], 'kind': kind,
                                   'basis': 'EuropePMC availabilityCode=OA', 'origin': 'europepmc_open_link'})
    return candidates


def _publisher_candidates(data, final_url, paper):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, 'html.parser')
    article_doi = next((normalize_doi(m.get('content')) for m in soup.find_all('meta')
                        if m.get('name', '').lower() in {'citation_doi', 'dc.identifier'}
                        and normalize_doi(m.get('content'))), None)
    if paper.get('doi') and article_doi != paper['doi']:
        return [], 'publisher_identity_unconfirmed'
    license_link = soup.find('a', href=re.compile(r'^https?://(?:www\.)?creativecommons.org/(?:licenses|publicdomain)/', re.I))
    open_meta = any(m.get('name', '').lower() in {'citation_open_access', 'dc.rights', 'dc.rights.accessrights'}
                    and re.search(r'^(true|1|open access)$|creativecommons.org|info:eu-repo/semantics/openAccess',
                                  m.get('content', ''), re.I) for m in soup.find_all('meta'))
    if not license_link and not open_meta:
        return [], 'open_access_unconfirmed'
    basis = license_link['href'] if license_link else 'publisher open-access metadata'
    candidates = [{'url': final_url, 'kind': 'html', 'basis': basis, 'origin': 'publisher', 'data': data}]
    for meta in soup.find_all('meta'):
        kind = {'citation_pdf_url': 'pdf', 'citation_xml_url': 'xml', 'citation_fulltext_html_url': 'html'}.get(meta.get('name', '').lower())
        if kind and meta.get('content'):
            target = urljoin(final_url, meta['content'])
            if urlsplit(target).hostname == urlsplit(final_url).hostname:
                candidates.append({'url': target, 'kind': kind, 'basis': basis, 'origin': 'publisher'})
    return candidates, None


def _store(folder, paper, candidate, data, final_url, content_type):
    kind = candidate['kind']
    if kind == 'pdf' and not data.startswith(b'%PDF-'):
        raise ValueError('Expected PDF bytes; possible access/interstitial page')
    if kind == 'xml' and not (data.lstrip().startswith(b'<') and
                             re.search(rb'<(?:\w+:)?(?:article|collection)[\s>]', data)):
        raise ValueError('Expected article/BioC XML')
    if kind == 'html' and (data.startswith(b'%PDF-') or b'<' not in data):
        raise ValueError('Expected HTML bytes')
    digest = hashlib.sha256(data).hexdigest()
    destination = folder / 'local' / 'sources' / f'{paper["source_id"]}_{digest}.{kind}'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha(destination) != digest:
        raise ValueError('Source cache hash mismatch')
    if not destination.exists():
        destination.write_bytes(data)
    source = {'path': str(destination.resolve()), 'source_sha256': digest,
              'source_kind': kind, 'origin': candidate['origin'], 'url': final_url,
              'availability': 'input_gap', 'access_basis': candidate['basis'],
              'content_type': content_type, 'retrieved_utc': _now(),
              'parse_status': 'pending', 'coverage': 'Parsing incomplete.'}
    if not any(s.get('source_sha256') == digest and s.get('url') == final_url for s in paper['sources']):
        paper['sources'].append(source)
    try:
        document = parse_document(destination, paper['paper_id'])
    except Exception as exc:
        source.update(parse_status='parse_error', parse_error=f'{type(exc).__name__}: {exc}')
        raise
    source.update(parse_status=document['status'], coverage=document['coverage'])
    if document['status'] not in {'readable', 'readable_partial'}:
        return False
    source['availability'] = 'local'
    if not paper.get('path') or PREFERENCE[kind] < PREFERENCE.get(paper.get('source_kind'), 99):
        paper.update(path=source['path'], source_sha256=digest, source_kind=kind,
                     source_format=kind, availability='local')
    return True


def fetch_sources(inventory_dir, limit=None):
    """Fetch at most limit unresolved papers; preserve every inventory row/source.

    Already-local and already-attempted papers are skipped. Failed/unknown
    requests are recorded without automatic retries. limit=0 is offline.
    """
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ValueError('limit must be a nonnegative integer or None')
    folder = Path(inventory_dir).resolve()
    papers, summary = read(folder / 'papers.json'), read(folder / 'source_inventory.json')
    client, processed = PublicClient(), 0
    client.checkpoint = lambda: _persist(folder, papers, summary)
    for paper in papers:
        if limit is not None and processed >= limit:
            break
        if paper.get('path') or paper.get('fetch_attempts') or paper.get('availability') == 'fetch_in_progress':
            continue
        processed += 1
        paper['availability'] = 'fetch_in_progress'
        _persist(folder, papers, summary)
        try:
            candidates = _search(client, paper)
            seen = set()
            success = False

            def consume(options):
                for candidate in sorted(options, key=lambda c: PREFERENCE[c['kind']]):
                    if candidate['url'] in seen:
                        continue
                    seen.add(candidate['url'])
                    if 'data' in candidate:
                        response = (candidate['data'], candidate['url'], 'text/html', None)
                    else:
                        response = _request(client, paper, candidate['url'], 'open_fulltext_' + candidate['kind'])
                    _persist(folder, papers, summary)
                    if response is None:
                        continue
                    try:
                        if _store(folder, paper, candidate, *response[:3]):
                            return True
                    except Exception as exc:
                        # Parser errors are source-specific and must not discard
                        # the inventory or make downloaded bytes look complete.
                        paper.setdefault('parse_errors', []).append(
                            {'url': candidate['url'], 'error': f'{type(exc).__name__}: {exc}'})
                        if response[3] is not None:
                            response[3]['status'] = 'invalid_or_unparseable_document'
                return False

            success = consume([c for c in candidates if c['kind'] == 'xml'])
            if not success:
                # A DOI/official URL is a landing page only until openness and
                # article identity are explicitly established by its metadata.
                response = _request(client, paper, paper['url'], 'official_landing_metadata')
                _persist(folder, papers, summary)
                if response is not None:
                    if 'html' in response[2].lower() or b'<html' in response[0][:500].lower():
                        extra, reason = _publisher_candidates(response[0], response[1], paper)
                        if reason:
                            paper['availability_reason'] = reason
                        candidates = extra + candidates
                    else:
                        paper['availability_reason'] = 'direct_document_without_explicit_open_access_basis'
                success = consume(candidates)
            if not success:
                paper['availability'] = 'input_gap' if paper['sources'] else 'unavailable'
                paper.setdefault('availability_reason', 'no_confirmed_public_fulltext')
        except Exception as exc:
            paper['availability'] = 'fetch_error'
            paper['fetch_error'] = f'{type(exc).__name__}: {exc}'
        finally:
            paper['fetch_checked_utc'] = _now()
            summary['last_fetch'] = {'checked_utc': _now(), 'processed': processed, 'limit': limit}
            _persist(folder, papers, summary)
            print({'paper_id': paper['paper_id'], 'availability': paper['availability'],
                   'processed': processed}, flush=True)
    summary['last_fetch'] = {'checked_utc': _now(), 'processed': processed, 'limit': limit}
    return _persist(folder, papers, summary)
