import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("community_records", ROOT / "scripts/community.py")
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


class ContributionTests(unittest.TestCase):
    def setUp(self):
        self.record = records.read(ROOT / "community/templates/contribution.json")
        self.record.update(
            id="C001",
            title="Test",
            status="accepted",
            evidence=["https://example.org/source"],
            required_checks=["roundtrip"],
            required_reviewers=["partner"],
            approvals=[{"reviewer": "partner", "evidence_url": "https://example.org/approval"}],
        )
        self.record["baseline"] = dict(
            dataset="test",
            release="1",
            import_repository="https://example.org/repo",
            import_revision="abc",
            input_hashes={"source": "hash"},
        )
        self.record["layer"]["implementation_revision"] = "def"
        self.record["runs"] = [
            dict(
                baseline=copy.deepcopy(self.record["baseline"]),
                layer_revision="def",
                evidence_url="https://example.org/run",
                checks=[
                    dict(
                        id="roundtrip",
                        status="passed",
                        evidence_url="https://example.org/check",
                    )
                ],
            )
        ]

    def test_accepted_requires_passing_checks_and_approvals(self):
        self.assertFalse(records.validate(self.record))
        self.record["runs"][0]["checks"][0]["status"] = "skipped"
        self.assertTrue(records.validate(self.record))

    def test_old_run_cannot_validate_new_layer(self):
        self.record["layer"]["implementation_revision"] = "changed"
        self.assertTrue(records.validate(self.record))

    def test_missing_partner_review_is_not_consensus(self):
        self.record["approvals"] = []
        self.assertTrue(records.validate(self.record))

    def test_unresolved_objection_blocks_acceptance(self):
        self.record["objections"] = [{"reason": "boundary"}]
        self.assertTrue(records.validate(self.record))

    def test_comparison_checks_scope_metrics_units_and_finiteness(self):
        baseline = records.read(ROOT / "community/templates/run-summary.json")
        with tempfile.TemporaryDirectory() as directory:
            before, after = (
                Path(directory) / "baseline.json",
                Path(directory) / "candidate.json",
            )
            before.write_text(json.dumps(baseline))
            candidate = copy.deepcopy(baseline)
            candidate["metrics"]["processes"]["value"] = 2
            after.write_text(json.dumps(candidate))
            self.assertEqual(records.compare(before, after)["metrics"]["processes"]["delta"], 1)
            for change in [
                lambda x: x["scope"].update(method="different"),
                lambda x: x["metrics"].pop("processes"),
                lambda x: x["metrics"]["processes"].update(unit="kg"),
                lambda x: x["metrics"]["processes"].update(value=float("nan")),
            ]:
                candidate = copy.deepcopy(baseline)
                change(candidate)
                after.write_text(json.dumps(candidate))
                with self.assertRaises(ValueError):
                    records.compare(before, after)
