import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resolve_scan_config.sh"


class ScanConfigTests(unittest.TestCase):
    def run_resolver(self, workspace: Path, kind: str, project_file: str = ""):
        return subprocess.run(
            ["bash", str(SCRIPT), kind, project_file],
            cwd=workspace, text=True, capture_output=True, check=False,
        )

    def test_defaults_are_explicit_and_ignore_implicit_trivy_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "trivy.yaml").write_text("severity: [LOW]\n")
            (root / ".trivyignore").write_text("AVD-DS-0002\n")
            for kind, expected in {
                "checkov": "skip-check: []\n",
                "trivy-config": "{}\n",
                "trivy-ignore": "vulnerabilities: []\nmisconfigurations: []\nsecrets: []\n",
            }.items():
                result = self.run_resolver(root, kind)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / result.stdout.strip()).read_text(), expected)
                self.assertTrue(result.stdout.strip().startswith(".security-reports/"))

    def test_project_override_is_used_and_missing_override_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy.yaml").write_text("skip-check: [CKV_DOCKER_3]\n")
            for kind in ("checkov", "trivy-config", "trivy-ignore"):
                self.assertEqual(self.run_resolver(root, kind, "policy.yaml").stdout.strip(), "policy.yaml")
                self.assertNotEqual(self.run_resolver(root, kind, "missing.yaml").returncode, 0)

    def test_checkov_rejects_unselected_implicit_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".checkov.yaml").write_text("skip-check: [CKV_DOCKER_3]\n")
            self.assertNotEqual(self.run_resolver(root, "checkov").returncode, 0)
            self.assertNotEqual(self.run_resolver(root, "checkov", "policy.yaml").returncode, 0)
            accepted = self.run_resolver(root, "checkov", ".checkov.yaml")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stdout.strip(), ".checkov.yaml")

    def test_does_not_write_through_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".security-reports").symlink_to(root)
            self.assertNotEqual(self.run_resolver(root, "checkov").returncode, 0)


if __name__ == "__main__":
    unittest.main()
