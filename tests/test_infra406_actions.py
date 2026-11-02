"""Local contract tests. These execute only the extracted bash with synthetic inputs."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = (ROOT / "azure-publish-docker/action.yml").read_text()
DOTNET = (ROOT / "azure-publish-dotnet-docker/action.yml").read_text()
DEPLOY = (ROOT / "azure-container-app-deploy/action.yml").read_text()


def script(action, name):
    block = action.split("    - name: " + name + "\n", 1)[1].split("\n    - name:", 1)[0]
    return textwrap.dedent(block.split("      run: |\n", 1)[1])


class ActionContracts(unittest.TestCase):
    def test_secret_is_not_a_build_arg_in_opt_in_mode(self):
        self.assertIn("inputs.nuget-secret-mode != 'true' && format('NUGET_PAT={0}', inputs.github-token) || ''", PUBLISH)
        self.assertIn("inputs.nuget-secret-mode == 'true' && 'nuget_pat=NUGET_PAT_SECRET' || ''", PUBLISH)
        self.assertIn("${{ inputs.build-args }}", PUBLISH)
        self.assertIn("${{ steps.build.outputs.digest }}", PUBLISH)
        self.assertIn("${{ steps.publish.outputs.digest }}", DOTNET)
        self.assertIn("nuget-secret-mode: ${{ inputs.nuget-secret-mode }}", DOTNET)
        self.assertIn("nuget-secret-mode: ${{ inputs.nuget-secret-mode }}", DEPLOY)

    def test_rejects_nuget_pat_as_extra_argument(self):
        code = script(PUBLISH, "Reject NuGet token build arguments in secret mode")
        for arg, expected in [("APP_VERSION=1.2.3", 0), ("NUGET_PAT=synthetic-secret", 1), ("NUGET_PAT", 1), (" APP=1\n  NUGET_PAT=synthetic-secret", 1)]:
            result = subprocess.run(["bash", "-e", "-c", code], env={**os.environ, "EXTRA_BUILD_ARGS": arg}, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected)
            self.assertNotIn("synthetic-secret", result.stdout + result.stderr)

    def test_digest_selection_and_legacy_tag(self):
        code = script(DEPLOY, "Resolve image reference")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            env = {**os.environ, "REGISTRY": "test.azurecr.io", "IMAGE": "cdc", "VERSION": "1.2.3", "GITHUB_OUTPUT": str(output)}
            digest = "sha256:" + "a" * 64
            result = subprocess.run(["bash", "-e", "-c", code], env={**env, "BY_DIGEST": "true", "DIGEST": digest}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output.read_text().strip(), "reference=test.azurecr.io/cdc@" + digest)
            output.unlink()
            result = subprocess.run(["bash", "-e", "-c", code], env={**env, "BY_DIGEST": "false", "DIGEST": ""}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output.read_text().strip(), "reference=test.azurecr.io/cdc:1.2.3")
            for bad in ("", "sha256:bad", "sha256:" + "A" * 64):
                result = subprocess.run(["bash", "-e", "-c", code], env={**env, "BY_DIGEST": "true", "DIGEST": bad}, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
        self.assertIn("image-ref: ${{ steps.image.outputs.reference }}", DEPLOY)
        self.assertIn('--image "$IMAGE_REFERENCE"', DEPLOY)

if __name__ == "__main__":
    unittest.main()
