"""Published/current Hurricane metadata must describe the cohort actually trained."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
import hurricane4 as H4
import hurricane5 as H5
import screen


class HurricaneDisplayCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.progress = json.loads((ROOT / 'progress/progress.json').read_text(encoding='utf-8'))
        cls.raw = {i: json.loads((ROOT / f'results/hurricane_round{i}.json').read_text(encoding='utf-8')) for i in range(1, 6)}

    def test_current_and_each_historical_cohort_match_their_source_report(self):
        block = self.progress['hurricane']
        self.assertEqual(block['current'], '4.0')
        self.assertEqual(block['data'], self.raw[4]['data'])
        self.assertEqual((block['data']['n'], block['data']['n_sc']), (2123, 1395))
        for version in block['versions']:
            self.assertEqual(version['data'], self.raw[version['round']]['data'])
            self.assertEqual(sum(row['n'] for row in version['data']['families'].values()), version['data']['n'])
        self.assertEqual(block['versions'][-1]['status'], 'experimental')
        self.assertEqual((block['versions'][-1]['data']['n'], block['versions'][-1]['data']['n_sc']), (619, 290))

    def test_headline_results_and_status_refer_to_active_h4(self):
        rows = [r for r in self.progress['results'] if r.get('tag') == 'hurricane']
        self.assertEqual(rows[0]['model'], 'Hurricane 4.0 (AI-designed)')
        self.assertEqual(rows[0]['target'], 'Tc_exp')
        self.assertEqual(rows[0]['mae'], round(self.raw[4]['best']['scores']['tc_mae'], 2))
        self.assertIn('2,123', rows[0]['note'])
        family = next(r for r in self.progress['model_family'] if r['id'] == 'hurricane')
        self.assertEqual(family['status'], 'Hurricane 4.0 in use')

    def test_rejected_h5_export_preserves_h4_cohort_and_published_results(self):
        out = copy.deepcopy(self.raw[5]); out['adopted'] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'progress.json'
            path.write_text(json.dumps(self.progress), encoding='utf-8')
            H5.update_progress(out, path)
            actual = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(actual['hurricane']['current'], '4.0')
        self.assertEqual(actual['hurricane']['data'], self.raw[4]['data'])
        self.assertEqual(actual['hurricane']['versions'][-1]['data'], self.raw[5]['data'])
        self.assertEqual(actual['results'], self.progress['results'])
        self.assertEqual(actual['model_family'], self.progress['model_family'])
        self.assertEqual(actual['screen'], self.progress['screen'])

    def test_h4_reexport_keeps_both_version_specific_cohorts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'progress.json'
            path.write_text(json.dumps(self.progress), encoding='utf-8')
            H4.update_progress(self.raw[4], path)
            actual = json.loads(path.read_text(encoding='utf-8'))['hurricane']
        self.assertEqual(actual['data'], self.raw[4]['data'])
        self.assertEqual({v['version']:v['data'] for v in actual['versions']},
                         {v['version']:v['data'] for v in self.progress['hurricane']['versions']})

    def test_display_correction_keeps_raw_result_files_and_unrelated_results_unchanged(self):
        correction = json.loads((ROOT / 'results/validation/hurricane-display-cohort-correction.json').read_text(encoding='utf-8'))
        for name, expected in correction['source_reports'].items():
            actual = hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            self.assertEqual(actual, expected)
        for patch in correction['corrections']:
            if patch['pointer'] in {'/results', '/model_family'}:
                key = 'tag' if patch['pointer'] == '/results' else 'id'
                self.assertEqual([r for r in patch['before'] if r.get(key) != 'hurricane'],
                                 [r for r in patch['after'] if r.get(key) != 'hurricane'])

    def test_screen_stage_counts_current_candidates_and_only_completed_phonon_checks(self):
        payload = {'round': 7, 'candidates': [{}, {}], 'hurricane': {'candidates': [{}]},
                   'phonon_checks': {'materials': [
                       {'status': 'completed', 'verdict': 'imaginary_modes_sampled'},
                       {'status': 'completed', 'verdict': 'no_significant_imaginary_modes_sampled'},
                       {'status': 'failed', 'verdict': 'not_assessed'},
                       {'status': 'pending', 'verdict': None}]}}
        detail = screen.screening_stage_detail(payload)
        self.assertIn('Round 7: 2 Storm candidates and 1 Hurricane candidates', detail)
        self.assertIn('2 sampled-phonon checks completed', detail)
        self.assertIn('not proof of novelty', detail)
        payload['phonon_checks']['materials'] = [{'status': 'failed', 'verdict': 'not_assessed'}]
        self.assertNotIn('checks completed', screen.screening_stage_detail(payload))


if __name__ == '__main__':
    unittest.main()
