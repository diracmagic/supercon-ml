"""Secondary records must not silently become experimental training evidence."""
import io
import unittest
import zipfile

from tools.normal_state_collection.batch3 import mdr_catalog as M


class MDRCatalogTests(unittest.TestCase):
    def table(self, tail):
        return ("number\tref\tformula\trho\nnum\trefno\telement\tresrt\n" + tail).encode()

    def test_strings_units_unknowns_and_blank_footer(self):
        parsed = M.parse_table(self.table("1\tR\tLa2CuO4-Y\t<0.2\n\t\t\t\n"), "table.txt")
        self.assertEqual(parsed["empty_logical_rows"], [4])
        row = parsed["rows"][0]
        self.assertEqual(row["raw_fields"]["element"], "La2CuO4-Y")
        self.assertEqual(row["raw_fields"]["resrt"], "<0.2")
        self.assertFalse(row["training_eligible"])
        self.assertFalse(row["sample_identity_verified"])
        self.assertEqual(row["phase_state"], "unclassified")

    def test_ambiguous_ids_or_ragged_fields_fail(self):
        for tail in ("1\tR\tC\t1\n1\tQ\tB\t2\n", "\tR\tC\t1\n", "1\tR\tC\n"):
            with self.assertRaises(ValueError):
                M.parse_table(self.table(tail), "table.txt")

    def test_series_and_sc_axes_stay_unclassified(self):
        raw = b"XPROP:T\nYPROP:Hc2\nXUNIT:K\nYUNIT:T\nxdata\tydata\tpdata\n1\t2\tfirst\n2\t3\tsecond\nNaN\t4\tfirst\n"
        parsed = M.text_inventory(raw, ".dat")
        self.assertEqual(parsed["numeric_xy_rows"], 2)
        self.assertEqual(parsed["axis_metadata_raw"]["YPROP"], "Hc2")
        self.assertEqual(parsed["third_column_raw_values"], {"first": 1, "second": 1})
        self.assertTrue(parsed["numeric_pairs_are_not_independent_samples"])

    def test_archive_preserves_gif_and_rejects_traversal(self):
        for unsafe in (False, True):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("../escape.dat" if unsafe else "dat/a.GIF", b"GIF89a")
            if unsafe:
                with self.assertRaises(ValueError):
                    M.archive_inventory(stream.getvalue())
            else:
                item = M.archive_inventory(stream.getvalue())[0]
                self.assertEqual(item["parse_status"], "non_numeric_attachment")
                self.assertIsNone(item["numeric_xy_rows"])
                self.assertFalse(item["training_eligible"])

    def test_multiple_graph_axes_are_not_overwritten(self):
        raw = b"FIGNO:A\nXPROP:T/Tc\nYPROP:Hc2\n1\t2\nFIGNO:B\nXPROP:T\nYPROP:Hc1\n3\t4\n"
        parsed = M.text_inventory(raw, ".dat")
        self.assertEqual(parsed["numeric_xy_rows"], 2)
        self.assertNotIn("XPROP", parsed["axis_metadata_raw"])
        self.assertEqual(parsed["axis_metadata_conflicts"]["XPROP"], ["T/Tc", "T"])
        self.assertEqual(len(parsed["metadata_sections"]), 2)
        self.assertFalse(parsed["physical_axes_resolved"])

    def test_csv_with_dat_extension_and_index_column(self):
        raw = b"Point,Temperature,Resistivity\r1,200,12\r2,250,13\r"
        parsed = M.text_inventory(raw, ".dat")
        self.assertEqual(parsed["numeric_xy_rows"], 2)
        self.assertEqual(parsed["delimiter"], "comma")
        self.assertTrue(parsed["delimiter_changed_from_extension_default"])
        self.assertFalse(parsed["physical_axes_resolved"])


if __name__ == "__main__":
    unittest.main()
