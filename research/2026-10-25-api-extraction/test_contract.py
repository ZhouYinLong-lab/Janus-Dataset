from copy import deepcopy
import unittest
from contract import FIELDS,validate
from prepare import build_jobs,split_units


def fixture():
    unit={'unit_id':'P:1','kind':'body_paragraph','locator':'p1','section':'Results',
          'text':'Compound X did not degrade GSPT1 after 6 hours in HEK293 cells.'}
    job={'job_id':'P_job','paper_id':'P','doi':None,'source_sha256':'hash',
         'primary_units':[unit],'context_units':[]}
    fields={f:None for f in FIELDS}
    fields.update(compound='Compound X',target='GSPT1',result_text='No degradation reported')
    record={'domain':'molecular_glue','negative_type':'no_degradation','experimental_setting':'unperturbed',
            'directness':'explicit','fields':fields,'qualifiers':[],
            'evidence':[{'field':f,'unit_id':'P:1','quote':unit['text']} for f in ['compound','target','result_text']]}
    return job,{'schema_version':1,'paper_id':'P','records':[record],'coverage_notes':[], 'no_negative_reason':None}


class ContractTests(unittest.TestCase):
    def test_grounded_is_not_training_ready(self):
        j,p=fixture();r=validate(p,j)
        self.assertTrue(r['accepted'][0]['primary_candidate'])
        self.assertFalse(r['accepted'][0]['ready_for_training'])
        self.assertEqual(r['accepted'][0]['table_overlap'],'not_evaluated')

    def test_fabricated_quote_quarantined(self):
        j,p=fixture();p['records'][0]['evidence'][0]['quote']='Invented experiment result'
        self.assertFalse(validate(p,j)['accepted'])

    def test_unknown_unit_quarantined(self):
        j,p=fixture();p['records'][0]['evidence'][0]['unit_id']='P:missing'
        self.assertFalse(validate(p,j)['accepted'])

    def test_ungrounded_condition_quarantined(self):
        j,p=fixture();p['records'][0]['fields']['treatment_time']='48 h'
        self.assertIn('ungrounded_field:treatment_time',validate(p,j)['rejected'][0]['errors'])

    def test_context_only_result_not_primary(self):
        j,p=fixture();j['context_units']=j['primary_units'];j['primary_units']=[]
        self.assertFalse(validate(p,j)['accepted'])

    def test_target_not_detected_is_risk_not_negative(self):
        j,p=fixture();p['records'][0]['negative_type']='target_not_detected'
        self.assertFalse(validate(p,j)['accepted'][0]['primary_candidate'])

    def test_protac_separate(self):
        j,p=fixture();p['records'][0]['domain']='protac'
        self.assertFalse(validate(p,j)['accepted'][0]['primary_candidate'])

    def test_paper_mismatch_rejected(self):
        j,p=fixture();p['paper_id']='OTHER'
        with self.assertRaises(ValueError):validate(p,j)

    def test_empty_requires_reason(self):
        j,p=fixture();p['records']=[]
        with self.assertRaises(ValueError):validate(p,j)
        p['no_negative_reason']='No negative result in these primary paragraphs.'
        self.assertEqual(validate(p,j)['accepted'],[])

    def test_relative_not_primary(self):
        j,p=fixture();p['records'][0]['negative_type']='relative_weakening'
        self.assertFalse(validate(p,j)['accepted'][0]['primary_candidate'])

    def test_all_body_units_scanned(self):
        unit=fixture()[0]['primary_units'][0]
        units=[dict(unit,unit_id=f'P:{i}',text=('positive result ' if i%2 else 'no effect ')*70) for i in range(12)]
        d={'paper_id':'P','source_sha256':'s','source_path':'source.xml','units':units}
        jobs=build_jobs(d,{},primary_cap=3000,context_cap=2000)
        self.assertEqual({u['unit_id'] for j in jobs for u in j['primary_units']},{u['unit_id'] for u in units})

    def test_long_unit_no_silent_loss(self):
        u=dict(fixture()[0]['primary_units'][0],text='0123456789'*2000)
        pieces=split_units([u]);coverage=set()
        for p in pieces:coverage.update(range(p['char_start'],p['char_end']))
        self.assertEqual(len(coverage),len(u['text']))


if __name__=='__main__':unittest.main()
