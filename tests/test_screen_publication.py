"""The shipped payload must use the audited screen, not a browser-only fixture."""
import copy
import csv
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
        cls.deployed = cls.payload['screen']
        cls.report = json.loads((ROOT / 'results/validation/screening-app-publication.json').read_text(encoding='utf-8'))
        cls.audit = json.loads((ROOT / 'results/validation/screening-ci61.json').read_text(encoding='utf-8'))
        cls.literature, _ = load_audit()
        # Screening round 6 replaces Hurricane's list (screened by Hurricane 4.0) with the list of the version in use.
        # Its record, written before that run, names the two fields of the screen block the run may replace and keeps
        # the audited list. Before the run the deployed screen is the audited one; after it, putting the two recorded
        # values back must give the audited screen, so every check of the round-5 audit below still runs on the
        # payload that audit saw, and Storm's list is bound to it hash for hash.
        cls.round6 = json.loads((ROOT / 'results/validation/hurricane9-screen-publication.json').read_text(encoding='utf-8'))
        cls.rescreened = cls.deployed['hurricane']['model'] != 'Hurricane 4.0'
        # The correction to the screening pools comes after round 6 and adds one field to the screen block, /hull: each
        # published candidate's distance to the convex hull computed from JARVIS-DFT's formation energies. Its record,
        # written before that run, names the field and the log entry. The screen without the field is the published
        # screen, and everything below runs on it, so the correction can add what it says and change nothing else.
        cls.hull_record = json.loads((ROOT / 'results/validation/screen-hull-correction-publication.json').read_text(encoding='utf-8'))
        cls.corrected = 'hull' in cls.deployed
        cls.published = {k: v for k, v in cls.deployed.items() if k != 'hull'}
        cls.screen = copy.deepcopy(cls.published)
        for row in cls.round6['replaced_in_screen']:
            key = row['pointer'].strip('/')
            before = json.loads((ROOT / row['before_file']).read_text(encoding='utf-8')) if 'before_file' in row else copy.deepcopy(row['before'])
            if 'before_file' in row:
                assert digest(before) == row['before_canonical_sha256'], 'the archived list is not the audited one'
            if cls.rescreened:
                cls.screen[key] = before
            else:
                assert cls.screen[key] == before, f'{key} differs from the record written before screening round 6'

    def test_screen_publication_does_not_release_a_new_model_or_rewrite_history(self):
        rest = copy.deepcopy({k:v for k,v in self.payload.items() if k != 'screen'})
        correction = json.loads((ROOT / 'results/validation/hurricane-display-cohort-correction.json').read_text(encoding='utf-8'))
        # A later model release is not the screen publication rewriting history. The release run of Hurricane 9.0 has its
        # own record, written before that run, of what it may change outside the screen block. Before the run the
        # recorded values are the published ones; after it, putting them back and taking the round-9 entries out again
        # must give the audited payload, so the release added a version and changed nothing else.
        release = json.loads((ROOT / 'results/validation/hurricane9-release-publication.json').read_text(encoding='utf-8'))
        self.assertEqual(release['audited_non_screen_canonical_sha256'], correction['after_non_screen_canonical_sha256'])
        released = self.payload['hurricane']['current'] != '4.0'
        def locate(pointer):
            parts, parent = pointer.strip('/').split('/'), rest
            for key in parts[:-1]: parent = parent[int(key)] if isinstance(parent, list) else parent[key]
            return parent, parts[-1]
        def restore(rows, done):
            for row in rows:
                parent, key = locate(row['pointer'])
                key = int(key) if isinstance(parent, list) else key
                if done: parent[key] = copy.deepcopy(row['before'])
                else: self.assertEqual(parent[key], row['before'])
        def take_out(rows, done):
            for row in rows:
                parent, key = locate(row['pointer'])
                where = row['where']
                kept = [item for item in parent[key] if not (item.get('round') == where['round'] if 'round' in where
                                                             else str(item.get('event', '')).startswith(where['event_prefix']))]
                self.assertEqual(len(parent[key]) - len(kept), 1 if done else 0)
                parent[key] = kept
        # The correction to the screening pools comes last and is undone first: one log entry.
        self.assertTrue(self.rescreened or not self.corrected)
        take_out(self.hull_record['appended'], self.corrected)
        # Screening round 6 comes after the release and is undone next: one line of the screen stage and one log entry.
        self.assertTrue(released or not self.rescreened)
        restore(self.round6['replaced_outside_screen'], self.rescreened)
        take_out(self.round6['appended'], self.rescreened)
        restore(release['replaced'], released)
        take_out(release['appended'], released)
        if released:
            self.assertEqual(self.payload['hurricane']['current'], release['release']['version'])
            entry = next(v for v in self.payload['hurricane']['versions'] if v['round'] == release['release']['round'])
            self.assertEqual((entry['version'], entry['status']), (release['release']['version'], 'adopted'))
            self.assertEqual(entry['temporal']['protocol']['sha256'], release['release']['protocol_sha256'])
        self.assertEqual(digest(rest), correction['after_non_screen_canonical_sha256'])
        self.assertEqual(correction['before_non_screen_canonical_sha256'], self.report['unchanged_non_screen_canonical_sha256'])
        # The original publication audit stays frozen. Reverse only the separately
        # documented display repair before comparing with its original payload hash.
        allowed = {'/hurricane/data', '/results', '/model_family', '/stages/7/detail'} | {f'/hurricane/versions/{i}/data' for i in range(5)}
        self.assertEqual({row['pointer'] for row in correction['corrections']}, allowed)
        for row in correction['corrections']:
            parts = row['pointer'].strip('/').split('/')
            parent = rest
            for key in parts[:-1]: parent = parent[int(key)] if isinstance(parent, list) else parent[key]
            key = parts[-1]
            self.assertEqual(parent[key], row['after'])
            if row['before_present']: parent[key] = row['before']
            else: del parent[key]
        self.assertEqual(digest(rest), self.report['unchanged_non_screen_canonical_sha256'])
        self.assertEqual(self.payload['hurricane']['current'], release['release']['version'] if released else '4.0')
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
        self.assertEqual(self.deployed['candidates'], storm)      # Storm's deployed list is the audited one in either state

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
        for screen in (self.screen, self.deployed):          # the audited list, and the deployed one where it lists them
            rows = {c['id']:c for c in screen['hurricane']['candidates']}
            for candidate_id in ('JVASP-165558', 'JVASP-165420'):
                if screen is self.deployed and candidate_id not in rows:
                    continue
                check = rows[candidate_id]['check']
                self.assertEqual(check, self.literature[candidate_id]['check_correction']['check'])
                self.assertIsNone(check['superconducts'])
                self.assertNotIn('below', check)
                self.assertIn('unknown', check['note'].lower())

    def test_numeric_predictions_ranks_and_phonons_remain_bound_to_reviewed_screen(self):
        self.assertEqual(digest(self.screen), self.report['deployed_screen_canonical_sha256'])
        self.assertEqual(self.round6['audited_screen_canonical_sha256'], self.report['deployed_screen_canonical_sha256'])
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

    def test_screening_round_6_replaces_hurricanes_list_only_and_binds_it_to_the_release_run(self):
        import hurricane9_release as R
        import hurricane9_screen as S
        record = self.round6['screening']
        self.assertEqual((record['protocol'], record['protocol_sha256'], record['round']), (S.PROTOCOL['name'], S.protocol_sha256(), S.ROUND))
        self.assertIn(S.protocol_sha256(), (ROOT / record['declaration']).read_text(encoding='utf-8'))
        self.assertEqual([row['pointer'] for row in self.round6['replaced_in_screen']], ['/models', '/hurricane'])
        self.assertEqual({k: v for k, v in self.published.items() if k not in ('models', 'hurricane')},
                         {k: v for k, v in self.screen.items() if k not in ('models', 'hurricane')})
        result = ROOT / f'results/screen_round{S.ROUND}.json'
        if not self.rescreened:
            self.assertEqual(self.published, self.screen)
            return
        block = self.deployed['hurricane']
        self.assertEqual(self.payload['hurricane']['current'], R.MODEL_VERSION)
        self.assertEqual((block['model'], block['round']), (f"Hurricane {R.MODEL_VERSION}", S.ROUND))
        self.assertEqual(self.deployed['models'], ['Radar 1.0', 'Storm 5.0', block['model']])
        out = json.loads(result.read_text(encoding='utf-8'))
        self.assertEqual((out['round'], out['smoke'], out['protocol']['sha256'], out['hurricane']), (S.ROUND, False, S.protocol_sha256(), block))
        self.assertEqual(out['protocol']['release_protocol_sha256'], R.protocol_sha256())
        with open(ROOT / 'results' / S.BACKGROUND, newline='', encoding='utf-8') as fh:
            released = {r['jid']: r for r in csv.DictReader(fh)}
        with open(ROOT / f'results/screen_round{S.ROUND}_hurricane.csv', newline='', encoding='utf-8') as fh:
            table = {r['jid']: r for r in csv.DictReader(fh)}
        self.assertEqual(set(table), {k for k, r in released.items() if r['sent'] == 'True'})
        self.assertEqual(block['pool']['n_sent'], len(table))
        self.assertEqual(block['pool']['n_screened'], len(released))
        self.assertEqual(block['not_known']['n'], sum(r['not_known'] == 'True' for r in table.values()))
        cands = block['candidates']
        self.assertEqual([c['rank'] for c in cands], list(range(1, len(cands) + 1)))
        self.assertLessEqual(len(cands), S.TOP_N)
        self.assertEqual(len({table[c['id']]['chemsys'] for c in cands}), len(cands))
        self.assertEqual(len(cands), min(S.TOP_N, len({r['chemsys'] for r in table.values() if r['not_known'] == 'False'})))
        for c in cands:
            # every published chance is the cross-fitted chance the release run committed for that compound
            self.assertEqual((released[c['id']]['sent'], released[c['id']]['not_known']), ('True', 'False'))
            self.assertAlmostEqual(c['p_sc'], float(released[c['id']]['p_sc']), delta=6e-4)
            self.assertAlmostEqual(c['p_sc'], float(table[c['id']]['p_sc']), delta=6e-4)
            self.assertLessEqual(c['novelty'], 1.0)
            self.assertTrue(0 <= c['p_sc'] <= 1 and c['lo'] <= c['tc_sc'] <= c['hi'])
            self.assertNotIn('p_lo', c)
        self.assertEqual({c['id'] for c in self.deployed['candidates']} - set(self.literature), set())

    def test_the_hull_correction_adds_one_field_and_changes_no_list(self):
        import screen_hull as H
        record = self.hull_record
        self.assertEqual([row['pointer'] for row in record['added_in_screen']], ['/hull'])
        self.assertEqual((record['step']['module'], record['step']['record'], record['step']['jarvis_rows_sha256']), (H.VERSION, H.RECORD, H.ROWS_SHA256))
        self.assertEqual(record['step']['result'], f'results/{H.RESULT}')
        self.assertEqual(record['appended'][0]['where']['event_prefix'], H.LOG_PREFIX)
        self.assertTrue((ROOT / record['step']['record']).is_file())
        result = ROOT / record['step']['result']
        storm, hurricane = self.deployed['candidates'], self.deployed['hurricane']['candidates']
        self.assertEqual((self.deployed['round'], len(storm)), (record['lists']['storm']['round'], record['lists']['storm']['candidates']))
        if self.rescreened:
            self.assertEqual((self.deployed['hurricane']['round'], self.deployed['hurricane']['model'], len(hurricane)),
                             tuple(record['lists']['hurricane'][k] for k in ('round', 'model', 'candidates')))
        log = [e for e in self.payload['log'] if str(e.get('event', '')).startswith(H.LOG_PREFIX)]
        if not self.corrected:
            self.assertFalse(result.exists())
            self.assertEqual(log, [])
            return
        hull = self.deployed['hull']
        self.assertEqual(list(self.deployed)[-1], 'hull')            # added after everything the block held
        out = json.loads(result.read_text(encoding='utf-8'))
        self.assertEqual((out['module'], out['smoke'], out['screen']), (H.VERSION, False, {'hull': hull}))
        self.assertEqual(out['file']['rows_sha256'], H.ROWS_SHA256)
        self.assertLessEqual(out['against_pymatgen']['largest_difference_eV_per_atom'], H.AGREE)
        self.assertEqual(out['against_pymatgen']['published_candidates_compared'], len(storm) + len(hurricane))
        self.assertEqual((hull['about'], hull['record']), (H.ABOUT, H.RECORD))
        self.assertEqual({k: out['file'][k] for k in hull['file'] if k != 'source'}, {k: v for k, v in hull['file'].items() if k != 'source'})
        rows = {(row['list'], row['id']): row for row in out['candidates']}
        self.assertEqual(len(rows), len(storm) + len(hurricane))
        for name, block, cands in (('storm', self.deployed, storm), ('hurricane', self.deployed['hurricane'], hurricane)):
            rec = hull[name]
            d = rec['distance_eV_per_atom']
            self.assertEqual(set(d), {c['id'] for c in cands})
            self.assertEqual((rec['round'], rec['date'], rec['listed'], rec['found']), (block['round'], block['date'], len(cands), len(cands)))
            self.assertEqual((rec['within_50_meV'], rec['beyond_50_meV'], rec['beyond_200_meV']),
                             (sum(v <= 0.05 for v in d.values()), sum(v > 0.05 for v in d.values()), sum(v > 0.2 for v in d.values())))
            for c in cands:
                row = rows[(name, c['id'])]
                self.assertEqual((row['rank'], row['formula'], row['published_ehull'], row['distance_eV_per_atom']), (c['rank'], c['formula'], c['ehull'], d[c['id']]))
                self.assertTrue(0 <= d[c['id']] == round(d[c['id']], 4))
                self.assertLessEqual(row['ehull_field'], 0.05)       # the field is what the pool was selected with
        self.assertEqual([e['event'] for e in log], [H.message(hull)])


if __name__ == '__main__':
    unittest.main()
