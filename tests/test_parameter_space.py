"""Synthetic test fixtures only; these curves are not scientific measurements."""
import contextlib
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ml import feedback as F
from ml import parameter_space as P
from tests.test_feedback import normal, conditions


AS_OF = '2025-02-03T00:00:00Z'
GROUP = {'sample_id': 'synthetic-sample-A', 'phase': 'synthetic-phase-A',
         'quantity': 'resistivity', 'unit': 'microohm cm'}


class ParameterSpaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'synthetic-ledger.jsonl'
        self.now = datetime(2025, 2, 2, tzinfo=timezone.utc)
        self.ledger = F.FeedbackLedger(self.path, clock=lambda: self.now)
        self.sequence = 0

    def add(self, temperature, response, *, pressure=0, doping=0, strain=0, field=0, sample='synthetic-sample-A', **changes):
        self.sequence += 1
        payload = normal(value=float(response), statement=f'Synthetic fixture #{self.sequence}, not scientific evidence',
                         coordinates=dict(temperature_k=temperature, pressure_gpa=pressure, doping_fraction=doping,
                                          strain=strain, magnetic_field_t=field),
                         conditions=conditions(sample_id=sample, pressure_GPa=pressure, field_T=field),
                         feature_window=dict(kind='absolute_predeclared', min_K=10, max_K=300,
                                             defined_at='2024-01-01T00:00:00Z'))
        payload.update(copy.deepcopy(changes))
        return self.ledger.append_observation(payload)

    def fit(self, **changes):
        request = dict(as_of=AS_OF, group=GROUP, axes=['temperature_k'], bounds={'temperature_k': [80, 220]})
        request.update(changes)
        return P.fit_response(self.ledger.read(), **request)

    def line(self, *, scale=1, unit='microohm cm'):
        for temperature in [100, 120, 140, 160, 180, 200]:
            self.add(temperature, scale*(8+np.sin((temperature-100)/30)), unit=unit)
        return self.fit(group=dict(GROUP, unit=unit))

    def test_synthetic_1d_recovery_sources_and_observed_range_flags(self):
        fit = self.line()
        self.assertEqual(fit.status, 'ok')
        result = P.predict(fit, [{'temperature_k': 130}, {'temperature_k': 170}, {'temperature_k': 210}])
        for row, temperature in zip(result['rows'][:2], [130, 170]):
            self.assertAlmostEqual(row['predicted_response'], 8+np.sin((temperature-100)/30), delta=.1)
            self.assertGreaterEqual(row['posterior_std'], 0)
            self.assertFalse(row['extrapolates_observed_range'])
        self.assertTrue(result['rows'][2]['extrapolates_observed_range'])
        self.assertTrue(result['rows'][2]['outside_observed_convex_hull'])
        self.assertEqual(len(fit.audit['training_event_hashes']), 6)
        self.assertTrue(all(len(value) == 64 for value in fit.audit['training_event_hashes']))
        self.assertIn('sources', fit.audit['training_points'][0])
        self.assertIn('does not demonstrate movement toward superconductivity', result['limitation'])

    def test_synthetic_2d_response_surface_and_nonrectangular_support(self):
        for temperature in [100, 140, 180]:
            for pressure in [0, 1, 2]:
                self.add(temperature, 20+.1*(temperature-100)+2*pressure, pressure=pressure)
        fit = self.fit(axes=['temperature_k', 'pressure_gpa'], bounds={'temperature_k': [80, 220], 'pressure_gpa': [0, 3]})
        self.assertEqual(fit.status, 'ok')
        row = P.predict(fit, [{'temperature_k': 135, 'pressure_gpa': .75}])['rows'][0]
        self.assertAlmostEqual(row['predicted_response'], 25, delta=.7)
        self.assertEqual(fit.audit['centered_axis_rank'], 2)
        self.assertFalse(row['outside_observed_convex_hull'])
        # A triangular measured region has unmeasured corners even inside its
        # separate per-axis ranges; the model must disclose that extrapolation.
        extra = F.FeedbackLedger(Path(self.directory.name)/'synthetic-triangle.jsonl', clock=lambda: self.now)
        original = self.ledger
        self.ledger = extra
        for temperature, pressure in [(100,0),(140,0),(180,0),(100,1),(100,2),(120,.5)]:
            self.add(temperature, 20+.1*(temperature-100)+2*pressure, pressure=pressure)
        triangle = self.fit(axes=['temperature_k', 'pressure_gpa'], bounds={'temperature_k': [80,220], 'pressure_gpa':[0,3]})
        row = P.predict(triangle, [{'temperature_k':175, 'pressure_gpa':1.8}])['rows'][0]
        self.assertFalse(row['extrapolates_observed_range'])
        self.assertTrue(row['outside_observed_convex_hull'])
        self.ledger = original

    def test_insufficient_unique_points_and_collinear_axes_do_not_fabricate_curves(self):
        for repeat in range(3):
            self.add(100, 8+.1*repeat)
            self.add(200, 9+.1*repeat)
        fit = self.fit()
        self.assertEqual(fit.status, 'insufficient_data')
        self.assertEqual(fit.audit['unique_points'], 2)
        self.assertNotIn('predicted_response', P.predict(fit, [{'temperature_k':150}])['rows'][0])
        for temperature in [110, 130, 150, 170, 190]:
            self.add(temperature, temperature/100, pressure=(temperature-100)/50, unit='other exact unit')
        fit = self.fit(group=dict(GROUP, unit='other exact unit'), axes=['temperature_k','pressure_gpa'],
                       bounds={'temperature_k':[80,220], 'pressure_gpa':[0,3]})
        self.assertEqual(fit.status, 'insufficient_data')
        self.assertEqual(fit.audit['centered_axis_rank'], 1)

    def test_unknown_axes_remain_unknown_and_queries_are_bounded(self):
        for temperature in [100,120,140,160]:
            coordinate = dict(temperature_k=temperature, pressure_gpa=0, doping_fraction=None, strain=0, magnetic_field_t=0)
            self.add(temperature, 4, coordinates=coordinate)
        empty = self.fit()
        self.assertEqual(empty.status, 'insufficient_data')
        self.assertEqual(empty.audit['selected_measurements'], 0)
        self.assertEqual(len(empty.audit['excluded_by_eligibility']), 4)
        fit = self.line()
        result = P.predict(fit, [{}, {'temperature_k':None}, {'temperature_k':79},
                                 {'temperature_k':150, 'magnetic_field_t':1}, {'temperature_k':150,'tc_K':50}])
        self.assertEqual([row['status'] for row in result['rows']],
                         ['missing_axis','missing_axis','outside_bounds','outside_fixed_context','invalid_coordinates'])
        self.assertTrue(all('predicted_response' not in row for row in result['rows']))

    def test_series_must_be_explicit_and_phase_units_samples_never_silently_merge(self):
        for temperature in [100,120,140]:
            self.add(temperature, temperature/100)
            self.add(temperature, temperature, sample='synthetic-sample-B')
            self.add(temperature, temperature, unit='ohm m')
        self.assertEqual(self.fit().status, 'insufficient_data')
        self.assertEqual(self.fit(group=dict(GROUP, unit='ohm m')).status, 'insufficient_data')
        for index, temperature in enumerate([100,120,140,160,180]):
            self.add(temperature, temperature/100, sample='series-A' if index<3 else 'series-B',
                     material_id='fixture-series-A' if index<3 else 'fixture-series-B', series_id='explicit-synthetic-series')
        series = dict(series_id='explicit-synthetic-series', phase=GROUP['phase'], quantity=GROUP['quantity'], unit=GROUP['unit'])
        fit = self.fit(group=series)
        self.assertEqual(fit.status, 'ok')
        self.assertEqual(fit.audit['sample_ids'], ['series-A','series-B'])
        wrong_phase = self.fit(group=dict(series, phase='different-phase'))
        self.assertEqual(wrong_phase.status, 'insufficient_data')

    def test_unselected_axes_require_constant_context_or_explicit_slice(self):
        for temperature in [100,120,140,160,180]:
            self.add(temperature, temperature/100, pressure=0)
            self.add(temperature, temperature/100+1, pressure=1)
        fit = self.fit()
        self.assertEqual(fit.status, 'insufficient_data')
        self.assertIn('unselected pressure_gpa varies', fit.audit['reason'])
        fit = self.fit(fixed_coordinates={'pressure_gpa':0})
        self.assertEqual(fit.status, 'ok')
        self.assertEqual(len(fit.audit['excluded_by_slice']), 5)
        self.assertEqual(fit.audit['fixed_coordinates']['pressure_gpa'], 0)

    def test_method_and_sample_form_conflicts_require_adjudication(self):
        self.line()
        self.add(150, 8.5, conditions=conditions(method='other-resistivity-method'))
        self.assertEqual(self.fit().status, 'insufficient_data')
        self.assertIn('measurement methods or sample forms differ', self.fit().audit['reason'])

    def test_time_cutoff_normal_eligibility_and_sc_input_leakage(self):
        self.line()
        self.now = datetime(2025,3,2,tzinfo=timezone.utc)
        future = self.add(150, 999, observed_at='2025-03-01T00:00:00Z')
        fit = self.fit()
        self.assertEqual(fit.status, 'ok')
        self.assertNotIn(future['hash'], fit.audit['training_event_hashes'])
        self.assertTrue(any('measurement was not frozen by feature cutoff' in row['reasons'] for row in fit.audit['excluded_by_eligibility']))
        relative = self.add(155, 4, feature_window=dict(kind='tc_relative', min_K=10,max_K=300,defined_at='2024-01-01T00:00:00Z'))
        fit = self.fit(as_of='2025-03-03T00:00:00Z')
        self.assertNotIn(relative['hash'], fit.audit['training_event_hashes'])
        self.assertTrue(any('Tc-relative' in ' '.join(row['reasons']) for row in fit.audit['excluded_by_eligibility']))
        for quantity in ['tc_K','critical_temperature','critical_temperature_K','Tc_onset_K','shielding_fraction','upper_critical_field']:
            with self.subTest(quantity=quantity), self.assertRaisesRegex(ValueError, 'superconductivity criteria'):
                self.fit(group=dict(GROUP,quantity=quantity))
        with self.assertRaises(ValueError):
            self.fit(axes=['tc_K'],bounds={'tc_K':[1,100]})

    def test_response_unit_scaling_preserves_normalized_uncertainty_and_acquisition(self):
        first = self.line()
        second = self.line(scale=1000,unit='other-unit-multiplicative-fixture')
        queries = [{'temperature_k':110},{'temperature_k':170}]
        a, b = P.predict(first,queries)['rows'], P.predict(second,queries)['rows']
        for left,right in zip(a,b):
            self.assertAlmostEqual(right['predicted_response'],1000*left['predicted_response'],places=7)
            self.assertAlmostEqual(right['posterior_std'],1000*left['posterior_std'],places=7)
            self.assertAlmostEqual(right['normalized_std'],left['normalized_std'],places=12)
        candidates=[{'coordinates':row,'cost':1} for row in queries]
        left=P.suggest_next_points(first,candidates,budget=1,cost_unit='instrument-hour')['selected'][0]
        right=P.suggest_next_points(second,candidates,budget=1,cost_unit='instrument-hour')['selected'][0]
        self.assertEqual(left['index'],right['index'])
        self.assertAlmostEqual(left['acquisition_score'],right['acquisition_score'],places=12)

    def test_duplicate_candidates_cost_units_budget_and_existing_points(self):
        fit=self.line()
        candidates=[{'candidate_id':'costly','coordinates':{'temperature_k':110},'cost':100},
                    {'candidate_id':'same-expensive','coordinates':{'temperature_k':170},'cost':1},
                    {'candidate_id':'same-cheap','coordinates':{'temperature_k':170},'cost':.5},
                    {'coordinates':{'temperature_k':100},'cost':.1},
                    {'coordinates':{'temperature_k':150}},
                    {'coordinates':{'temperature_k':150},'cost':0},
                    {'coordinates':{'temperature_k':150},'cost':.1,'cost_unit':'dollars'},
                    {'coordinates':{'temperature_k':300},'cost':.1}]
        report=P.suggest_next_points(fit,candidates,budget=.5,cost_unit='instrument-hour',max_points=3)
        self.assertEqual([row['candidate_id'] for row in report['selected']],['same-cheap'])
        self.assertEqual(report['spent'],.5)
        reasons={row['reason'] for row in report['excluded']}
        self.assertTrue({'duplicate_candidate','already_observed_point','missing_or_invalid_external_cost','incompatible_cost_unit','outside_bounds'} <= reasons)
        self.assertEqual(report['experiments_executed'],0)
        self.assertTrue(report['training_event_hashes'])
        with self.assertRaises(ValueError):
            P.suggest_next_points(fit,[],budget=1,cost_unit='')

    def test_replicate_provenance_not_extra_unique_points_and_point_budget(self):
        fit=self.line()
        self.add(100,8.2)
        repeated=self.fit()
        self.assertEqual(repeated.status,'ok')
        self.assertEqual(repeated.audit['unique_points'],6)
        point=repeated.audit['training_points'][0]
        self.assertEqual(point['replicates'],2)
        self.assertAlmostEqual(point['mean'],8.1)
        self.assertGreater(point['replicate_variance'],0)
        self.assertEqual(len(point['event_hashes']),2)
        self.assertEqual(self.fit(max_points=5).status,'budget_exceeded')
        json.dumps(repeated.audit,allow_nan=False)

    def test_empty_read_only_cli_does_not_create_ledger_or_pretend_to_fit(self):
        missing=Path(self.directory.name)/'uncreated'/'ledger.jsonl'
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            status=P.main(['--audit','--ledger',str(missing),'--as-of',AS_OF])
        report=json.loads(output.getvalue())
        self.assertEqual(status,0)
        self.assertFalse(report['exists'])
        self.assertEqual(report['ledger_events'],0)
        self.assertEqual(report['eligible_normal_measurements'],0)
        self.assertEqual(report['groups'],[])
        self.assertEqual(report['models_fitted'],0)
        self.assertFalse(missing.parent.exists())
        empty=P.fit_response([],as_of=AS_OF,group=GROUP,axes=['temperature_k'],bounds={'temperature_k':[80,220]})
        self.assertEqual(empty.status,'insufficient_data')
        self.assertEqual(P.suggest_next_points(empty,[],budget=1,cost_unit='hour')['selected'],[])


if __name__=='__main__':
    unittest.main()
