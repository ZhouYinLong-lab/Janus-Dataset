"""Strict extraction contract and quote grounding; semantic review remains separate."""
import hashlib
import json
from corpus import normal

VERSION=1
FIELDS=('compound','target','construct','assay','cell_line','treatment_time',
        'tested_concentration','perturbation','endpoint','result_text')
DOMAINS={'molecular_glue','protac','engineered_tag','other','uncertain'}
NEGATIVES={'no_degradation','no_significant_degradation','no_abundance_change',
           'reported_zero','response_not_detected','conditional_loss',
           'relative_weakening','target_not_detected','uncertain'}
PRIMARY_NEGATIVES=NEGATIVES-{'relative_weakening','target_not_detected','uncertain'}


def validate(payload,job):
    if not isinstance(payload,dict) or payload.get('schema_version')!=VERSION:
        raise ValueError('Expected schema_version1 object')
    if payload.get('paper_id')!=job['paper_id']:
        raise ValueError('Response paper identity mismatch')
    records=payload.get('records')
    if not isinstance(records,list) or len(records)>100:
        raise ValueError('Expected records array of at most100 observations')
    notes=payload.get('coverage_notes')
    if not isinstance(notes,list) or any(not isinstance(x,str) for x in notes):
        raise ValueError('coverage_notes must be an array of strings')
    if not records and not isinstance(payload.get('no_negative_reason'),str):
        raise ValueError('An empty result needs an explicit reason; it is not proof of no negatives')
    units={u['unit_id']:u for u in job['primary_units']+job['context_units']}
    primary_ids={u['unit_id'] for u in job['primary_units']}
    accepted,rejected=[],[]
    for index,record in enumerate(records):
        errors=[]
        if not isinstance(record,dict):
            rejected.append({'index':index,'record':record,'errors':['record_not_object']});continue
        if set(record)!= {'domain','negative_type','experimental_setting','directness','fields','evidence','qualifiers'}:
            errors.append('unexpected_or_missing_record_keys')
        if record.get('domain') not in DOMAINS:errors.append('invalid_domain')
        if record.get('negative_type') not in NEGATIVES:errors.append('invalid_negative_type')
        if record.get('experimental_setting') not in {'unperturbed','special_condition','mixed_or_unclear'}:
            errors.append('invalid_experimental_setting')
        if record.get('directness') not in {'explicit','author_inferred','unclear'}:errors.append('invalid_directness')
        fields=record.get('fields')
        if not isinstance(fields,dict) or set(fields)!=set(FIELDS):
            errors.append('invalid_fields');fields={}
        for field,value in fields.items():
            if value is not None and (not isinstance(value,str) or not value.strip() or len(value)>2000):
                errors.append('invalid_field_value:'+field)
        evidence=record.get('evidence')
        by_field={field:[] for field in FIELDS}
        if not isinstance(evidence,list) or not evidence or len(evidence)>100:
            errors.append('invalid_evidence');evidence=[]
        for item in evidence:
            if not isinstance(item,dict) or set(item)!= {'field','unit_id','quote'}:
                errors.append('invalid_evidence_item');continue
            field,uid,quote=item['field'],item['unit_id'],item['quote']
            if field not in FIELDS or not isinstance(uid,str) or uid not in units:
                errors.append('unknown_field_or_unit');continue
            if not isinstance(quote,str) or len(normal(quote))<8 or len(quote)>3000:
                errors.append('invalid_quote');continue
            if normal(quote) not in normal(units[uid]['text']):
                errors.append('quote_not_in_cited_unit');continue
            by_field[field].append(uid)
        for field,value in fields.items():
            if value is not None and not by_field.get(field):errors.append('ungrounded_field:'+field)
        if not fields.get('result_text') or not by_field['result_text']:
            errors.append('missing_result_evidence')
        if not (set(by_field['result_text']) & primary_ids):
            errors.append('result_not_in_scanned_primary_body')
        qualifiers=record.get('qualifiers')
        if not isinstance(qualifiers,list) or any(not isinstance(x,str) for x in qualifiers):
            errors.append('invalid_qualifiers')
        if errors:
            rejected.append({'index':index,'record':record,'errors':sorted(set(errors))});continue
        canonical={k:record[k] for k in ['domain','negative_type','experimental_setting','fields']}
        record_hash=hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        accepted.append(dict(record,record_key=job['paper_id']+':'+record_hash[:20],
            result_origin='body_narrative',source_sha256=job['source_sha256'],
            paper_id=job['paper_id'],doi=job.get('doi'),job_id=job['job_id'],
            quote_checks='passed_normalized_substring',semantic_review='pending',expert_gold=False,
            ready_for_training=False,
            primary_candidate=(record['domain']=='molecular_glue'
                and record['negative_type'] in PRIMARY_NEGATIVES
                and fields.get('compound') is not None and fields.get('target') is not None),
            table_overlap='not_evaluated',
            result_units=sorted(set(by_field['result_text']))))
    return {'accepted':accepted,'rejected':rejected,'coverage_notes':notes,
            'no_negative_reason':payload.get('no_negative_reason'),
            'semantic_validation':'not performed; quotes may exist without supporting the claim'}
