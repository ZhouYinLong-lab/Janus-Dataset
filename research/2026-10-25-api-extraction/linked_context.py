"""Offline figure/table links layered over unchanged corpus units and locators."""
from collections import defaultdict
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from corpus import tag, text


# A label includes its namespace: Figure 1, Figure S1 and Supplementary Figure 1
# are distinct from the main Figure 1. Never infer a label from an XML id number.
_REF = re.compile(
    r'\b(?P<supp>(?:supplementary|supplemental|supporting)'
    r'(?:\s+(?:information|material))?\s+)?'
    r'(?P<kind>fig(?:ure)?s?\.?|tables?\.?|schemes?\.?)\s*'
    r'(?P<number>S?\s*\d+)(?:[A-Za-z](?![A-Za-z]))?\b', re.I)
_MORE = re.compile(r'\s*(?P<sep>[,;–−-]|and|&)\s*(?P<number>S?\s*\d+)'
                   r'(?:[A-Za-z](?![A-Za-z]))?\b', re.I)
_SUPP_SUFFIX = re.compile(
    r'^\s*[,;]?\s*(?:\(?\s*(?:in\s+(?:the\s+)?)?(?:supporting\s+information|'
    r'supplementary\s+(?:information|material)|supplemental\s+material))\b', re.I)
_SUPP_SCOPE = re.compile(r'\b(?:supplementary|supplemental|supporting information)\b', re.I)
_METHOD = re.compile(
    r'\b(methods?|experimental|procedures?|protocols?|assays?|western blot(?:ting)?|'
    r'cell culture)\b', re.I)
_ACTION = re.compile(
    r'\b(?:were|was)\s+(?:\w+\s+){0,2}'
    r'(?:washed|lysed|seeded|incubated|cultured|transfected|treated|measured)\b', re.I)
_BLOCKS = {'fig', 'table-wrap', 'table', 'supplementary-material'}


def _labels(value):
    """Read explicit labels, including bounded lists/ranges; no bare numbers."""
    for match in _REF.finditer(value):
        kind = match['kind'].lower()
        kind = 'table' if kind.startswith('tab') else 'scheme' if kind.startswith('sch') else 'figure'
        number = re.sub(r'\s+', '', match['number']).upper()
        supplement = bool(match['supp'] or number.startswith('S'))
        end = match.end()
        previous = int(number.lstrip('S'))
        entries = [(previous, supplement, end)]
        while more := _MORE.match(value, end):
            number = re.sub(r'\s+', '', more['number']).upper()
            current = int(number.lstrip('S'))
            scoped = supplement or number.startswith('S')
            if more['sep'] in {'-', '–', '−'} and 0 < current - previous <= 30:
                for n in range(previous + 1, current):
                    entries.append((n, scoped, more.end()))
            entries.append((current, scoped, more.end()))
            previous, supplement, end = current, scoped, more.end()
        trailing_supplement = bool(_SUPP_SUFFIX.match(value[end:]))
        for number, supplement, label_end in entries:
            yield (kind, supplement or trailing_supplement, number), value[match.start():label_end]


def _prose(node):
    """Collect xrefs and plain prose separately, excluding nested table/fig text."""
    parts = [node.text or '']
    refs = []
    for child in node:
        if tag(child) == 'xref':
            refs.append(child)
            parts.append(' ')  # An authoritative rid must not be relinked by label.
        elif tag(child) not in _BLOCKS:
            content, nested = _prose(child)
            parts.append(content)
            refs.extend(nested)
        parts.append(child.tail or '')
    return ''.join(parts), refs


def _parent_id(unit):
    return unit.get('parent_unit_id', unit['unit_id'])


class LinkedContext:
    def __init__(self, document):
        self.units = {u['unit_id']: u for u in document['units']}
        self.positions = {u['unit_id']: i for i, u in enumerate(
            u for u in document['units'] if u['kind'] == 'body_paragraph')}
        self.nodes = {}
        self.sections = {}
        self.supplement_locators = set()
        self.method_units = set()
        self.label_index = defaultdict(set)
        self.xml_status = 'unavailable'
        self._load_xml(document)
        for uid, unit in self.units.items():
            if unit['kind'] not in {'table', 'figure_caption'}:
                continue
            node = self.nodes.get(unit['locator'])
            if node is not None:
                label = next((text(c) for c in node if tag(c) == 'label'), '')
            else:
                # BioC/no XML: only an anchored, explicit caption/table label is safe.
                label = unit['text'] if _REF.match(unit['text']) else ''
            keys = _labels(label)
            # Only the leading label identifies a text-only target; later mentions
            # inside its caption may refer to entirely different figures/tables.
            if node is None:
                first = next(keys, None)
                keys = [first] if first else []
            for key, _ in keys:
                if (unit['kind'] == 'table') != (key[0] == 'table'):
                    continue
                if unit['locator'] in self.supplement_locators or _SUPP_SCOPE.search(unit.get('section', '')):
                    key = (key[0], True, key[2])
                self.label_index[key].add(uid)

    def _load_xml(self, document):
        try:
            path = Path(document['source_path'])
            if path.suffix.lower() == '.txt':
                self.xml_status = 'text_source'
                return
            raw = path.read_bytes()
            if len(raw) > 20_000_000 or b'<!ENTITY' in raw:
                self.xml_status = 'unsafe_xml'
                return
            if hashlib.sha256(raw).hexdigest() != document['source_sha256']:
                self.xml_status = 'source_hash_mismatch'
                return
            root = ET.fromstring(raw)
        except (OSError, ValueError, ET.ParseError, KeyError):
            return
        if any(tag(n) == 'passage' for n in root.iter()):
            self.xml_status = 'bioc_text_labels'
            return
        body = next((n for n in root.iter() if tag(n) == 'body'), None)
        if body is None:
            self.xml_status = 'no_xml_body'
            return
        self.xml_status = 'jats'

        def visit(node, address, section='', method=False, supplement=False):
            kind = tag(node)
            locator = node.get('id') or address
            if kind in {'ref-list', 'ack', 'permissions', 'supplementary-material'}:
                return
            if kind == 'sec':
                section = locator
                title = next((text(c) for c in node if tag(c) == 'title'), '')
                method = method or bool(_METHOD.search(title + ' ' + node.get('sec-type', '')))
                supplement = supplement or bool(_SUPP_SCOPE.search(title))
            self.nodes[locator] = node
            self.sections[locator] = (section, method)
            if supplement:
                self.supplement_locators.add(locator)
            if kind in {'fig', 'table-wrap', 'table'}:
                return
            for i, child in enumerate(node):
                visit(child, f'{address}/{tag(child)}[{i+1}]', section, method, supplement)

        visit(body, 'body')
        for uid, unit in self.units.items():
            if self.sections.get(unit['locator'], ('', False))[1]:
                self.method_units.add(uid)

    def _section(self, unit):
        if unit['locator'] in self.sections:
            return self.sections[unit['locator']][0]
        locator = unit['locator']
        return locator.rsplit('/', 1)[0] if '/' in locator else unit.get('section', '')

    def references(self, primary):
        by_locator = defaultdict(list)
        for uid, unit in self.units.items():
            if unit['kind'] in {'table', 'figure_caption'}:
                by_locator[unit['locator']].append(uid)
        result = []
        seen = set()
        for unit in primary:
            uid = _parent_id(unit)
            if uid in seen:
                continue
            seen.add(uid)
            original = self.units[uid]
            node = self.nodes.get(original['locator'])
            if node is not None:
                prose, xrefs = _prose(node)
            else:
                prose, xrefs = original['text'], []
            for xref in xrefs:
                rids = xref.get('rid', '').split() or ['']
                # Some JATS sources use ref-type="other" for real table links.
                if (xref.get('ref-type') not in {'fig', 'table', 'supplementary-material'} and
                    not any(rid in by_locator for rid in rids) and not _REF.search(text(xref))):
                    continue
                for rid in rids:
                    result.append({'source_unit_id': uid, 'via': 'xml_xref',
                                   'rid': rid, 'label': text(xref),
                                   'target_unit_ids': by_locator.get(rid, [])})
            for key, label in _labels(prose):
                if original['locator'] in self.supplement_locators or _SUPP_SCOPE.search(original.get('section', '')):
                    key = (key[0], True, key[2])
                matches = sorted(self.label_index.get(key, ()))
                # Duplicate labels cannot establish a unique target.
                result.append({'source_unit_id': uid, 'via': 'text_label',
                               'label': label, 'label_key': list(key),
                               'target_unit_ids': matches if len(matches) == 1 else [],
                               'resolution': 'ambiguous_label' if len(matches) > 1 else
                                             'matched' if matches else 'missing_label'})
        return result

    def select(self, primary, options, cap):
        if cap < 0:
            raise ValueError('context_cap must be nonnegative')
        refs = self.references(primary)
        explicit = {uid for ref in refs for uid in ref['target_unit_ids']}
        primary_ids = {_parent_id(u) for u in primary}
        words = set(re.findall(r'[a-z0-9]{3,}', ' '.join(u['text'] for u in primary).lower()))

        def priority(unit):
            uid = _parent_id(unit)
            if uid in explicit:
                return 0, 0
            original = self.units[uid]
            if original['kind'] == 'body_paragraph' and (
                uid in self.method_units or _METHOD.search(original.get('section', '')) or
                _ACTION.search(original['text'])
            ):
                distances = [abs(self.positions[uid] - self.positions[pid])
                             for pid in primary_ids if pid in self.positions and
                             self._section(original) and
                             self._section(original) == self._section(self.units[pid])]
                if distances and min(distances) <= 2:
                    return 1, min(distances)
            return 2, 0

        def rank(unit):
            overlap = len(words & set(re.findall(r'[a-z0-9]{3,}', unit['text'].lower())))
            return (*priority(unit), -overlap, unit['unit_id'])

        context, candidates, used = [], [], 0
        selected = set()
        for unit in sorted(options, key=rank):
            fits = used + len(unit['text']) <= cap
            if fits:
                context.append(unit)
                selected.add(unit['unit_id'])
                used += len(unit['text'])
            candidates.append({'unit_id': unit['unit_id'], 'parent_unit_id': _parent_id(unit),
                               'locator': unit['locator'], 'chars': len(unit['text']),
                               'priority': ('explicit_reference', 'nearby_method', 'word_overlap')[priority(unit)[0]],
                               'status': 'selected' if fits else 'omitted_context_cap'})
        for ref in refs:
            targets = set(ref['target_unit_ids'])
            pieces = [u['unit_id'] for u in options if _parent_id(u) in targets]
            ref['selected_unit_ids'] = [uid for uid in pieces if uid in selected]
            ref['omitted_unit_ids'] = [uid for uid in pieces if uid not in selected]
            ref['status'] = ('unresolved' if not targets else
                             'partial_context_cap' if ref['omitted_unit_ids'] and ref['selected_unit_ids'] else
                             'omitted_context_cap' if ref['omitted_unit_ids'] else 'selected')
        return context, {'version': 1, 'xml_status': self.xml_status, 'context_cap': cap,
                         'context_chars': used, 'references': refs, 'candidates': candidates}
