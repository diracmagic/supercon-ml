import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import storm6 as S6
import storm8 as S


def optimade_page(entries, next_url=None):
    data = [{"id": i, "type": "structures", "attributes": a} for i, a in entries]
    return json.dumps({"data": data, "links": {"next": next_url}, "meta": {"api_version": "1.1.0"}}).encode()


def atoms(elements, edge=2.0):
    n = len(elements)
    return {"lattice_mat": (np.diag([edge, edge * 1.1, edge * 1.3]) * n).tolist(), "elements": list(elements),
            "coords": [[k / n, (k * .37) % 1, (k * .61) % 1] for k in range(n)], "cartesian": False}


def record(structure, dos=1.0, gap=0.0, *, rotate=False, xc=S.EXPECTED_XC, magnetization=0.0):
    L, X = np.asarray(structure["lattice_mat"], float), np.asarray(structure["coords"], float)
    C = X @ L
    if rotate:
        c, s = np.cos(.7), np.sin(.7)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        L, C = L @ R.T, C @ R.T
    elements = structure["elements"]
    return {"lattice_vectors": L.tolist(), "cartesian_site_positions": C.tolist(), "species_at_sites": list(elements),
            "species": [{"name": e, "chemical_symbols": [e], "concentration": [1.0]} for e in sorted(set(elements))],
            "nsites": len(elements), "chemical_formula_reduced": "unused", "_alexandria_xc_functional": xc,
            "_alexandria_dos_ef": dos, "_alexandria_band_gap": gap, "_alexandria_magnetization": magnetization,
            "last_modified": "2023-11-16T07:57:59Z"}


class FakeOptimade:
    """Answers OPTIMADE filters from a dictionary; IDs absent from it are simply not returned."""
    def __init__(self, records, split_pages=False):
        self.records, self.split_pages, self.urls = records, split_pages, []

    def __call__(self, url):
        self.urls.append(url)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "page" in query:
            ids = json.loads(query["page"][0])
            return optimade_page([(i, self.records[i]) for i in ids if i in self.records])
        ids = [part.split('"')[1] for part in query["filter"][0].split(" OR ")]
        found = [i for i in ids if i in self.records]
        if self.split_pages and len(found) > 1:
            rest = S.OPTIMADE_URL + "?" + urllib.parse.urlencode({"page": json.dumps(found[1:])})
            return optimade_page([(found[0], self.records[found[0]])], rest)
        return optimade_page([(i, self.records[i]) for i in found])


class Storm8Tests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(81)
        self.D, self.G = rng.normal(size=(200, 5)), rng.normal(size=(200, 19))
        self.E = np.column_stack([np.exp(rng.normal(size=200)), rng.random(200), np.zeros(200)])
        self.groups = np.repeat([f"system-{i}" for i in range(100)], 2)
        self.y = np.expm1(.4 + .1 * np.tanh(self.D[:, 0]) + .05 * self.E[:, 0])
        self.train, self.test = np.arange(160), np.arange(160, 200)

    def forecast(self, design, y=None, E=None):
        E = self.E if E is None else E
        y = self.y if y is None else y
        tr, te = self.train, self.test
        return S.forecast(design, self.D[tr], self.G[tr], E[tr], y[tr], self.D[te], self.G[te], E[te], fold=0, params=S.SMOKE_PARAMS)[0]

    def test_p0_is_exactly_storm6_r2(self):
        reference = S6.forecast("R2", self.D[self.train], self.G[self.train], {"tc": self.y[self.train]},
                                self.D[self.test], self.G[self.test], seed=S6.SEED, params=S.SMOKE_PARAMS)["tc"]
        np.testing.assert_array_equal(self.forecast("P0"), reference)

    def test_all_missing_electronic_inputs_reduce_p1_to_p0(self):
        self.assertFalse(np.array_equal(self.forecast("P1"), self.forecast("P0")))  # the P1 path is exercised here
        np.testing.assert_array_equal(self.forecast("P1", E=np.full_like(self.E, np.nan)), self.forecast("P0"))

    def test_test_labels_cannot_change_forecasts(self):
        altered = self.y.copy()
        altered[self.test] = 1e4
        for design in S.DESIGNS:
            np.testing.assert_array_equal(self.forecast(design), self.forecast(design, y=altered))

    def test_structure_check_accepts_only_the_same_structure(self):
        base = atoms(["Nb", "Nb", "Sn", "V"])
        self.assertEqual(S.same_structure(base, record(base)), "ok")
        self.assertEqual(S.same_structure(base, record(base, rotate=True)), "ok")
        shuffled = record(base)
        order = [2, 0, 3, 1]
        for key in ("cartesian_site_positions", "species_at_sites"):
            shuffled[key] = [shuffled[key][i] for i in order]
        self.assertEqual(S.same_structure(base, shuffled), "ok")
        swapped = record(base)
        swapped["lattice_vectors"] = [swapped["lattice_vectors"][i] for i in (1, 2, 0)]
        self.assertEqual(S.same_structure(base, swapped), "ok")
        cartesian = dict(base, coords=(np.asarray(base["coords"]) @ np.asarray(base["lattice_mat"])).tolist(), cartesian=True)
        self.assertEqual(S.same_structure(cartesian, record(base)), "ok")
        shifted = dict(base, coords=((np.asarray(base["coords"]) + [.25, .5, .125]) % 1).tolist())
        self.assertEqual(S.same_structure(shifted, record(base)), "ok")
        relaxed = dict(base, lattice_mat=(np.asarray(base["lattice_mat"]) * .98).tolist())
        self.assertEqual(S.same_structure(base, record(relaxed)), "mismatch_cell")
        moved = record(base)
        moved["cartesian_site_positions"][1][0] += .01
        self.assertEqual(S.same_structure(base, moved), "mismatch_sites")
        self.assertEqual(S.same_structure(base, record(atoms(["Nb", "Nb", "Sn", "Ti"]))), "mismatch_species")
        self.assertEqual(S.same_structure(base, record(base, xc="gga_x_pbesol + gga_c_pbesol")), "mismatch_functional")
        broken = record(base)
        del broken["species"]
        self.assertEqual(S.same_structure(base, broken), "mismatch_unreadable")

    def test_electronic_inputs_normalise_and_flag_every_row(self):
        a, b = atoms(["Al", "V", "V", "V"]), atoms(["Nb"])
        volume = abs(np.linalg.det(np.asarray(a["lattice_mat"])))
        records = {"a": record(a, 9.0, .1, magnetization=.3), "b": record(atoms(["Nb", "Ti"]), 1.0),
                   "c": record(b, None), "e": record(b, -.1, .5)}
        E, status, diagnostics = S.electronic_inputs(["a", "b", "c", "d", "e"], [a, b, b, b, b], records)
        np.testing.assert_allclose(E[0], [9.0 / 4, 9.0 / volume, 0.1])
        self.assertEqual(status, ["ok", "mismatch_species", "partial", "not_returned", "partial"])
        self.assertTrue(np.isnan(E[1]).all() and np.isnan(E[2, :2]).all() and np.isnan(E[3]).all())
        np.testing.assert_allclose(E[4], [np.nan, np.nan, .5])
        self.assertEqual(diagnostics, {"negative_dos_rows": 1, "magnetization_recorded_rows": 3,
                                       "abs_magnetization_ge_0p1_muB_per_cell": 1})

    def test_fetch_batches_pages_snapshots_and_reuses_cache(self):
        ids = [f"agm{i:09d}" for i in range(60)]
        records = {i: record(atoms(["Nb"]), 1.0 + k) for k, i in enumerate(ids) if k % 7}
        fake = FakeOptimade(records, split_pages=True)
        with tempfile.TemporaryDirectory() as tmp:
            got, manifest, bodies = S.fetch_electronic(ids, tmp, get=fake, pause=0)
            self.assertEqual(set(got), set(records))
            self.assertEqual(len(manifest["pages"]), len(bodies))
            self.assertGreater(len(fake.urls), 3)  # three batches, each with a second page
            for page in manifest["pages"]:
                self.assertTrue((Path(tmp) / "raw" / f"{page['sha256']}.json").is_file())

            def refuse(url):
                raise AssertionError("cached responses must be reused without network access")
            again, cached, _ = S.fetch_electronic(ids, tmp, get=refuse, offline=True)
            self.assertEqual(again, got)
            self.assertTrue(cached["reused_cache"])
            raw = Path(tmp) / "raw" / f"{manifest['pages'][0]['sha256']}.json"
            raw.write_bytes(raw.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "changed"):
                S.fetch_electronic(ids, tmp, get=refuse, offline=True)

    def test_fetch_rejects_filter_injection_and_unrequested_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unsafe"):
                S.fetch_electronic(['agm1" OR id="x'], tmp, get=FakeOptimade({}))
            with self.assertRaisesRegex(ValueError, "offline"):
                S.fetch_electronic(["agm1"], tmp, offline=True)
            with self.assertRaisesRegex(ValueError, "unrequested"):
                S.fetch_electronic(["agm1"], tmp, get=lambda url: optimade_page([("agm2", record(atoms(["Nb"])))]), pause=0)

    def test_decision_rule(self):
        def paired(delta, low, high):
            return {"delta_mae_k_new_minus_reference": delta, "percentile_95_interval_k": [low, high]}

        def verdict(delta=-.05, low=-.08, high=-.02, coverage=.95, plus=-.04, minus=-.05):
            return S.decision(paired(delta, low, high), coverage=coverage, shifted_deltas={"plus_1ulp": plus, "minus_1ulp": minus})
        met = verdict()
        self.assertTrue(met["prespecified_gain_rule_met"])
        self.assertEqual(met["conclusion"], "prespecified gain rule met")
        self.assertFalse(met["adopted"])
        self.assertFalse(verdict(delta=-.02, low=-.04, high=-.01)["prespecified_gain_rule_met"])  # point effect too small
        self.assertFalse(verdict(high=.01)["prespecified_gain_rule_met"])  # interval includes no improvement
        self.assertFalse(verdict(plus=-.02)["prespecified_gain_rule_met"])  # not robust to a 1-ulp refit
        below = verdict(coverage=.85)
        self.assertFalse(below["prespecified_gain_rule_met"])
        self.assertIn("no conclusion", below["conclusion"])
        self.assertEqual(below["conditions"], {"coverage_floor_met": False, "main_rule_met": True, "robust_under_1ulp_refits": True})
        self.assertFalse(S.decision(paired(-.05, -.08, -.02), coverage=1.0, shifted_deltas={})["prespecified_gain_rule_met"])

    def test_array_hash_ignores_nan_payload_and_memory_order(self):
        X = np.arange(6.).reshape(2, 3)
        X[0, 1] = np.nan
        Y = np.asfortranarray(X.copy())
        Y[0, 1] = -np.nan
        self.assertEqual(S.array_sha256(X), S.array_sha256(Y))
        self.assertNotEqual(S.array_sha256(X), S.array_sha256(np.nextafter(X, np.inf)))

    def test_protocol_is_deterministic_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, digest = S.freeze_protocol(tmp)
            second, again = S.freeze_protocol(tmp)
            self.assertEqual((first, digest), (second, again))
            self.assertIn("ml/requirements.txt", first["source_sha256_lf"])
            with self.assertRaisesRegex(ValueError, "Refusing"):
                S.freeze_protocol(tmp, smoke=True)

    def test_synthetic_smoke_run_completes_and_reports_both_designs(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = S.run(smoke=True, output_dir=Path(tmp) / "run")
            self.assertEqual(report["status"], "completed")
            self.assertFalse(report["adopted"])
            self.assertEqual(set(report["designs"]), {"P0", "P1"})
            self.assertIn("overall", report["paired_P1_minus_P0"])
            self.assertIn("prespecified_gain_rule_met", report["decision"])
            self.assertEqual(set(report["decision"]["conditions"]), {"coverage_floor_met", "main_rule_met", "robust_under_1ulp_refits"})
            self.assertEqual(set(report["refits_under_1ulp_shifts"]), {"plus_1ulp", "minus_1ulp"})
            for shift in report["refits_under_1ulp_shifts"].values():
                self.assertEqual(set(shift), {"P0", "P1", "delta_mae_k_P1_minus_P0"})
                self.assertAlmostEqual(shift["delta_mae_k_P1_minus_P0"], shift["P1"]["mae_k"] - shift["P0"]["mae_k"])
            self.assertEqual(set(report["input_reproduction"]["bitwise_equal_to_storm7"]), {"D", "geometry", "ids"})
            self.assertTrue((Path(tmp) / "run" / "artifact-manifest.json").is_file())
            with self.assertRaisesRegex(ValueError, "non-overwriting"):
                S.run(smoke=True, output_dir=Path(tmp) / "run")


if __name__ == "__main__":
    unittest.main()
