"""The shipped payload must use the audited screen, not a browser-only fixture."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
from literature_audit import load_audit


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


class ScreeningPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / 'progress/progress.json').read_text(encoding='utf-8'))
        cls.screen = cls.payload['screen']
        cls.report = json.loads((ROOT / 'results/validation/screening-app-publication.json').read_text(encoding='utf-8'))
        cls.audit = json.loads((ROOT / 'results/validation/screening-ci61.json').read_text(encoding='utf-8'))
        cls.literature, _ = load_audit()

    def test_screen_publication_does_not_release_a_new_model_or_rewrite_history(self):
        rest = {k:v for k,v in self.payload.items() if k != 'screen'}
        self.assertEqual(digest(rest), self.report['unchanged_non_screen_canonical_sha256'])
        self.assertEqual(self.payload['hurricane']['current'], '4.0')
        self.assertEqual(self.screen['models'], ['Radar 1.0', 'Storm 5.0', 'Hurricane 4.0'])
        self.assertEqual(self.screen['hurricane']['model'], 'Hurricane 4.0')
        self.assertTrue(all(v.get('status') != 'adopted' for v in self.payload['hurricane']['versions'] if v['version'] in {'5.0','6.0'}))
        self.assertEqual(self.report['source_binding']['source_commit'], self.audit['source_binding']['source_commit'])
        self.assertEqual(self.report['source_binding']['artifact_sha256'], self.audit['source_binding']['artifact_sha256'])

    def test_actual_deployment_has_all_152_audited_candidates_and_explicit_tracks(self):
        storm, hurricane = self.screen['candidates'], self.screen['hurricane']['candidates']
        self.assertEqual(self.screen['round'], 5)
        self.assertEqual((len(storm), len(hurricane)), (102, 50))
        ids = {c['id'] for c in storm + hurricane}
        self.assertEqual(len(ids), 152)
        self.assertEqual(ids, {key for key,row in self.literature.items() if row['currently_listed']})
        self.assertEqual({k:len(v) for k,v in self.screen['tracks'].items()},
                         {'storm_in_domain':50,'storm_exploration':50,'borides':2,'carbides':0})
        self.assertEqual(set().union(*(set(v) for v in self.screen['tracks'].values())), {c['id'] for c in storm})

    def test_five_fold_probabilities_are_the_audited_values_not_old_scores(self):
        audit = self.audit['hurricane']
        self.assertEqual(audit['member_count'], 5)
        self.assertEqual({f['excluded_background_fold'] for f in audit['fold_audit']}, set(range(5)))
        self.assertTrue(all(f['members_per_query'] == 5 for f in audit['fold_audit']))
        for row in self.screen['hurricane']['candidates']:
            self.assertEqual(row['p_spread_method'], 'same-background-fold-training-fold-ensemble')
            self.assertLessEqual(0, row['p_lo'])
            self.assertLessEqual(row['p_lo'], row['p_sc'])
            self.assertLessEqual(row['p_sc'], row['p_hi'])
            self.assertLessEqual(row['p_hi'], 1)
        yb = next(c for c in self.screen['hurricane']['candidates'] if c['id'] == 'JVASP-16400')
        self.assertEqual((yb['p_sc'], yb['p_lo'], yb['p_hi'], yb['tc_sc']), (0.35, 0.076, 0.487, 4.35))
        self.assertEqual(yb['p_sc'], round(audit['yb_rh_example']['probability_mean'], 3))
        self.assertNotIn(yb['p_sc'], (0.61, 0.165, 0.03))

    def test_ce_literature_corrections_replace_old_false_negative_in_raw_payload(self):
        rows = {c['id']:c for c in self.screen['hurricane']['candidates']}
        for candidate_id in ('JVASP-165558', 'JVASP-165420'):
            check = rows[candidate_id]['check']
            self.assertEqual(check, self.literature[candidate_id]['check_correction']['check'])
            self.assertIsNone(check['superconducts'])
            self.assertNotIn('below', check)
            self.assertIn('unknown', check['note'].lower())

    def test_numeric_predictions_ranks_and_phonons_remain_bound_to_reviewed_screen(self):
        self.assertEqual(digest(self.screen), self.report['deployed_screen_canonical_sha256'])
        scientific = copy.deepcopy(self.screen)
        paths = []
        def walk(value):
            if isinstance(value, dict):
                if 'result_file' in value:
                    name = value.pop('result_file')
                    paths.append(name)
                    self.assertTrue(name.startswith('results/phonons/'))
                    self.assertFalse(Path(name).is_absolute())
                    self.assertNotIn('..', Path(name).parts)
                if value.get('id') in {'JVASP-165558','JVASP-165420'}:
                    value.pop('check', None)
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(scientific)
        self.assertEqual(len(paths), 6)
        self.assertEqual(digest(scientific), self.report['scientific_projection_sha256'])
        phonons = self.screen['phonon_checks']
        self.assertEqual((phonons['eligible'],phonons['selected'],phonons['not_selected']), (50,3,47))
        self.assertEqual([p['verdict'] for p in phonons['materials']],
                         ['imaginary_modes_sampled','imaginary_modes_sampled','no_significant_imaginary_modes_sampled'])
        self.assertIn('or superconductivity test', phonons['scope'])


if __name__ == '__main__':
    unittest.main()
