"""Offline apply diagnostics tests using synthetic output and fake Terraform."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ACTION = Path(__file__).resolve().parents[1]


def block(path, name):
    manifest = path.read_text()
    step = manifest.split(f'    - name: {name}\n', 1)[1].split('\n    - name:', 1)[0]
    run = step.split('      run: ', 1)[1]
    return textwrap.dedent(run[2:]) if run.startswith('|\n') else run.splitlines()[0]


class ApplySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'bin').mkdir()
        self.fake = self.root / 'bin/terraform'
        self.fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$FIXTURE_STDOUT"\nprintf "%s\\n" "$FIXTURE_STDERR" >&2\nexit "$FIXTURE_EXIT"\n')
        self.fake.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root / 'bin') + os.pathsep + os.environ['PATH'],
                        ACTION_PATH=str(ACTION), ACTION_APPLY_PATH=str(ACTION.parent / 'terraform-apply-saved'),
                        GITHUB_OUTPUT=str(self.root / 'output'), GITHUB_STEP_SUMMARY=str(self.root / 'summary'),
                        FIXTURE_STDOUT='synthetic-success', FIXTURE_STDERR='synthetic-error <bad>&',
                        FIXTURE_EXIT='0', APPLY_ENVIRONMENT='alpha', APPLY_COMMIT='a' * 40,
                        APPLY_PLAN_ID='fixture/plan', APPLY_SUMMARY_MODE='human-readable', APPLY_OUTPUT_READY='true')

    def bash(self, script, **updates):
        return subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=self.root,
                              env={**self.env, **updates}, capture_output=True, text=True)

    def render(self, **updates):
        return subprocess.run(['python3', str(ACTION / 'summarize-apply.py')], cwd=self.root,
                              env={**self.env, **updates}, capture_output=True, text=True)

    def test_success_and_failure_capture_actual_exit_and_diagnostics(self):
        for exit_code, outcome in [('0', 'success'), ('17', 'failure')]:
            with self.subTest(exit_code=exit_code):
                (self.root / 'output').unlink(missing_ok=True)
                (self.root / 'summary').unlink(missing_ok=True)
                result = self.bash('bash "$ACTION_PATH/run-terraform.sh" apply terraform apply', FIXTURE_EXIT=exit_code)
                self.assertEqual(result.returncode, int(exit_code))
                self.assertIn('exit-code=' + exit_code, (self.root / 'output').read_text())
                self.assertNotIn('synthetic-error', result.stdout + result.stderr)
                summary = self.render(APPLY_OUTCOME=outcome, APPLY_EXIT_CODE=exit_code)
                self.assertEqual(summary.returncode, 0)
                output = (self.root / 'summary').read_text()
                for value in (outcome, exit_code, 'alpha', 'a' * 40, 'fixture/plan', 'synthetic-success',
                              'synthetic-error &lt;bad&gt;&amp;'):
                    self.assertIn(value, output)
                self.assertIn('<details>', output)
                self.assertNotIn('<bad>', output)

    def test_default_summary_does_not_disclose_captured_output(self):
        (self.root / 'apply-result.txt').write_text('synthetic-secret\n\x1b[32mApply complete! Resources: 5 added, 7 changed, 1 destroyed.\x1b[0m\n')
        result = self.render(APPLY_OUTCOME='success', APPLY_EXIT_CODE='0', APPLY_SUMMARY_MODE='counts-only')
        self.assertEqual(result.returncode, 0)
        summary = (self.root / 'summary').read_text()
        self.assertIn('5 added, 7 changed, 1 destroyed', summary)
        self.assertNotIn('synthetic-secret', summary)

    def test_truncates_to_bounded_tail_and_escapes(self):
        (self.root / 'apply-result.txt').write_text('discarded-marker' + '&' * 200000 + '<actual-error>')
        result = self.render(APPLY_OUTCOME='failure', APPLY_EXIT_CODE='1')
        self.assertEqual(result.returncode, 0)
        summary = (self.root / 'summary').read_text()
        self.assertIn('Output truncated', summary)
        self.assertIn('&lt;actual-error&gt;', summary)
        self.assertNotIn('discarded-marker', summary)
        self.assertLess(len(summary.encode()), 1024 * 1024)

    def test_unknown_exit_does_not_show_stale_result_file(self):
        (self.root / 'apply-result.txt').write_text('stale-fixture')
        result = self.render(APPLY_OUTCOME='failure', APPLY_EXIT_CODE='')
        self.assertEqual(result.returncode, 0)
        summary = (self.root / 'summary').read_text()
        self.assertIn('Apply output unavailable', summary)
        self.assertNotIn('stale-fixture', summary)

    def test_failed_cleanup_does_not_publish_stale_result(self):
        (self.root / 'apply-result.txt').write_text('stale-fixture')
        fake_rm = self.root / 'bin/rm'
        fake_rm.write_text('#!/usr/bin/env bash\nexit 9\n')
        fake_rm.chmod(0o755)
        result = self.bash('bash "$ACTION_PATH/run-terraform.sh" apply terraform apply')
        self.assertEqual(result.returncode, 9)
        output = (self.root / 'output').read_text()
        self.assertIn('output-ready=false', output)
        summary = self.render(APPLY_OUTCOME='failure', APPLY_EXIT_CODE='9', APPLY_OUTPUT_READY='false')
        self.assertEqual(summary.returncode, 0)
        self.assertNotIn('stale-fixture', (self.root / 'summary').read_text())

    def test_summary_failure_cannot_change_apply_exit(self):
        result = self.bash('bash "$ACTION_PATH/run-terraform.sh" apply terraform apply', FIXTURE_EXIT='19',
                           GITHUB_OUTPUT=str(self.root / 'missing' / 'outputs'))
        self.assertEqual(result.returncode, 19)
        for action_path, replace in [(ACTION / 'action.yml', '$ACTION_PATH'),
                                     (ACTION.parent / 'terraform-apply-saved/action.yml', '$ACTION_APPLY_PATH')]:
            manifest = action_path.read_text()
            section = manifest.split('    - name: Summarize Terraform apply\n', 1)[1].split('\n    - name:', 1)[0]
            self.assertIn('always()', section)
            script = block(action_path, 'Summarize Terraform apply').replace('${{ github.action_path }}', replace)
            summary = self.bash(script, APPLY_OUTCOME='failure', APPLY_EXIT_CODE='19',
                                GITHUB_STEP_SUMMARY=str(self.root / 'missing' / 'summary'))
            self.assertEqual(summary.returncode, 0)
            self.assertIn('summary unavailable', summary.stdout)
            self.assertNotIn('synthetic-error', summary.stdout + summary.stderr)


if __name__ == '__main__':
    unittest.main()
