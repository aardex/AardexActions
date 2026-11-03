"""Synthetic tests only: in-memory Blob service and fake plan bytes; no Azure or Terraform apply."""
import datetime as dt
from email.utils import format_datetime
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import os
import subprocess
import sys
import contextlib
import io
import textwrap
import threading
import unittest
from unittest import mock

ACTION = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plan_store', ACTION / 'plan_store.py')
store_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store_module)


class FakeBlobs:
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()
        self.created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.now = self.created
        self.fail_create = False

    def create(self, container, name, data, metadata=None):
        with self.lock:
            key = (container, name)
            if self.fail_create or key in self.items:
                raise store_module.PlanError('conditional create rejected')
            self.items[key] = {'data': data, 'metadata': dict(metadata or {}), 'etag': '"v1"'}

    def head(self, container, name):
        item = self.items.get((container, name))
        if not item:
            raise store_module.PlanError('missing')
        return {'Date': format_datetime(self.now, usegmt=True),
                'Last-Modified': format_datetime(self.created, usegmt=True),
                'ETag': item['etag'],
                **{'x-ms-meta-' + k: v for k, v in item['metadata'].items()}}

    def get(self, container, name, etag):
        item = self.items[(container, name)]
        if etag != item['etag']:
            raise store_module.PlanError('etag changed')
        return item['data']


class SecurePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.plan = self.dir / 'plan'
        self.payload = b'fixture-sensitive-plan-bytes'
        self.plan.write_bytes(self.payload)
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.env = {'GITHUB_REPOSITORY': 'aardex/PersistenceComponent', 'PLAN_ENVIRONMENT': 'alpha',
                    'PLAN_WORKSPACE': 'default', 'PLAN_ROOT': 'terraform', 'PLAN_COMMIT': 'a' * 40,
                    'PLAN_TERRAFORM_VERSION': '1.13.3', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1',
                    'PLAN_CONTAINER': 'tfplans', 'EVENT_CONTAINER': 'tfplan-events', 'PLAN_SHA256': self.sha}
        self.blobs = FakeBlobs()

    def publish(self):
        plan_id, sha = store_module.publish(self.blobs, self.env, self.plan)
        self.assertEqual(sha, self.sha)
        self.env['PLAN_ID'] = plan_id
        return plan_id

    def test_publish_and_apply_exact_bytes_with_single_use_claim(self):
        plan_id = self.publish()
        self.assertRegex(plan_id, r'^aardex/PersistenceComponent/alpha/123/1/')
        returned, path, expiry = store_module.acquire(self.blobs, self.env, self.dir)
        self.assertEqual(returned, plan_id)
        self.assertGreater(expiry, int(self.blobs.now.timestamp()))
        self.assertEqual(Path(path).read_bytes(), self.payload)
        self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
        self.assertIn(('tfplan-events', plan_id + '.claim'), self.blobs.items)
        self.env['APPLY_STATUS'] = 'success'
        self.assertEqual(store_module.record(self.blobs, self.env), 'success')
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)
        with self.assertRaises(store_module.PlanError):
            store_module.record(self.blobs, self.env)
        self.assertIn(('tfplans', plan_id + '.tfplan'), self.blobs.items)

    def test_previous_revision_plan_is_consumed_without_format_changes(self):
        # Load the real prior publisher; fake bytes and in-memory Blob storage only.
        source = subprocess.run(
            ['git', 'show', 'b6bc7e2c72f868102908b454223a4157f2dd7689:terraform-deploy/plan_store.py'],
            cwd=ACTION, check=True, capture_output=True, text=True).stdout
        previous = {'__name__': 'previous_plan_store'}
        exec(compile(source, 'previous_plan_store.py', 'exec'), previous)
        self.env.update(PLAN_ROOT='terraform/environments/alpha',
                        PLAN_COMMIT='e2e7786949c97c5d10629ab30ce7b839d75f852b',
                        GITHUB_RUN_ID='41644050622')
        plan_id = ('aardex/PersistenceComponent/alpha/41644050622/1/'
                   '285ccf5e-c20b-4ac8-8dad-899fbaaca667')
        published, digest = previous['publish'](self.blobs, self.env, self.plan, plan_id=plan_id)
        self.assertEqual((published, digest), (plan_id, self.sha))
        self.env['PLAN_ID'] = plan_id
        _, path, _ = store_module.acquire(self.blobs, self.env, self.dir)
        self.assertEqual(Path(path).read_bytes(), self.payload)
        self.assertIn(('tfplan-events', plan_id + '.claim'), self.blobs.items)
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)

    def test_reviewed_checkout_is_verified_before_initialization(self):
        action = (ACTION.parent / 'terraform-apply-saved/action.yml').read_text()
        step = action.split('    - name: Verify checkout and initialize\n', 1)[1].split('\n    - name:', 1)[0]
        script = textwrap.dedent(step.split('      run: |\n', 1)[1]).replace(
            '${{ github.action_path }}', '$ACTION_APPLY_PATH')
        bindir = self.dir / 'bin'
        bindir.mkdir()
        git = bindir / 'git'
        git.write_text('#!/usr/bin/env bash\ncase "$2" in HEAD) echo "$FAKE_COMMIT";; --show-prefix) echo terraform/environments/alpha/;; *) exit 1;; esac\n')
        git.chmod(0o755)
        terraform = bindir / 'terraform'
        terraform.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
case "$1 $2" in
  'workspace show') echo default ;;
  'version -json') echo '{"terraform_version":"1.13.3"}' ;;
esac
''')
        terraform.chmod(0o755)
        env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                   ACTION_APPLY_PATH=str(ACTION.parent / 'terraform-apply-saved'),
                   EXPECTED_COMMIT='a' * 40, FAKE_COMMIT='b' * 40, EXPECTED_WORKSPACE='default',
                   GITHUB_OUTPUT=str(self.dir / 'outputs'), CALLS=str(self.dir / 'calls'))
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=self.dir,
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.dir / 'calls').exists())
        env['FAKE_COMMIT'] = env['EXPECTED_COMMIT']
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=self.dir,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('init -upgrade -input=false', (self.dir / 'calls').read_text())
        self.assertIn('root=terraform/environments/alpha', (self.dir / 'outputs').read_text())

    def test_publish_outputs_only_nonsecret_identifier_and_hash(self):
        summary = self.dir / 'summary'
        outputs = self.dir / 'outputs'
        (self.dir / 'tfplan.tfplan').write_bytes(self.payload)
        env = {**self.env, 'PLAN_STORAGE_ACCOUNT': 'validaccount', 'GITHUB_OUTPUT': str(outputs),
               'GITHUB_STEP_SUMMARY': str(summary)}
        cwd = os.getcwd()
        try:
            os.chdir(self.dir)
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, 'argv', ['tool', 'publish']), \
                 mock.patch.object(store_module, 'token', return_value='fixture-token'), \
                 mock.patch.object(store_module, 'BlobStore', return_value=self.blobs), \
                 contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(store_module.main(), 0)
        finally:
            os.chdir(cwd)
        published = outputs.read_text() + summary.read_text() + out.getvalue() + err.getvalue()
        self.assertIn(self.sha, published)
        self.assertIn('plan-id=', published)
        self.assertNotIn(self.payload.decode(), published)
        self.assertNotIn('fixture-token', published)

    def test_atomic_claim_allows_only_one_concurrent_attempt(self):
        self.publish()
        results = []
        def attempt():
            try:
                store_module.acquire(self.blobs, self.env, self.dir)
                results.append('success')
            except store_module.PlanError:
                results.append('rejected')
        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(results, ['success', 'rejected'])
        self.assertEqual(len(list(self.dir.glob('reviewed-tfplan-*'))), 1)

    def test_duplicate_id_and_failed_upload_fail_closed(self):
        plan_id = self.publish()
        with self.assertRaises(store_module.PlanError):
            store_module.publish(self.blobs, self.env, self.plan, plan_id=plan_id)
        self.blobs.fail_create = True
        with self.assertRaises(store_module.PlanError):
            store_module.publish(self.blobs, self.env, self.plan)

    def test_missing_expired_or_future_plan_is_rejected(self):
        plan_id = self.publish()
        plan_key = ('tfplans', plan_id + '.tfplan')
        entry = self.blobs.items.pop(plan_key)
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)
        self.blobs.items[plan_key] = entry
        for age in (dt.timedelta(days=7), dt.timedelta(seconds=-1)):
            self.blobs.now = self.blobs.created + age
            with self.assertRaises(store_module.PlanError):
                store_module.acquire(self.blobs, self.env, self.dir)
        self.assertNotIn(('tfplan-events', plan_id + '.claim'), self.blobs.items)

    def test_mismatched_context_and_checksum_rejected(self):
        plan_id = self.publish()
        for key, value in [('GITHUB_REPOSITORY', 'aardex/Other'), ('PLAN_ENVIRONMENT', 'beta'),
                           ('PLAN_COMMIT', 'b' * 40), ('PLAN_WORKSPACE', 'other'), ('PLAN_ROOT', 'other'),
                           ('PLAN_TERRAFORM_VERSION', '1.13.2'), ('PLAN_SHA256', 'f' * 64)]:
            with self.subTest(key=key), self.assertRaises(store_module.PlanError):
                store_module.acquire(self.blobs, {**self.env, key: value}, self.dir)
        self.assertNotIn(('tfplan-events', plan_id + '.claim'), self.blobs.items)

    def test_corrupt_content_or_metadata_rejected_even_if_etag_unchanged(self):
        plan_id = self.publish()
        item = self.blobs.items[('tfplans', plan_id + '.tfplan')]
        item['data'] = b'tampered'
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)
        item['metadata']['sha256'] = hashlib.sha256(b'tampered').hexdigest()
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)
        self.assertNotIn(('tfplan-events', plan_id + '.claim'), self.blobs.items)

    def test_plan_changed_after_summary_is_not_uploaded(self):
        self.plan.write_bytes(b'changed')
        with self.assertRaises(store_module.PlanError):
            self.publish()
        self.assertFalse(self.blobs.items)

    def test_failed_apply_remains_claimed_and_plan_is_preserved(self):
        plan_id = self.publish()
        store_module.acquire(self.blobs, self.env, self.dir)
        self.env['APPLY_STATUS'] = 'failed'
        store_module.record(self.blobs, self.env)
        self.assertEqual(self.blobs.items[('tfplans', plan_id + '.tfplan')]['data'], self.payload)
        self.assertIn(b'failed', self.blobs.items[('tfplan-events', plan_id + '.result')]['data'])
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)

    def test_bad_claim_write_cleans_local_copy(self):
        self.publish()
        self.blobs.fail_create = True
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)
        self.assertEqual(list(self.dir.glob('reviewed-tfplan-*')), [])

    def test_saved_apply_step_uses_verified_path_and_preserves_failure(self):
        plan_id = self.publish()
        _, path, expiry = store_module.acquire(self.blobs, self.env, self.dir)
        action = (ACTION.parent / 'terraform-apply-saved/action.yml').read_text()
        step = action.split('    - name: Apply reviewed plan\n', 1)[1].split('\n    - name:', 1)[0]
        script = textwrap.dedent(step.split('      run: |\n', 1)[1]).replace(
            '${{ github.action_path }}', '$ACTION_APPLY_PATH')
        bindir = self.dir / 'bin'
        bindir.mkdir()
        fake = bindir / 'terraform'
        fake.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > \"$CAPTURE\"\necho fixture-secret-output\nexit 9\n")
        fake.chmod(0o755)
        summary = self.dir / 'summary'
        env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                   ACTION_APPLY_PATH=str(ACTION.parent / 'terraform-apply-saved'),
                   REVIEWED_PLAN_PATH=path, EXPECTED_SHA256=self.sha, PLAN_EXPIRES_AT=str(expiry),
                   CAPTURE=str(self.dir / 'call'), GITHUB_STEP_SUMMARY=str(summary))
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=self.dir,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 9)
        self.assertEqual((self.dir / 'call').read_text().strip(), f'apply -input=false -auto-approve {path}')
        self.assertNotIn('fixture-secret-output', result.stdout + result.stderr + summary.read_text())
        self.env['APPLY_STATUS'] = 'failed'
        store_module.record(self.blobs, self.env)
        with self.assertRaises(store_module.PlanError):
            store_module.acquire(self.blobs, self.env, self.dir)
        self.assertIn(('tfplans', plan_id + '.tfplan'), self.blobs.items)

    def test_token_uses_existing_azure_cli_session(self):
        completed = mock.Mock(stdout='synthetic-token\n')
        with mock.patch.object(store_module.subprocess, 'run', return_value=completed) as run:
            self.assertEqual(store_module.token(), 'synthetic-token')
        args = run.call_args.args[0]
        self.assertEqual(args[:3], ['az', 'account', 'get-access-token'])
        self.assertIn('https://storage.azure.com/', args)
        self.assertNotIn('--tenant', args)
        self.assertNotIn('--subscription', args)

    def test_actions_do_not_use_storage_oidc(self):
        plan = (ACTION / 'action.yml').read_text()
        apply = (ACTION.parent / 'terraform-apply-saved/action.yml').read_text()
        for manifest in (plan, apply):
            self.assertNotIn('azure/login@', manifest)
            self.assertNotIn('plan-storage-client-id', manifest)
            self.assertNotIn('plan-storage-tenant-id', manifest)
            self.assertNotIn('AZURE_CONFIG_DIR:', manifest)
        self.assertIn('az login --service-principal', apply)
        self.assertIn('az account set --subscription', apply)

    def test_http_create_uses_single_put_and_if_none_match(self):
        class Response:
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *_): return False
        remote = store_module.BlobStore('validaccount', 'synthetic-token')
        with mock.patch.object(remote.opener, 'open', return_value=Response()) as send:
            remote.create('tfplans', 'a/b', b'synthetic', {'sha256': self.sha})
        request = send.call_args.args[0]
        self.assertEqual(request.method, 'PUT')
        self.assertEqual(request.get_header('If-none-match'), '*')
        self.assertEqual(request.get_header('X-ms-blob-type'), 'BlockBlob')
        self.assertTrue(request.get_header('X-ms-date'))
        self.assertEqual(request.data, b'synthetic')


if __name__ == '__main__':
    unittest.main()
