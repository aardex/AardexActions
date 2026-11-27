"""Run the real `run:` blocks of the OCI workflows with fake gh/docker; no network, Azure or registry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'release-management'))
sys.path.insert(0, str(ROOT / 'release-management' / 'tests'))

SHA = 'a' * 40
DIGEST = 'sha256:' + 'b' * 64
REGISTRY = 'acradxinframgmeun.azurecr.io'
REF = f'{REGISTRY}/mma-backend-api@{DIGEST}'
REPO_URL = 'https://github.com/aardex/MemsMobile.Backend'


def step(workflow, name):
    jobs = yaml.safe_load((ROOT / '.github' / 'workflows' / workflow).read_text())['jobs']
    return next(s for job in jobs.values() for s in job['steps'] if s.get('name') == name)['run']


class Step(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.output = self.dir / 'output'
        self.output.touch()

    def tearDown(self):
        self.tmp.cleanup()

    def fake(self, name, stdout):
        (self.dir / name).write_text(f"#!/usr/bin/env bash\ncat <<'JSON'\n{stdout}\nJSON\n")
        (self.dir / name).chmod(0o755)

    def run_step(self, workflow, name, **env):
        environ = {'PATH': f'{self.dir}:{os.environ["PATH"]}', 'GITHUB_OUTPUT': str(self.output), **env}
        return subprocess.run(['bash', '-e', '-c', step(workflow, name)], env=environ,
                              capture_output=True, text=True, timeout=30, cwd=self.dir)

    def outputs(self):
        return dict(line.split('=', 1) for line in self.output.read_text().splitlines())


class Promote(Step):
    WF = 'oci-promote-containerapp.yml'

    def validate(self, ref, sha=''):
        return self.run_step(self.WF, 'Validate the image reference', IMAGE_REF=ref,
                             EXPECTED_REGISTRY=REGISTRY, EXPECTED_SHA=sha)

    def test_only_shared_registry_digests_are_promotable(self):
        self.assertEqual(0, self.validate(REF).returncode)
        self.assertEqual(DIGEST, self.outputs()['digest'])
        for ref in [f'{REGISTRY}/mma-backend-api:3.1.0', f'acrenvinfraprdeun.azurecr.io/mma-backend-api@{DIGEST}',
                    f'{REGISTRY}/mma-backend-api@sha256:short', f'{REF}\n{REF}']:
            with self.subTest(ref=ref):
                self.assertNotEqual(0, self.validate(ref).returncode)

    def approval(self, records, required='true', environment='prod'):
        self.fake('gh', json.dumps(records))
        return self.run_step(self.WF, 'Prove the environment approval of this run', GH_TOKEN='x',
                             REQUIRED=required, ENVIRONMENT=environment, RUN_URL='repos/o/r/actions/runs/1/approvals')

    def record(self, state='approved', env='prod'):
        return {'state': state, 'comment': 'ok', 'user': {'login': 'reviewer'}, 'environments': [{'name': env}]}

    def test_prod_requires_a_recorded_approval_for_that_environment(self):
        self.assertNotEqual(0, self.approval([]).returncode)
        self.assertNotEqual(0, self.approval([self.record(state='rejected')]).returncode)
        self.assertNotEqual(0, self.approval([self.record(env='beta')]).returncode)
        result = self.approval([self.record(env='Prod')])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([{'user': 'reviewer', 'comment': 'ok'}], json.loads(self.outputs()['approvals']))

    def test_unrequired_approval_is_only_recorded_and_names_are_data(self):
        self.assertEqual(0, self.approval([], required='false').returncode)
        self.assertEqual(0, self.approval([self.record(env='a"b')], environment='a"b').returncode)

    def verify(self, labels, expected_sha=''):
        self.fake('docker', json.dumps({'config': {'Labels': labels}}))
        return self.run_step(self.WF, 'Verify the published digest and its provenance label',
                             IMAGE_REF=REF, EXPECTED_SHA=expected_sha, EXPECTED_SOURCE=REPO_URL)

    def test_digest_must_come_from_this_repository_and_expected_source(self):
        good = {'org.opencontainers.image.revision': SHA, 'org.opencontainers.image.source': REPO_URL}
        self.assertEqual(0, self.verify(good, expected_sha=SHA).returncode)
        for labels, expected in [({}, ''), ({**good, 'org.opencontainers.image.source': 'https://github.com/aardex/AcquisitionComponent'}, ''),
                                 (good, 'c' * 40)]:
            with self.subTest(labels=labels, expected=expected):
                self.assertNotEqual(0, self.verify(labels, expected_sha=expected).returncode)

    def rollout(self, health_sequence, fail_app='', wait='true'):
        # All Azure commands are replaced by a stateful local executable.
        fake = self.dir / 'az'
        fake.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
state_file = Path(os.environ['FAKE_STATE'])
state = json.loads(state_file.read_text()) if state_file.exists() else {'updated': [], 'health_calls': 0}
app = args[args.index('-n') + 1]
query = args[args.index('--query') + 1] if '--query' in args else ''
if args[:2] == ['containerapp', 'update']:
    state['updated'].append(app)
    state_file.write_text(json.dumps(state))
    if app == os.environ['FAIL_APP']:
        sys.exit(1)
elif args[:3] == ['containerapp', 'revision', 'show']:
    if query == 'properties.healthState':
        states = json.loads(os.environ['HEALTH_SEQUENCE'])
        print(states[min(state['health_calls'], len(states) - 1)])
        state['health_calls'] += 1
        state_file.write_text(json.dumps(state))
    elif query == 'properties.provisioningState': print('Provisioned')
    elif query == 'properties.runningState': print('Running')
elif args[:3] == ['containerapp', 'replica', 'count']: print('1')
elif 'registries' in query: print(os.environ['REGISTRY'])
elif query == 'properties.latestRevisionName': print(app + ('-new' if app in state['updated'] else '-old'))
elif 'containers[0].image' in query: print(os.environ['IMAGE_REF'] if app in state['updated'] else app + '-old-image')
""")
        fake.chmod(0o755)
        self.fake('sleep', '')
        return self.run_step(self.WF, 'Roll out the digest and wait for health', IMAGE_REF=REF,
                             REGISTRY=REGISTRY, APPS='app-a\napp-b', RESOURCE_GROUP='fixture', AZ_ENV='test',
                             WAIT_FOR_REPLICAS=wait, FAKE_STATE=str(self.dir / 'state'), FAIL_APP=fail_app,
                             HEALTH_SEQUENCE=json.dumps(health_sequence))

    def test_partial_failure_preserves_previous_state_and_progress(self):
        result = self.rollout(['Healthy'], fail_app='app-b')
        self.assertNotEqual(0, result.returncode)
        apps = json.loads(self.outputs()['apps'])
        self.assertEqual(['app-a', 'app-b'], [app['app'] for app in apps])
        self.assertEqual('app-a-old-image', apps[0]['previous_image'])
        self.assertEqual('app-a-new', apps[0]['revision'])
        self.assertEqual('app-b-old-image', apps[1]['previous_image'])
        self.assertEqual('app-b-old', apps[1]['previous_revision'])
        self.assertEqual('updating', apps[1]['status'])
        record = self.run_step(self.WF, 'Write the promotion record', ENVIRONMENT='test', IMAGE_REF=REF,
                               DIGEST=DIGEST, REVISION=SHA, SOURCE=REPO_URL, APPROVALS='[]',
                               APPS=json.dumps(apps), OUTCOME='failure', RUN='https://example.test/run',
                               ACTOR='tester', GITHUB_STEP_SUMMARY=str(self.dir / 'summary'))
        self.assertEqual(0, record.returncode, record.stderr)
        self.assertEqual(apps, json.loads((self.dir / 'promotion-record.json').read_text())['apps'])

    def test_unknown_health_waits_for_healthy_in_both_modes(self):
        for wait in ['true', 'false']:
            with self.subTest(wait=wait):
                (self.dir / 'state').unlink(missing_ok=True)
                result = self.rollout(['None', 'Unknown', 'Healthy'], wait=wait)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertGreaterEqual(json.loads((self.dir / 'state').read_text())['health_calls'], 4)

    def test_unknown_health_does_not_pass_in_scale_to_zero_mode(self):
        result = self.rollout(['None'], wait='false')
        self.assertNotEqual(0, result.returncode)
        apps = json.loads(self.outputs()['apps'])
        self.assertEqual('None', apps[0]['health'])


class Publish(Step):
    WF = 'oci-publish.yml'

    def test_nuget_token_cannot_be_a_build_argument(self):
        base = dict(IMAGE='mma-backend-api', SOURCE_REF='', VERSION='', REGISTRY=REGISTRY, GATE='report')
        self.assertEqual(0, self.run_step(self.WF, 'Validate inputs', BUILD_ARGS='A=1', **base).returncode)
        self.assertNotEqual(0, self.run_step(self.WF, 'Validate inputs', BUILD_ARGS='A=1\n NUGET_PAT=x', **base).returncode)

    def published(self, revision):
        self.fake('docker', json.dumps({'config': {'Labels': {'org.opencontainers.image.revision': revision}}}))
        return self.run_step(self.WF, 'Resolve content-addressed reference', REGISTRY=REGISTRY,
                             IMAGE='mma-backend-api', DIGEST=DIGEST, SHA=SHA)

    def test_reference_is_bound_to_the_built_source(self):
        self.assertEqual(0, self.published(SHA).returncode)
        self.assertEqual(REF, self.outputs()['image-ref'])
        self.assertNotEqual(0, self.published('c' * 40).returncode)


class ManifestCompatibility(Step):
    """The publish output must be accepted unchanged by the EN-44 release-management publisher."""

    def test_publish_manifest_data_is_valid_release_manifest_input(self):
        import manifest as m
        import test_manifest
        case = test_manifest.ManifestPublication('test_valid_artifact_digest_is_declared_and_bound_to_release')
        case.setUp()
        self.addCleanup(case.tearDown)
        wanted, sha, _ = case.prepare()
        self.fake('docker', json.dumps({'config': {'Labels': {'org.opencontainers.image.revision': sha}}}))
        result = self.run_step('oci-publish.yml', 'Resolve content-addressed reference', REGISTRY=REGISTRY,
                               IMAGE='mma-backend-api', DIGEST=DIGEST, SHA=sha)
        self.assertEqual(0, result.returncode, result.stderr)
        data = self.outputs()['manifest-data']
        with patch.dict(os.environ, RELEASE_MANIFEST_DATA=data):
            document = m.generate(case.api, wanted, sha)
        self.assertEqual(json.loads(data)['artifacts'], document['artifacts'])
        self.assertEqual('missing', document['sbom']['state'])
        self.assertEqual('missing', document['provenance']['state'])


if __name__ == '__main__':
    unittest.main()
