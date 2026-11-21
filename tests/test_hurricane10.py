"""Hurricane round 10: the protocol, the variants of datasheet parents, the rule, and a run on invented rows."""
import contextlib
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
import hurricane10 as T  # noqa: E402


def comp(formula):
    return T.D.parse_formula(formula)


class ProtocolTests(unittest.TestCase):
    def test_the_protocol_binds_the_previous_release_and_the_pool_and_states_the_rule(self):
        p = T.PROTOCOL
        self.assertEqual(T.protocol_sha256(), hashlib.sha256(T.protocol_text().encode('utf-8')).hexdigest())
        self.assertEqual(p['previous']['release_protocol_sha256'], T.R.protocol_sha256())
        self.assertIn(T.S7.protocol_sha256(), p['background']['pool'])
        self.assertEqual((p['tests']['factor'], p['tests']['margin']), (0.5, 0.05))
        self.assertEqual(p['tests']['A'], T.TEST_A)
        self.assertEqual(p['tests']['B'], T.TEST_B)
        self.assertIn('progress/progress.json', p['not_written'])
        # the guard's numbers are 9.0's: the module uses hurricane9_release's guard and windows, not copies of them
        self.assertEqual((T.R.WEIGHT, T.R.RADIUS, T.R.ABSTAIN), (0.3, 1.0, 1.0))

    def test_the_run_refuses_to_read_data_without_the_declared_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / 'declaration.md'
            empty.write_text('no hash here\n', encoding='utf-8')
            with mock.patch.object(T, 'DECLARATION', empty), mock.patch.object(T.D, 'fetch', side_effect=AssertionError('data read')):
                with self.assertRaises(SystemExit) as caught:
                    T.run(smoke=False, output_dir=Path(tmp))
            self.assertIn('refusing to read any data', str(caught.exception))


class VariantTests(unittest.TestCase):
    def test_substituted_variants_reach_the_parent_of_their_host(self):
        ybco = T.parent_key(comp('YBa2Cu3O7'))
        self.assertEqual(ybco, 'Ba2Cu3O7Y')
        self.assertEqual(T.parent_key(comp('Ba1.888Na0.094YCu3Cl0.057O6.961')), ybco)   # rank 1 of round 7's list
        self.assertEqual(T.parent_key(comp('YBa2Cu3O6.5')), ybco)
        self.assertEqual(T.parent_key(comp('La1.85Sr0.15CuO4')), T.parent_key(comp('La2CuO4')))
        self.assertEqual(T.parent_key(comp('BaFe1.8Co0.2As2')), T.parent_key(comp('BaFe2As2')))
        # a compound of its own kind keeps its own parent
        self.assertEqual(T.parent_key(comp('YCu3Se2ClO8')), 'ClCu3O8Se2Y')
        self.assertIsNone(T.parent_key({'Cu': 0.2, 'O': 1.0}))          # every cation below the dopant threshold: unresolved

    def test_the_datasheet_parents_hold_claims_and_coefficient_parents(self):
        obs = [{'parent': 'CuLa2O4', 'composition': comp('La1.85Sr0.15CuO4'), 'oxygen': {'status': 'numeric'}},
               {'parent': 'unresolved', 'composition': comp('YBa2Cu3O6.9'), 'oxygen': {'status': 'numeric'}},
               {'parent': 'ambiguous: A | B', 'composition': {}, 'oxygen': {'status': 'none'}},
               {'parent': 'Ba2Cu3O7Y', 'composition': comp('YBa2Cu3O7'), 'oxygen': {'status': 'unknown'}}]
        self.assertEqual(T.datasheet_parents(obs), {'CuLa2O4', 'Ba2Cu3O7Y'})

    def test_the_pool_is_split_into_background_and_variants(self):
        pool = [{'comp': comp('Ba1.888Na0.094YCu3Cl0.057O6.961'), 'db': 'COD', 'id': '1526964'},
                {'comp': comp('YCu3Se2ClO8'), 'db': 'COD', 'id': '1'},
                {'comp': {'Cu': 0.2, 'O': 1.0}, 'db': 'COD', 'id': '2'}]
        kept, variants = T.split_pool(pool, {'Ba2Cu3O7Y'})
        self.assertEqual([r['id'] for r in kept], ['1', '2'])
        self.assertEqual([(r['id'], r['variant_of']) for r in variants], [('1526964', 'Ba2Cu3O7Y')])
        self.assertNotIn('variant_of', pool[0])                           # the pool's records are not changed


class RuleTests(unittest.TestCase):
    def test_the_rule(self):
        self.assertEqual(T.decide(0.10, 0.21, 0.70, 0.73), {'A': True, 'B': True, 'adopted': True})
        self.assertEqual(T.decide(0.105, 0.21, 0.70, 0.73), {'A': True, 'B': True, 'adopted': True})     # exactly half
        self.assertEqual(T.decide(0.11, 0.21, 0.73, 0.73), {'A': False, 'B': True, 'adopted': False})
        self.assertEqual(T.decide(0.05, 0.21, 0.67, 0.73), {'A': True, 'B': False, 'adopted': False})
        self.assertEqual(T.decide(0.0, 0.0, 0.73, 0.73)['A'], False)                                       # nothing to halve
        self.assertEqual(T.decide(None, 0.2, 0.73, 0.73)['adopted'], False)
        self.assertEqual(T.decide(0.05, 0.2, None, 0.73)['B'], False)


class SmokeRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.progress_before = T.P.PROGRESS.read_bytes()
        cls.stdout = io.StringIO()
        with contextlib.redirect_stdout(cls.stdout), contextlib.redirect_stderr(io.StringIO()):
            cls.out = T.run(smoke=True, output_dir=Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_run_writes_its_result_and_table_and_nothing_else(self):
        out = self.out
        self.assertTrue(out['smoke'])
        written = json.loads((Path(self.tmp.name) / T.RESULT).read_text(encoding='utf-8'))
        self.assertEqual(written['protocol']['sha256'], T.protocol_sha256())
        self.assertEqual(written['adopted'], written['result']['rule']['adopted'])
        self.assertEqual(T.P.PROGRESS.read_bytes(), self.progress_before)
        table = Path(self.tmp.name) / T.TABLE
        self.assertEqual(out['files']['pool_table_sha256'], hashlib.sha256(table.read_bytes()).hexdigest())
        with gzip.open(table, 'rt', encoding='utf-8') as fh:
            rows = list(csv.DictReader(fh))
        pool = out['result']['pool']
        self.assertEqual(len(rows), pool['compounds'])
        self.assertEqual(sum(1 for r in rows if r['variant_of']), out['result']['variants']['n'])
        self.assertEqual(pool['background'] + out['result']['variants']['n'], pool['compounds'])

    def test_the_rule_reads_the_numbers_it_reports(self):
        r = self.out['result']
        expected = T.decide(r['A']['new'], r['A']['previous'], r['B']['new'], r['B']['previous'])
        self.assertEqual(r['rule'], expected)
        self.assertEqual(r['B']['new'], r['family_windows']['new']['found'])
        self.assertEqual(r['B']['previous'], r['family_windows']['previous']['found'])
        self.assertLessEqual(r['A']['alarms_new'], r['A']['compounds'])
        # the Tc and the distance to the training data are 9.0's in both designs
        self.assertEqual(r['checks']['regressor_unchanged_largest_difference_k'], 0.0)
        self.assertEqual(r['checks']['inside_differs_for'], 0)

    def test_the_printed_block_is_checked_by_its_hash(self):
        lines = self.stdout.getvalue().splitlines()
        body = ''.join(line.split('|', 2)[2] for line in lines if line.startswith('h10|'))
        end = next(line for line in lines if line.startswith('=== hurricane10 end'))
        self.assertIn(hashlib.sha256(body.encode('utf-8')).hexdigest(), end)
        shown = json.loads(body)
        self.assertEqual(shown['result']['rule'], self.out['result']['rule'])
        self.assertLessEqual(max(len(v) for v in shown['top'].values()), T.TOP)


if __name__ == '__main__':
    unittest.main()
