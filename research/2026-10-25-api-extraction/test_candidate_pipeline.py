"""End-to-end invariants using a local injected provider, never real credentials."""
import json
from pathlib import Path
import tempfile
import unittest

import batch_budget
from batch_candidate import candidate_enrichment, candidate_request_for
from candidate_workspace import prepare, verify
from candidate_export import export, snapshot
from candidate_runtime import run
from contract import FIELDS
from corpus import read, save


TEXT = ('HeLa cells received compound X at 10 microM for 24 h. '
        'Compound X did not degrade protein Y. Compound Z did not degrade protein Y.')


class Provider:
    def __init__(self, duplicates=False):
        self.calls = 0
        self.duplicates = duplicates

    def complete(self, request):
        self.calls += 1
        user = json.loads(request['messages'][1]['content'])
        if 'primary_units' in user:
            uid = user['primary_units'][0]['unit_id']
            compounds = ['X', 'X'] if self.duplicates else ['X', 'Z']
            payload = {'paper_id': user['paper_id'], 'coverage_notes': [],
                       'no_candidate_reason': None, 'candidates': [
                {'candidate_id': 'C'+str(i), 'unit_id': uid,
                 'quote': f'Compound {compound} did not degrade protein Y.',
                 'compound_mentions': [f'Compound {compound}'], 'condition_mentions': [],
                 'category': 'no_degradation', 'notes': []}
                for i, compound in enumerate(compounds)]}
        else:
            items = []
            for c in user['candidates']:
                compound = 'X' if 'Compound X' in c['quote'] else 'Z'
                fields = dict.fromkeys(FIELDS)
                fields.update(compound='Compound '+compound, target='protein Y',
                              endpoint='protein degradation', result_text=c['quote'])
                evidence = [{'field': f, 'unit_id': c['unit_id'], 'quote': c['quote']}
                            for f in ('compound', 'target', 'endpoint', 'result_text')]
                if compound == 'X':
                    fields['cell_line'] = 'HeLa'
                    evidence.append({'field': 'cell_line', 'unit_id': c['unit_id'],
                                     'quote': TEXT.split(' Compound X')[0]})
                statuses = {f: 'supported' if fields[f] is not None else
                            'not_found_in_supplied_context' for f in FIELDS}
                if self.duplicates and c['candidate_id'] == 'C1':
                    statuses['construct'] = 'ambiguous_in_supplied_context'
                items.append({'candidate_id': c['candidate_id'], 'field_search_status': statuses,
                              'record': {'domain': 'molecular_glue', 'negative_type': 'no_degradation',
                                'experimental_setting': 'unperturbed', 'directness': 'explicit',
                                'fields': fields, 'evidence': evidence, 'qualifiers': []}})
            payload = {'paper_id': user['paper_id'], 'items': items, 'unresolved': [], 'coverage_notes': []}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(payload)}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}, 'model': 'test'}


class CandidatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root/'paper.xml'
        source.write_text('<article><body><sec><title>Results</title><p>'+TEXT+
                          '</p></sec></body></article>', encoding='utf-8')
        self.manifest = self.root/'papers.json'
        save(self.manifest, [{'paper_id': 'P1', 'path': str(source), 'doi': '10.1/example',
                              'source_kind': 'paper', 'availability': 'full_text_available'}])
        self.workspace = self.root/'work'
        prepare(self.workspace, papers=['P1'], manifest_path=self.manifest, phase='pilot')
        self.ledger = self.root/'budget.json'
        batch_budget.create(self.ledger, 10, 1_000_000, 'Local injected-provider tests only')
        self.config = {'base_url': 'http://localhost', 'model': 'test', 'api_key_env': 'JANUS_TEST_KEY',
            'timeout_seconds': 1, 'max_output_tokens': 100, 'output_token_parameter': 'max_tokens',
            'response_format': 'json_object', 'max_requests': 10, 'max_reserved_tokens': 1_000_000}

    def execute(self, provider, workspace=None):
        return run(workspace or self.workspace, self.config, self.ledger,
                   candidate_request_for, candidate_enrichment, live=True, client=provider,
                   phase='pilot', on_progress=export)

    def test_same_paragraph_fields_and_repeat_resume(self):
        provider = Provider()
        self.execute(provider)
        first_calls = provider.calls
        summary = export(self.workspace)
        self.assertEqual(summary['unique_records'], 2)
        self.assertEqual(summary['failed_tasks'], 0)
        values = read(self.workspace/'exports/records.json')
        self.assertEqual(next(r for r in values if r['fields']['compound'] == 'Compound X')['fields']['cell_line'], 'HeLa')
        self.execute(provider)
        self.assertEqual(first_calls, provider.calls)
        before = {p: p.stat().st_mtime_ns for p in self.workspace.rglob('*') if p.is_file()}
        snapshot(self.workspace)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_merged_records_keep_individual_statuses(self):
        self.execute(Provider(duplicates=True))
        export(self.workspace)
        rows = read(self.workspace/'exports/records.json')
        self.assertEqual(len(rows), 1)
        self.assertNotIn('field_search_status', rows[0])
        statuses = {r['field_search_status']['construct'] for r in rows[0]['provenance']}
        self.assertEqual(statuses, {'not_found_in_supplied_context', 'ambiguous_in_supplied_context'})

    def test_source_change_stops_before_provider(self):
        m = verify(self.workspace)
        Path(m['papers'][0]['source_path']).write_text('changed', encoding='utf-8')
        provider = Provider()
        with self.assertRaises(ValueError):
            self.execute(provider)
        self.assertEqual(provider.calls, 0)

    def test_full_run_requires_acceptance(self):
        from candidate_acceptance import require_acceptance
        with self.assertRaises(ValueError):
            require_acceptance(None, self.workspace, self.config)


if __name__ == '__main__':
    unittest.main()
