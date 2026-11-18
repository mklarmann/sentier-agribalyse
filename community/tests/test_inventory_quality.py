"""The evidence a local build can support on the quality page."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import inventory_quality as quality


class InventoryQuality(unittest.TestCase):
    def test_reference_outputs_keep_nonzero_waste_and_coproducts_and_surface_missing_evidence(self):
        cases = [
            ("Products", "item;kg;1,0", "pass"),
            ("Waste treatment", "waste;kg;-0.1", "pass"),
            ("Products", "item;kg;0", "fail"),
            ("Products", "item;kg;formula", "absent"),
            ("Products", "item;;1", "absent"),
            ("Products", "item;kg;0\ntwin;kg;1", "pass"),
        ]
        for heading, rows, expected in cases:
            self.assertEqual(quality.output_evidence(f"{heading}\n{rows}\n\nEnd\n").said, expected)
        self.assertEqual(quality.output_evidence("no output section\n").said, "absent")

    def test_climate_coverage(self):
        for audited, failed, expected in [(1, 0, "pass"), (1, 1, "fail"), (0, 0, "absent")]:
            result = quality.factor_coverage({"methods": audited, "failed": failed})
            self.assertEqual(result.said, expected)
        with self.assertRaises(ValueError):
            quality.factor_coverage({"methods": 1, "failed": 2})

    def test_agreement_requires_measured_reference_scores(self):
        for within, compared, expected in [(99, 100, "pass"), (98, 100, "fail"), (0, 0, "absent")]:
            step = {
                "figures": [
                    {"label": "climate scores within 5%", "value": within},
                    {"label": "climate scores compared", "value": compared},
                ]
            }
            self.assertEqual(quality.climate_agreement(step).said, expected)

    def test_review_uses_same_revision_and_keeps_the_unrated_ef_dimensions_visible(self):
        evidence = json.loads((ROOT / "site/inventory-quality-evidence.json").read_text())
        record = json.loads((ROOT / "site/licensed-run.json").read_text())
        page = quality.render(evidence, record)
        self.assertIn("Rated 0 of 3", page)
        self.assertIn("88.3%", page)
        with self.assertRaises(ValueError):
            quality.render(evidence | {"commit": "earlier"}, record)
