"""Evidence coverage and unknown outcomes must survive ranking/UI integration."""
import copy
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
from literature_audit import attach_audits, compact_record, load_audit


class LiteratureAuditTests(unittest.TestCase):
    def test_every_published_candidate_has_an_actual_search_record(self):
        records, index = load_audit()
        screen = json.loads((ROOT / "progress" / "progress.json").read_text(encoding="utf-8"))["screen"]
        candidates = screen["candidates"] + screen["hurricane"]["candidates"]
        self.assertEqual(len(records), 157)
        if screen["round"] == 4:  # Later CI rankings are not part of the frozen audit cohort.
            self.assertEqual({c["id"] for c in candidates}, {key for key,r in records.items() if r["audit_screen_round"] == 4})
        for model in ("Storm", "Hurricane"):
            self.assertEqual(sorted(r["rank_at_audit"] for r in records.values() if r["model"] == model and r["audit_screen_round"] == 4), list(range(1, 51)))
        self.assertEqual(sum(r["currently_listed"] for r in records.values()), 152)
        self.assertEqual(Counter(r["status"] for r in records.values()), index["summary"]["status_counts"])
        self.assertTrue(all(r["search_log"] and all(log.get("query") for log in r["search_log"]) for r in records.values()))

    def test_exact_id_attachment_preserves_predictions_and_does_not_invent_tests(self):
        records, _ = load_audit()
        rows = [{"id": "JVASP-185426", "formula": "Tl3O", "p_sc": 0.7, "tc": 2},
                {"id": "another-phase", "formula": "Tl3O", "p_sc": 0.6}]
        before = copy.deepcopy(rows)
        counts = attach_audits(rows, records)
        self.assertEqual(counts["searched"], 1)
        self.assertEqual(counts["unsearched"], 1)
        self.assertEqual(rows[0]["literature_audit"]["status"], "not-found-in-this-search")
        self.assertNotIn("check", rows[0])
        self.assertNotIn("literature_audit", rows[1])
        del rows[0]["literature_audit"]
        self.assertEqual(rows, before)

    def test_frontend_data_matches_validated_source_records(self):
        records, index = load_audit()
        script = (ROOT / "app" / "dist" / "literature-audit.js").read_text(encoding="utf-8")
        payload = json.loads(script.split("globalThis.SuperconLiterature = ", 1)[1].strip().removesuffix(";"))
        self.assertEqual(payload["by_id"], {key: compact_record(row) for key, row in records.items()})
        self.assertEqual(payload["summary"], index["summary"])

    def test_ce_heat_capacity_floor_is_not_a_superconductivity_negative(self):
        checks = json.loads((ROOT / "data" / "checks.json").read_text(encoding="utf-8"))
        ce = [m for m in checks["materials"] if m["formula"] in {"Ce2CuGa12", "Ce2NiGa12"}]
        self.assertEqual(len(ce), 2)
        for row in ce:
            self.assertIsNone(row["superconducts"])
            self.assertNotIn("below", row)
            self.assertTrue(any(r["quantity"] == "heat capacity" and r["tmin_k"] == 0.35 for r in row["measurement_conditions"]))


if __name__ == "__main__":
    unittest.main()
