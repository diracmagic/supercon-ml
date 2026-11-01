"""External research must preserve evidence boundaries and safe offline delivery."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_external_research', ROOT / 'tools' / 'build_external_research.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class ExternalResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = BUILD.load_registry()

    def test_reviewed_source_matches_offline_bundle_exactly(self):
        expected = BUILD.bundle_bytes(self.registry)
        self.assertEqual(expected, BUILD.OUTPUT.read_bytes())
        self.assertLess(len(expected), 70_000)
        self.assertEqual(BUILD.main(['--check']), 0)
        self.assertFalse(any('C:\\Users' in str(v) for v in self.registry.values()))

    def test_citation_and_evidence_boundaries_survive_seed_import(self):
        by_id = {row['id']: row for row in self.registry['entries']}
        self.assertTrue({f'{n:02d}' for n in range(1, 32)}.issubset(by_id))
        self.assertEqual(by_id['28']['doi'], '10.1140/epjp/s13360-024-05947-w')
        self.assertEqual(by_id['29']['doi'], '10.1038/s41524-023-01023-6')
        self.assertEqual(by_id['30']['doi'], '10.1038/s41524-026-02117-7')
        self.assertIn('杂相', by_id['29']['boundary'])
        self.assertIn('预测晶体一般未形成', by_id['30']['boundary'])
        self.assertIn('Tc=0', by_id['31']['boundary'])
        self.assertEqual(by_id['23']['category'], '研究计划')
        self.assertEqual(by_id['24']['category'], '研究计划')

    def test_forecast_or_plan_cannot_be_promoted_to_experiment(self):
        for entry_id in ('01', '07', '19', '22', '23', '24'):
            with self.subTest(entry_id=entry_id):
                bad = copy.deepcopy(self.registry)
                row = next(e for e in bad['entries'] if e['id'] == entry_id)
                row['progress_steps'].append({'kind':'measurement','label':'实验','detail':'错误新增','status':'completed'})
                with self.assertRaisesRegex(ValueError, 'cannot claim an experimental stage'):
                    BUILD.validate_registry(bad)

    def test_script_injection_is_encoded_and_content_roundtrips(self):
        data = copy.deepcopy(self.registry)
        payload = '</script><script>alert(1)</script>&\u2028\u2029'
        data['entries'][0]['boundary'] = payload
        js = BUILD.bundle_bytes(data).decode('utf-8')
        self.assertNotIn('</script>', js)
        decoded = json.loads(js.split('globalThis.SuperconExternalResearch = ', 1)[1].rstrip().removesuffix(';'))
        self.assertEqual(decoded['entries'][0]['boundary'], payload)

    def test_non_public_or_executable_links_rejected(self):
        unsafe = ['javascript:alert(1)', 'data:text/html,test', 'http://example.com',
                  'https://user:secret@example.com/', 'https://127.0.0.1/',
                  'https://localhost/', 'https://10.0.0.1/', 'https://example.com/%0Aevil',
                  'https://example.com\\evil', 'https://example.com:8080/']
        for url in unsafe:
            with self.subTest(url=url), self.assertRaises(ValueError):
                BUILD.safe_url(url)
        BUILD.safe_url('https://doi.org/10.1140/epjp/s13360-024-05947-w')
        BUILD.safe_url('https://example.org/author%20data.pdf')

    def test_ids_and_dates_cannot_silently_merge_or_claim_future_review(self):
        bad = copy.deepcopy(self.registry)
        bad['entries'][1]['id'] = bad['entries'][0]['id']
        with self.assertRaisesRegex(ValueError, 'Duplicate stable entry ID'):
            BUILD.validate_registry(bad)
        bad = copy.deepcopy(self.registry)
        bad['entries'][0]['reviewed_on'] = '2999-01-01'
        with self.assertRaisesRegex(ValueError, 'future entry review date'):
            BUILD.validate_registry(bad)
        bad = copy.deepcopy(self.registry)
        bad['schedule']['status'] = 'daily_review_success'
        with self.assertRaisesRegex(ValueError, 'not review completion'):
            BUILD.validate_registry(bad)

    def test_manifest_cannot_read_outside_review_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'schema_version':1,'entry_count':1,'entry_parts':['../outside.json']}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Invalid part path'):
                BUILD.load_registry(path)


if __name__ == '__main__':
    unittest.main()
