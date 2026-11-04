#!/usr/bin/env python3
"""Local-only tests: fake Terraform executable, disposable temp directory, no network."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ACTION = Path(__file__).resolve().parents[1]
MANIFEST = (ACTION / 'action.yml').read_text()


def run_block(name):
    step = MANIFEST.split(f'    - name: {name}\n', 1)[1].split('\n    - name:', 1)[0]
    run = step.split('      run: ', 1)[1]
    if run.startswith('|\n'):
        return textwrap.dedent(run[2:]).replace('${{ github.action_path }}', '$ACTION_PATH').rstrip() + '\n'
    return run.splitlines()[0].replace('${{ github.action_path }}', '$ACTION_PATH') + '\n'


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'bin').mkdir()
        self.summary = self.root / 'summary'
        self.calls = self.root / 'calls'
        self.payload = self.root / 'payload'
        self.human_payload = self.root / 'human-payload'
        self.env = dict(os.environ, PATH=str(self.root / 'bin') + os.pathsep + os.environ['PATH'],
                        GITHUB_STEP_SUMMARY=str(self.summary), RUNNER_TEMP=str(self.root),
                        CALLS=str(self.calls), PAYLOAD=str(self.payload), HUMAN_PAYLOAD=str(self.human_payload), PLAN_ARGS='', PLAN_OUTCOME='success',
                        ACTION_PATH=str(ACTION))
        mock = self.root / 'bin/terraform'
        mock.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
case "$1" in
  init|validate) echo "$1-SECRET"; printf '%s\n' '::error::STDERR-SECRET' 'https://secret.example/token' >&2; exit "${STAGE_EXIT:-0}" ;;
  plan) echo 'PLAN-SECRET'; if [[ ${PLAN_FAIL:-0} == 1 ]]; then exit 7; fi; touch tfplan.tfplan ;;
  show) if [[ $2 == -json ]]; then cat "$PAYLOAD"; exit "${SHOW_EXIT:-0}"; else cat "$HUMAN_PAYLOAD"; echo 'SHOW-SECRET' >&2; exit "${HUMAN_SHOW_EXIT:-0}"; fi ;;
  apply) echo 'APPLY-SECRET'; exit "${APPLY_EXIT:-0}" ;;
esac
''')
        mock.chmod(0o755)

    def bash(self, script, **env):
        return subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=self.root,
                              env={**self.env, **env}, capture_output=True, text=True)

    def summarize(self, outcome='success'):
        return self.bash('bash "$SUMMARY_SCRIPT"', PLAN_OUTCOME=outcome,
                         SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))

    def write_plan(self, actions):
        changes = [{'address': 'module.secret["customer-password"]', 'change': {'actions': a,
                    'before': {'password': 'BEFORE-SECRET'}, 'after': {'token': 'AFTER-SECRET'}}}
                   for a in actions]
        self.payload.write_text(json.dumps({'format_version': '1.2', 'resource_changes': changes,
                                            'variables': {'secret': {'value': 'VARIABLE-SECRET'}},
                                            'output_changes': {'secret': {'after': 'OUTPUT-SECRET'}}}))
        (self.root / 'tfplan.tfplan').touch()

    def test_counts_and_sensitive_values(self):
        self.write_plan([['no-op'], ['read'], ['create'], ['update'], ['delete'],
                         ['delete', 'create'], ['create', 'delete']])
        result = self.summarize()
        self.assertEqual(result.returncode, 0)
        summary = self.summary.read_text()
        for label, count in [('create', 1), ('update', 1), ('delete', 1), ('replace', 2)]:
            self.assertIn(f'| {label} | {count} |', summary)
        for secret in ['SECRET', 'password', 'customer', 'token', 'module.', 'VARIABLE']:
            self.assertNotIn(secret, summary + result.stdout + result.stderr)

    def test_human_summary_is_opt_in_escaped_and_follows_counts(self):
        self.write_plan([['create']])
        self.human_payload.write_text('public = "visible"\nunmarked = "EXAMPLE-UNMARKED"\nsecret = (sensitive value)\n</code></pre><script>unsafe & markup</script>\n')
        default = self.summarize()
        self.assertEqual(default.returncode, 0)
        self.assertNotIn('public =', self.summary.read_text())
        self.assertNotIn('show -no-color', self.calls.read_text())
        self.summary.unlink()
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))
        self.assertEqual(result.returncode, 0)
        summary = self.summary.read_text()
        self.assertLess(summary.index('| create | 1 |'), summary.index('<details>'))
        self.assertIn('public = "visible"', summary)
        self.assertIn('(sensitive value)', summary)
        # Unmarked values are intentionally visible in opt-in mode.
        self.assertIn('EXAMPLE-UNMARKED', summary)
        self.assertEqual(list(self.root.glob('terraform-summary.*')), [])
        self.assertIn('&lt;/code&gt;&lt;/pre&gt;&lt;script&gt;unsafe &amp; markup&lt;/script&gt;', summary)
        self.assertNotIn('<script>', summary)
        self.assertIn('show -no-color tfplan.tfplan', self.calls.read_text())
        self.assertNotIn('SHOW-SECRET', result.stdout + result.stderr + summary)

    def test_human_mode_missing_or_failed_plan_does_not_call_show(self):
        for outcome, exists in [('failure', True), ('success', False)]:
            (self.root / 'tfplan.tfplan').unlink(missing_ok=True)
            if exists:
                (self.root / 'tfplan.tfplan').touch()
            self.summary.unlink(missing_ok=True)
            result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                               PLAN_OUTCOME=outcome, SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))
            self.assertEqual(result.returncode, 0)
            self.assertFalse(self.calls.exists())
            self.assertNotIn('<details>', self.summary.read_text())

    def test_human_mode_oversized_or_failed_show_keeps_counts(self):
        self.write_plan([['update']])
        self.human_payload.write_text('x' * 180001)
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))
        self.assertEqual(result.returncode, 0)
        self.assertIn('| update | 1 |', self.summary.read_text())
        self.assertIn('exceeds', self.summary.read_text())
        self.assertNotIn('<details>', self.summary.read_text())
        self.assertLess(self.summary.stat().st_size, 1048576)
        self.summary.unlink()
        self.human_payload.write_text('confidential but incomplete')
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable', HUMAN_SHOW_EXIT='9',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))
        self.assertEqual(result.returncode, 0)
        self.assertIn('| update | 1 |', self.summary.read_text())
        self.assertIn('Human-readable plan unavailable', self.summary.read_text())
        self.assertNotIn('confidential', self.summary.read_text() + result.stdout + result.stderr)
        self.assertNotIn('SHOW-SECRET', result.stdout + result.stderr + self.summary.read_text())
        self.assertEqual(list(self.root.glob('terraform-summary.*')), [])

    def test_largest_allowed_escaped_output_fits_summary(self):
        self.write_plan([])
        self.human_payload.write_text('&' * 180000)
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))
        self.assertEqual(result.returncode, 0)
        self.assertIn('<details>', self.summary.read_text())
        self.assertLess(self.summary.stat().st_size, 1048576)

    def test_readiness_flags_reflect_summary_generation(self):
        self.write_plan([])
        outputs = self.root / 'outputs'
        self.human_payload.write_text('synthetic plan')
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'), GITHUB_OUTPUT=str(outputs))
        self.assertEqual(result.returncode, 0)
        self.assertIn('counts-ready=true', outputs.read_text())
        self.assertIn('human-ready=true', outputs.read_text())
        outputs.unlink()
        self.human_payload.write_text('x' * 180001)
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'), GITHUB_OUTPUT=str(outputs))
        self.assertEqual(result.returncode, 0)
        self.assertIn('counts-ready=true', outputs.read_text())
        self.assertNotIn('human-ready=true', outputs.read_text())

    def test_failed_human_renderer_does_not_set_ready_flag(self):
        self.write_plan([])
        self.human_payload.write_text('synthetic plan')
        outputs = self.root / 'outputs'
        renderer = self.root / 'bin/sed'
        renderer.write_text('#!/usr/bin/env bash\nprintf partial\nexit 1\n')
        renderer.chmod(0o755)
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'), GITHUB_OUTPUT=str(outputs))
        self.assertEqual(result.returncode, 0)
        self.assertIn('counts-ready=true', outputs.read_text())
        self.assertNotIn('human-ready=true', outputs.read_text())
        self.assertNotIn('</details>', self.summary.read_text())

    def test_failed_summary_write_never_sets_ready_flags(self):
        self.write_plan([])
        self.human_payload.write_text('synthetic plan')
        outputs = self.root / 'outputs'
        self.summary.mkdir()
        self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable',
                  SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'), GITHUB_OUTPUT=str(outputs))
        if outputs.exists():
            self.assertNotIn('counts-ready=true', outputs.read_text())
            self.assertNotIn('human-ready=true', outputs.read_text())

    def test_unrecognized_mode_is_not_silently_accepted(self):
        self.write_plan([])
        result = self.bash('bash "$SUMMARY_SCRIPT"', PLAN_SUMMARY_MODE='human-readable-typo',
                           SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'))
        self.assertEqual(result.returncode, 0)
        self.assertIn('Unsupported plan summary mode', self.summary.read_text())
        self.assertNotIn('show -no-color', self.calls.read_text())

    def test_no_change(self):
        self.write_plan([])
        self.assertEqual(self.summarize().returncode, 0)
        for label in ('create', 'update', 'delete', 'replace'):
            self.assertIn(f'| {label} | 0 |', self.summary.read_text())

    def test_failed_and_missing_plan_do_not_show(self):
        (self.root / 'tfplan.tfplan').touch()
        self.assertEqual(self.summarize('failure').returncode, 0)
        self.assertFalse(self.calls.exists())
        (self.root / 'tfplan.tfplan').unlink()
        self.assertEqual(self.summarize().returncode, 0)
        self.assertFalse(self.calls.exists())
        self.assertIn('saved plan is missing', self.summary.read_text())

    def test_bad_json_show_failure_and_unknown_actions(self):
        self.write_plan([['create', 'delete', 'SECRET']])
        for payload, show_exit in [(self.payload.read_text(), '0'), ('SECRET {', '0'), ('{}', '0'), ('{}', '1')]:
            self.payload.write_text(payload)
            self.summary.unlink(missing_ok=True)
            result = self.bash('bash "$SUMMARY_SCRIPT"', SUMMARY_SCRIPT=str(ACTION / 'summarize-plan.sh'), SHOW_EXIT=show_exit)
            self.assertEqual(result.returncode, 0)
            self.assertIn('could not be summarized', self.summary.read_text())
            self.assertNotIn('SECRET', self.summary.read_text() + result.stdout + result.stderr)

    def test_failures_expose_only_fixed_stage_and_numeric_status(self):
        cases = [
            ('Terraform Init', 'init', {'STAGE_EXIT': '13'}, 13),
            ('Terraform Validate', 'validate', {'STAGE_EXIT': '13'}, 13),
            ('Terraform Plan', 'plan', {'PLAN_FAIL': '1'}, 7),
            ('Terraform Apply (opt-in)', 'apply', {'APPLY_EXIT': '4'}, 4),
        ]
        for name, stage, env, status in cases:
            with self.subTest(stage=stage):
                self.summary.unlink(missing_ok=True)
                result = self.bash(run_block(name), **env)
                self.assertEqual(result.returncode, status)
                summary = self.summary.read_text()
                self.assertIn(f'Terraform {stage} failed', summary)
                self.assertIn(f'exit status {status}', summary.lower())
                self.assertIn(f'Terraform {stage} failed', result.stdout + result.stderr)
                self.assertNotIn('SECRET', summary + result.stdout + result.stderr)
                self.assertNotIn('secret.example', summary + result.stdout + result.stderr)
                if stage == 'apply':
                    self.assertIn('partial', summary.lower())
                    self.assertIn('retry', summary.lower())

    def test_success_has_no_failure_report_and_failed_summary_keeps_exit_code(self):
        result = self.bash(run_block('Terraform Init'))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, '')
        self.assertFalse(self.summary.exists())
        self.summary.mkdir()
        result = self.bash(run_block('Terraform Init'), STAGE_EXIT='13')
        self.assertEqual(result.returncode, 13)
        self.assertIn('exit status 13', result.stdout)
        self.assertNotIn('SECRET', result.stdout + result.stderr)

    def test_output_file_failure_does_not_run_terraform(self):
        (self.root / 'init-result.txt').mkdir()
        result = self.bash(run_block('Terraform Init'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Terraform init failed', self.summary.read_text())
        self.assertFalse(self.calls.exists())
        self.assertNotIn('SECRET', result.stdout + result.stderr + self.summary.read_text())

    def test_failure_report_rejects_untrusted_stage(self):
        result = self.bash('bash "$ACTION_PATH/run-terraform.sh" "SECRET" terraform plan')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('SECRET', result.stdout + result.stderr)
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.summary.exists())

    def test_secure_storage_opt_in_does_not_change_default_apply(self):
        validation = run_block('Validate execution mode')
        legacy = dict(EXECUTION_MODE='legacy', STORAGE_MODE='none', APPLY_INPUT='false')
        self.assertEqual(self.bash(validation, **legacy).returncode, 0)
        self.assertEqual(self.bash(validation, **{**legacy, 'APPLY_INPUT': 'true'}).returncode, 0)
        self.assertEqual(self.bash(validation, **{**legacy, 'STORAGE_MODE': 'azure-blob'}).returncode, 0)
        self.assertNotEqual(self.bash(validation, **{**legacy, 'STORAGE_MODE': 'azure-blob', 'APPLY_INPUT': 'true'}).returncode, 0)
        self.assertNotEqual(self.bash(validation, **{**legacy, 'STORAGE_MODE': 'unexpected'}).returncode, 0)
        self.assertLess(MANIFEST.index('- name: Capture saved plan context'), MANIFEST.index('- name: Terraform plan summary'))
        self.assertLess(MANIFEST.index('- name: Terraform plan summary'), MANIFEST.index('- name: Store reviewed plan'))

    def test_reviewed_mode_input_validation_fails_closed(self):
        validation = run_block('Validate execution mode')
        base = dict(EXECUTION_MODE='reviewed-plan', STORAGE_MODE='azure-blob', APPLY_INPUT='false',
                    SUMMARY_MODE='human-readable', STORAGE_ACCOUNT='fixtureaccount', PLAN_CONTAINER='tfplans',
                    EVENT_CONTAINER='tfplan-events', PLAN_ENVIRONMENT='alpha',
                    PLAN_ID='synthetic-id', PLAN_SHA256='a' * 64, PLAN_COMMIT='b' * 40, PLAN_WORKSPACE='default')
        self.assertEqual(self.bash(validation, **base).returncode, 0)
        for updates in ({'EXECUTION_MODE': 'unknown'}, {'APPLY_INPUT': 'true'}, {'STORAGE_MODE': 'none'},
                        {'SUMMARY_MODE': 'counts-only'}, {'STORAGE_ACCOUNT': ''}, {'PLAN_CONTAINER': ''},
                        {'EVENT_CONTAINER': ''}, {'PLAN_ENVIRONMENT': ''}):
            with self.subTest(updates=updates):
                self.assertNotEqual(self.bash(validation, **{**base, **updates}).returncode, 0)
        reviewed_apply = {**base, 'EXECUTION_MODE': 'reviewed-apply', 'STORAGE_MODE': 'none'}
        self.assertEqual(self.bash(validation, **reviewed_apply).returncode, 0)
        self.assertEqual(self.bash(validation, **{**reviewed_apply, 'STORAGE_MODE': 'azure-blob'}).returncode, 0)
        for field in ('STORAGE_ACCOUNT', 'PLAN_CONTAINER', 'EVENT_CONTAINER', 'PLAN_ENVIRONMENT', 'PLAN_ID'):
            with self.subTest(field=field):
                self.assertNotEqual(self.bash(validation, **{**reviewed_apply, field: ''}).returncode, 0)
        self.assertNotEqual(self.bash(validation, **{**reviewed_apply, 'APPLY_INPUT': 'true'}).returncode, 0)

    def test_reviewed_apply_delegates_without_plan_or_legacy_apply(self):
        self.assertIn("default: 'legacy'", MANIFEST)
        for name in ('Terraform Init', 'Terraform Validate', 'Terraform Plan'):
            step = MANIFEST.split(f'    - name: {name}\n', 1)[1].split('\n    - name:', 1)[0]
            self.assertIn("inputs.execution-mode != 'reviewed-apply'", step)
        self.assertIn("inputs.execution-mode == 'legacy' && steps.plan.outcome", MANIFEST)
        self.assertIn('terraform-apply-saved@53c4effaa17146b2beb1e1c44f19f6c7667c63ea', MANIFEST)
        self.assertIn('apply-summary-mode: ${{ inputs.apply-summary-mode }}', MANIFEST)
        self.assertIn('ref: ${{ steps.reviewed_plan.outputs.commit }}', MANIFEST)
        self.assertIn('plan-sha256: ${{ steps.reviewed_plan.outputs.sha256 }}', MANIFEST)

    def test_plan_exit_stale_plan_and_apply_command(self):
        plan = run_block('Terraform Plan')
        apply = run_block('Terraform Apply (opt-in)')
        self.assertIn('steps.plan.outcome == \'success\' && inputs.apply == \'true\'', MANIFEST)
        self.assertIn("always() && steps.plan.outcome != 'skipped'", MANIFEST)
        self.assertIn('terraform_wrapper: false', MANIFEST)
        self.assertIn("default: 'counts-only'", MANIFEST)
        self.assertIn('PLAN_SUMMARY_MODE: ${{ inputs.plan-summary-mode }}', MANIFEST)
        self.assertNotRegex(MANIFEST, r'upload-artifact|terraform show -json.*>')
        (self.root / 'tfplan.tfplan').write_text('stale')
        failed = self.bash(plan, PLAN_FAIL='1', PLAN_ARGS='-var=password=SECRET')
        self.assertEqual(failed.returncode, 7)
        self.assertFalse((self.root / 'tfplan.tfplan').exists())
        self.assertNotIn('SECRET', failed.stdout + failed.stderr)
        self.assertEqual(self.summarize('failure').returncode, 0)
        self.assertNotIn('show ', self.calls.read_text())
        ok = self.bash(plan)
        self.assertEqual(ok.returncode, 0)
        self.assertTrue((self.root / 'tfplan.tfplan').exists())
        # The same saved plan is passed to apply, and its output stays local.
        applied = self.bash(apply, APPLY_EXIT='4')
        self.assertEqual(applied.returncode, 4)
        self.assertIn('apply -input=false -auto-approve tfplan.tfplan', self.calls.read_text())
        self.assertNotIn('APPLY-SECRET', applied.stdout + applied.stderr)
        self.assertIn('APPLY-SECRET', (self.root / 'apply-result.txt').read_text())


class LocalTerraformTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('terraform'), 'Terraform is not installed')
    def test_real_human_plan_sensitive_and_nonsensitive(self):
        # Disposable local plan with only Terraform's built-in provider, no cloud access.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'main.tf').write_text('''
variable "secret" {
  type = string
  sensitive = true
  default = "PRIVATE-MARKER"
}
resource "terraform_data" "public" { input = "public-marker" }
resource "terraform_data" "private" { input = var.secret }
''')
            (root / 'terraform.rc').write_text('disable_checkpoint = true\n')
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(('TF_', 'ARM_', 'AWS_', 'GOOGLE_'))}
            env.update(HOME=temp, TF_CLI_CONFIG_FILE=str(root / 'terraform.rc'),
                       TF_IN_AUTOMATION='1', PLAN_ARGS='', PLAN_OUTCOME='success', ACTION_PATH=str(ACTION),
                       PLAN_SUMMARY_MODE='human-readable', GITHUB_STEP_SUMMARY=str(root / 'summary'), RUNNER_TEMP=temp)
            def run(command):
                return subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(run(['terraform', 'init', '-backend=false', '-get=false', '-input=false']).returncode, 0)
            self.assertEqual(run(['bash', '-e', '-o', 'pipefail', '-c', run_block('Terraform Plan')]).returncode, 0)
            summary = run(['bash', str(ACTION / 'summarize-plan.sh')])
            self.assertEqual(summary.returncode, 0, summary.stderr)
            output = (root / 'summary').read_text()
            self.assertIn('| create | 2 |', output)
            self.assertIn('public-marker', output)
            self.assertIn('(sensitive value)', output)
            self.assertNotIn('PRIVATE-MARKER', output + summary.stdout + summary.stderr)
            self.assertNotIn('PRIVATE-MARKER', (root / 'summary').read_text())

    @unittest.skipUnless(shutil.which('terraform'), 'Terraform is not installed')
    def test_disposable_local_plan_and_apply(self):
        # Built-in terraform_data only, local backend, no modules or external providers.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'main.tf').write_text('resource "terraform_data" "example" { input = "fixture" }\n')
            (root / 'terraform.rc').write_text('disable_checkpoint = true\n')
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(('TF_', 'ARM_', 'AWS_', 'GOOGLE_'))}
            env.update(HOME=temp, TF_CLI_CONFIG_FILE=str(root / 'terraform.rc'),
                       TF_IN_AUTOMATION='1', PLAN_ARGS='', PLAN_OUTCOME='success', ACTION_PATH=str(ACTION),
                       GITHUB_STEP_SUMMARY=str(root / 'summary'), RUNNER_TEMP=temp)

            def run(command):
                return subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)

            init = run(['terraform', 'init', '-backend=false', '-get=false', '-input=false'])
            self.assertEqual(init.returncode, 0, init.stderr)
            plan = run(['bash', '-e', '-o', 'pipefail', '-c', run_block('Terraform Plan')])
            self.assertEqual(plan.returncode, 0, plan.stderr)
            self.assertFalse((root / 'terraform.tfstate').exists())  # apply=false
            summary = run(['bash', str(ACTION / 'summarize-plan.sh')])
            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertIn('| create | 1 |', (root / 'summary').read_text())
            apply = run(['bash', '-e', '-o', 'pipefail', '-c', run_block('Terraform Apply (opt-in)')])
            self.assertEqual(apply.returncode, 0, apply.stderr)
            self.assertTrue((root / 'terraform.tfstate').exists())  # disposable local state only
            again = run(['bash', '-e', '-o', 'pipefail', '-c', run_block('Terraform Plan')])
            self.assertEqual(again.returncode, 0, again.stderr)
            (root / 'summary').unlink()
            self.assertEqual(run(['bash', str(ACTION / 'summarize-plan.sh')]).returncode, 0)
            self.assertIn('| create | 0 |', (root / 'summary').read_text())
            (root / 'main.tf').write_text('this is invalid terraform\n')
            failed = run(['bash', '-e', '-o', 'pipefail', '-c', run_block('Terraform Plan')])
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((root / 'tfplan.tfplan').exists())


if __name__ == '__main__':
    unittest.main()
