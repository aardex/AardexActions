import json
import tempfile
import unittest
from pathlib import Path

from sarif_summary import summarize


class SarifSummaryTests(unittest.TestCase):
    def test_counts_without_exposing_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.sarif"
            path.write_text(json.dumps({"version": "2.1.0", "runs": [{"results": [
                {"ruleId": "RULE-A", "message": {"text": "sensitive value"},
                 "locations": [{"physicalLocation": {"artifactLocation": {"uri": "secret.tf"}}}]},
                {"ruleId": "RULE-A"}, {"ruleId": "RULE-B"},
                {"ruleId": "BAD|<script>"}
            ]}]}), encoding="utf-8")
            summary = summarize(path, "Test")
            self.assertIn("4 results", summary)
            self.assertIn("| RULE-A | 2 |", summary)
            self.assertIn("| BAD__script_ | 1 |", summary)
            self.assertNotIn("<script>", summary)
            self.assertNotIn("sensitive value", summary)
            self.assertNotIn("secret.tf", summary)

    def test_rejects_invalid_sarif(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.sarif"
            path.write_text('{"version":"2.1.0"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                summarize(path, "Test")


if __name__ == "__main__":
    unittest.main()
