"""Local source units with stable identities; no network or inference."""
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY = ROOT / 'research/2026-10-22-sol-extraction/batch02'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normal(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value).casefold()).replace('μ', 'µ')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def text(node):
    return ' '.join(' '.join(node.itertext()).split())


def tag(node):
    return node.tag.rsplit('}', 1)[-1]


def parse_source(path, paper_id):
    """Separate narrative, table and figure sources. Never read figure pixels."""
    path = Path(path)
    raw = path.read_bytes()
    if len(raw)>20_000_000:
        raise ValueError('Source exceeds20MB; split/review it explicitly')
    if b'<!ENTITY' in raw:
        raise ValueError('XML entity declarations are not accepted')
    units = []

    def add(kind, locator, content, section=''):
        if not content.strip():
            return
        digest = hashlib.sha256(f'{paper_id}:{kind}:{locator}:{content}'.encode()).hexdigest()[:16]
        units.append({'unit_id':paper_id+':'+digest,'kind':kind,'locator':locator,
                      'section':section,'text':content})

    if path.suffix.lower()=='.txt':
        for i, paragraph in enumerate(re.split(r'\n\s*\n', raw.decode('utf-8-sig'))):
            add('unsegmented_text',f'paragraph:{i+1}',paragraph.strip())
    else:
        tree = ET.fromstring(raw)
        if any(tag(n)=='passage' for n in tree.iter()):
            for i, node in enumerate(n for n in tree.iter() if tag(n)=='passage'):
                info={n.get('key'):text(n) for n in node if tag(n)=='infon'}
                role=(info.get('section_type','')+' '+info.get('type','')).upper()
                kind='body_paragraph'
                if 'TABLE' in role:kind='table'
                elif 'FIG' in role:kind='figure_caption'
                elif any(x in role for x in ('REF','ABSTRACT','TITLE','AUTH')):kind='other'
                offset=next((text(n) for n in node if tag(n)=='offset'),str(i))
                content=' '.join(text(n) for n in node if tag(n)=='text')
                add(kind,f'bioc_passage:{i}:offset:{offset}',content,role)
        else:
            body=next((n for n in tree.iter() if tag(n)=='body'),None)
            if body is not None:
                def visit(node, address, section=''):
                    kind=tag(node)
                    if kind=='sec':
                        section=next((text(n) for n in node if tag(n)=='title'),section)
                    locator=node.get('id') or address
                    if kind=='table-wrap':
                        add('table',locator,text(node),section)
                        return
                    if kind=='fig':
                        caption=next((n for n in node if tag(n)=='caption'),None)
                        if caption is not None:add('figure_caption',locator,text(caption),section)
                        return
                    if kind in {'ref-list','ack','permissions','supplementary-material'}:
                        return
                    if kind=='p':
                        add('body_paragraph',locator,text(node),section)
                        return
                    for i,child in enumerate(node):
                        visit(child,f'{address}/{tag(child)}[{i+1}]',section)
                visit(body,'body')
    return {'paper_id':paper_id,'source_path':str(path.resolve()),'source_sha256':sha(path),
            'source_bytes':len(raw),'units':units,
            'status':'readable' if any(u['kind']=='body_paragraph' for u in units) else 'no_structured_body',
            'coverage':'XML text and captions only; no figure pixels or independent supplementary files'}


def locate_quote(units, quote):
    needle=normal(quote)
    if not needle:return []
    return [{'unit_id':u['unit_id'],'kind':u['kind'],'locator':u['locator']}
            for u in units if needle in normal(u['text'])]


def existing_papers(legacy=LEGACY):
    legacy=Path(legacy)
    records=read(legacy/'continuation_2026-10-24/final_records.json')['records']
    metadata={r['paper_id']:r for r in read(legacy/'source_manifest.json')}
    papers={}
    for pid,m in metadata.items():
        files=sorted((legacy/'sources').glob(pid+'_*'))
        if not files:continue
        group=[r for r in records if r['paper_id']==pid]
        scopes=sorted({r['scope_group'] for r in group})
        papers[pid]={'paper_id':pid,'path':str(files[0].resolve()),'doi':m.get('doi'),
                     'title':m.get('title'),'url':m.get('url'),
                     'source_license':m.get('source_license'),
                     'legacy_scope_groups':scopes,
                     'legacy_metadata_decisions':sorted({r['metadata_decision'] for r in group}),
                     'scope_basis':'Inherited paper screening, not newly verified glue-specific membership'}
    return records,papers
