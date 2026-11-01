"""Atomic real-data ingestion contracts, tested with synthetic observations."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ml import feedback as F
from tests.test_feedback import normal, observation, snapshot, computed


class FeedbackBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.jsonl"
        self.ledger = F.FeedbackLedger(self.path, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_prefix_idempotence_and_copy(self):
        snap = self.ledger.append_snapshot(snapshot())
        before = self.path.read_bytes()
        rows = [normal(value=float(i)) for i in range(12)]
        out = self.ledger.append_observations(rows + [rows[0]])
        self.assertEqual(out[0], out[-1])
        self.assertEqual(out[0]["previous_hash"], snap["hash"])
        self.assertTrue(self.path.read_bytes().startswith(before))
        full = self.path.read_bytes()
        self.assertEqual(out, self.ledger.append_observations(rows + [rows[0]]))
        self.assertEqual(full, self.path.read_bytes())
        out[0]["payload"]["value"] = -100
        rows[0]["value"] = -100
        self.assertEqual(self.ledger.read()[1]["payload"]["value"], 0)
        self.assertEqual(F.verify_events(self.ledger.read())["events"], 13)

    def test_invalid_later_payload_and_future_time_leave_no_partial_batch(self):
        self.ledger.append_observation(observation())
        before = self.path.read_bytes()
        for bad in [normal(value=float("nan")), normal(observed_at="2030-01-01T00:00:00Z")]:
            with self.assertRaises((F.FeedbackValidationError, F.LedgerIntegrityError)):
                self.ledger.append_observations([normal(value=1), bad])
            self.assertEqual(self.path.read_bytes(), before)
            self.assertFalse(self.path.with_name("ledger.jsonl.lock").exists())

    def test_replace_failure_preserves_ledger_and_cleans_temp(self):
        self.ledger.append_observation(observation())
        before = self.path.read_bytes()
        with patch.object(F.os, "replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.ledger.append_observations([normal()])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["ledger.jsonl"])

    def test_tamper_lock_and_computation_cannot_bypass_checks(self):
        self.ledger.append_observation(observation())
        before = self.path.read_bytes()
        lock = self.path.with_name("ledger.jsonl.lock")
        lock.write_bytes(b"")
        with self.assertRaises(F.LedgerBusyError):
            self.ledger.append_observations([normal()])
        lock.unlink()
        with self.assertRaises(F.FeedbackValidationError):
            self.ledger.append_observations([computed()])
        self.assertEqual(before, self.path.read_bytes())
        self.path.write_bytes(before.replace(b'"tc_K":8.0', b'"tc_K":9.0'))
        with self.assertRaises(F.LedgerIntegrityError):
            self.ledger.append_observations([])

    def test_unknowns_remain_ineligible_and_empty_batch_does_not_create(self):
        self.assertEqual(self.ledger.append_observations([]), [])
        self.assertFalse(self.path.exists())
        row = normal()
        row["coordinates"]["pressure_gpa"] = None
        row["conditions"]["pressure_GPa"] = None
        row["feature_eligible"] = True
        with self.assertRaises(F.FeedbackValidationError):
            self.ledger.append_observations([row])
        row.pop("feature_eligible")
        out = self.ledger.append_observations([row])
        self.assertFalse(out[0]["payload"]["feature_eligible"])
        self.assertIsNone(out[0]["payload"]["coordinates"]["pressure_gpa"])

    def test_bulk_corrections_are_explicit_idempotent_and_preserve_originals(self):
        originals = self.ledger.append_observations([normal(value=1), normal(value=2)])
        before = self.path.read_bytes()
        corrected = [normal(value=1, unit=None, correction_reason="Original unit was unreported"),
                     normal(value=2, unit=None, correction_reason="Original unit was unreported")]
        hashes = [r["hash"] for r in originals]
        result = self.ledger.append_observations(corrected, supersedes=hashes)
        self.assertTrue(self.path.read_bytes().startswith(before))
        self.assertEqual([r["supersedes"] for r in result], hashes)
        complete = self.path.read_bytes()
        self.assertEqual(result, self.ledger.append_observations(corrected, supersedes=hashes))
        self.assertEqual(complete, self.path.read_bytes())
        self.assertEqual(F.verify_events(self.ledger.read())["active_observations"], 2)
        self.assertTrue(all(r["unit"] is None for r in [e["payload"] for e in F._active_observations(self.ledger.read())]))

    def test_invalid_bulk_correction_cannot_partially_modify_ledger(self):
        old = self.ledger.append_observation(normal(value=1))
        before = self.path.read_bytes()
        good = normal(value=3, correction_reason="Checked raw value")
        cases = [([good], []),
                 ([good, good], [old["hash"], "a" * 64]),
                 ([good, normal(value=4, correction_reason="Conflicting second correction")], [old["hash"], old["hash"]]),
                 ([normal(value=3)], [old["hash"]]),
                 ([normal(material_id="different", correction_reason="Wrong specimen")], [old["hash"]])]
        for payloads, hashes in cases:
            with self.assertRaises((F.FeedbackValidationError, F.LedgerIntegrityError)):
                self.ledger.append_observations(payloads, supersedes=hashes)
            self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
