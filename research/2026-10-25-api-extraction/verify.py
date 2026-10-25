"""Run offline tests, recompute reuse counts, replay real legacy evidence, record results."""
from contextlib import redirect_stdout
from datetime import datetime,timezone
import io
from pathlib import Path
import unittest

from corpus import HERE,read,save,sha
from replay import replay
from reuse import inventory


def main():
    log=io.StringIO()
    with redirect_stdout(log):
        suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
        result=unittest.TextTestRunner(stream=log,verbosity=1).run(suite)
        if not result.wasSuccessful():
            print(log.getvalue())
            raise RuntimeError('Offline tests failed')
        _,summary=inventory()
        previous=read(HERE/'reuse_inventory/summary.json')
        if summary!=previous:raise RuntimeError('Reuse/source snapshot changed; investigate instead of overwriting')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        workspace=HERE/'local'/('verified_replay_'+stamp)
        replay_result=replay(workspace)
    report={'status':'offline_validation_passed','timestamp_utc':stamp,
            'unit_and_integration_tests':result.testsRun,'test_failures':len(result.failures),
            'test_errors':len(result.errors),'live_provider_requests':0,
            'http_tests':'Two loopback HTTP scenarios: normal request and blocked redirect; no paid service',
            'legacy_inventory_reproduced':True,
            'legacy_negative_candidates':summary['negative_candidates'],
            'glue_include_candidates':summary['glue_include_candidates'],
            'glue_include_origin_counts':summary['glue_include_origin_counts'],
            'replay_workspace':workspace.relative_to(HERE).as_posix(),
            'replay_summary':replay_result,
            'code_sha256':{p.name:sha(p) for p in sorted(HERE.glob('*.py'))},
            'prompt_sha256':sha(HERE/'prompt.md'),
            'not_yet_validated':['actual provider authentication and model compatibility',
                                 'fresh model extraction precision/recall','expert semantics or downstream utility']}
    save(HERE/'validation_report.json',report)
    print({'status':report['status'],'tests':result.testsRun,'live_provider_requests':0,
           'legacy_cases':len(replay_result['matched_legacy_cases'])})


if __name__=='__main__':main()
