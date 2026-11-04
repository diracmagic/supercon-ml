"""Offline checks of the paper feed filters and of the curated-advances merge (feed/sync_curation.py)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "feed" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


papers = load("papers")
sync = load("sync_curation")


def entry(ref: str, **extra) -> dict:
    item = {"d": "2026-10", "k": "experiment", "cards": ["nickelate"], "ref": ref,
            "h": "A new nickelate result", "x": "A summary in our own words."}
    item.update(extra)
    return item


class FeedFilterTest(unittest.TestCase):
    def test_editorial_notices_are_not_new_papers(self):
        for title in ("Author Correction: Magnetic field screening in hydrogen-rich high-temperature superconductors",
                      "Publisher Correction: Reply to: Conductance measurements cannot distinguish crossed Andreev reflection",
                      "Addendum: Magnetic field screening in hydrogen-rich high-temperature superconductors",
                      "Retraction Note: Evidence of near-ambient superconductivity", "Erratum: Superconductivity in X",
                      "Correction to “Superconductivity in X”"):
            self.assertTrue(papers.is_notice(title), title)
        for title in ("Reply to “On the Author Correction to “Magnetic field screening in hydride superconductors”",
                      "Corrections to the BCS gap equation from vertex terms",
                      "Correction of the superconducting gap anisotropy in MgB2", "Superconductivity in UTe2"):
            self.assertFalse(papers.is_notice(title), title)

    def test_superionic_conductors_are_not_superconductors(self):
        self.assertTrue(papers.is_ion_conductor("Synthesis of ZIF-62 Glass and Solid-state Lithium Superconductor Composite "
                                                "Membranes for Electrodialytic Lithium Extraction"))
        for title in ("Superconductivity in compressed lithium", "Ionic liquid gating induces superconductivity",
                      "Electrolyte gating of superconducting films", "Superconducting NbSe2 membranes"):
            self.assertFalse(papers.is_ion_conductor(title), title)


class CurationMergeTest(unittest.TestCase):
    def setUp(self):
        self.main = {"contact": {"service": "web3forms", "key": "public-form-key"}, "schema": 1, "updated": "2026-10-31",
                     "about": "Curated recent advances.", "refs": {"old2026": {"t": "A. Old et al., Nature (2026)", "d": "10.1038/old"}},
                     "recent": [entry("old2026", h="An entry already on main")], "hide": ["builtin2020"]}
        self.curated = json.loads(json.dumps(self.main))
        self.curated["refs"]["new2026"] = {"t": "B. New et al., Phys. Rev. Lett. (2026)", "d": "10.1103/new"}
        self.curated["recent"].insert(0, entry("new2026"))

    def test_new_valid_entry_is_added_and_main_stays_authoritative(self):
        self.curated["recent"][1]["h"] = "Rewritten on the branch"
        self.curated["contact"] = {"service": "elsewhere", "key": "changed"}
        self.curated["hide"] = []
        merged, added, skipped = sync.merge(self.main, self.curated, today="2026-11-04")
        self.assertEqual(added, ["new2026"])
        self.assertEqual(skipped, [])
        self.assertEqual([r["ref"] for r in merged["recent"]], ["new2026", "old2026"])
        self.assertEqual(merged["recent"][1]["h"], "An entry already on main")
        self.assertEqual(merged["contact"], self.main["contact"])
        self.assertEqual(merged["hide"], ["builtin2020"])
        self.assertEqual(merged["updated"], "2026-11-04")
        self.assertEqual(self.main["updated"], "2026-10-31", "the input is not modified")
        again, added_again, _ = sync.merge(merged, self.curated, today="2026-11-05")
        self.assertEqual(added_again, [])
        self.assertEqual(again, merged)

    def test_invalid_or_duplicate_entries_are_skipped_with_a_reason(self):
        bad = [
            (entry("kind2026", k="opinion"), {"t": "C", "d": "10.1/kind"}),
            (entry("card2026", cards=["unknown"]), {"t": "C", "d": "10.1234/card"}),
            (entry("date2026", d="2026-13"), {"t": "C", "d": "10.1234/date"}),
            (entry("long2026", h="x" * 181), {"t": "C", "d": "10.1234/long"}),
            (entry("html2026", x="<script>alert(1)</script>"), {"t": "C", "d": "10.1234/html"}),
            (entry("Upper2026"), {"t": "C", "d": "10.1234/upper"}),
            (entry("nodoi2026"), {"t": "C", "d": "doi:10.1234/x"}),
            (entry("http2026"), {"t": "C", "u": "http://example.org/paper"}),
            (entry("same2026"), {"t": "C", "d": "10.1038/OLD"}),
            (entry("missing2026"), None),
            (dict(entry("extra2026"), live=True), {"t": "C", "d": "10.1234/extra"}),
        ]
        for item, ref in bad:
            self.curated["recent"].append(item)
            if ref is not None:
                self.curated["refs"][item["ref"]] = ref
        merged, added, skipped = sync.merge(self.main, self.curated, builtin={"10.1234/builtin"}, today="2026-11-04")
        self.assertEqual(added, ["new2026"])
        reasons = dict(skipped)
        self.assertEqual(set(reasons), {item["ref"] for item, _ in bad})
        self.assertIn("the same paper is already listed", reasons["same2026"])
        self.assertTrue(all(k not in merged["refs"] for k in reasons))
        self.curated["recent"] = [entry("built2026")]
        self.curated["refs"]["built2026"] = {"t": "D", "d": "10.1234/BUILTIN"}
        _, added, skipped = sync.merge(self.main, self.curated, builtin={"10.1234/builtin"})
        self.assertEqual(added, [])
        self.assertEqual(skipped, [("built2026", "the same paper is already listed")])

    def test_limits_of_the_app_are_respected(self):
        self.main["recent"] = [entry(f"r{i:03d}") for i in range(sync.MAX_RECENT)]
        _, added, skipped = sync.merge(self.main, self.curated)
        self.assertEqual(added, [])
        self.assertIn("at most", skipped[0][1])

    def test_layout_and_builtin_links_match_the_repository(self):
        text = (ROOT / "progress" / "content.json").read_text(encoding="utf-8")
        self.assertEqual(sync.dump_content(json.loads(text)), text, "content.json keeps its existing layout")
        links = sync.builtin_links(ROOT / "app" / "dist" / "js" / "initialize" / "content.js")
        self.assertIn("10.1073/pnas.2536178123", links)

    def test_command_line_writes_only_when_something_is_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, source = Path(tmp) / "content.json", Path(tmp) / "curated.json"
            target.write_text(sync.dump_content(self.main), encoding="utf-8")
            source.write_text(json.dumps(self.curated), encoding="utf-8")
            run = lambda: subprocess.run([sys.executable, str(ROOT / "feed" / "sync_curation.py"), str(target), str(source)],
                                         capture_output=True, text=True, check=True)
            self.assertIn("added 1 curated advance(s): new2026", run().stdout)
            first = target.read_text(encoding="utf-8")
            self.assertTrue(first.startswith('{ "contact": {"service": "web3forms", "key": "public-form-key"},\n'))
            self.assertIn("no new curated advances", run().stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), first)
            source.write_text("not json", encoding="utf-8")
            self.assertIn("unreadable", run().stdout)


if __name__ == "__main__":
    unittest.main()
