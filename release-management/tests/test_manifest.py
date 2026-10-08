"""Offline snapshots and publication with real disposable Git, mock GitHub only."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_release as fixture
import release as r
import manifest as m


class ManifestPublication(unittest.TestCase):
    setUp = fixture.Fixture.setUp
    tearDown = fixture.Fixture.tearDown
    change = fixture.Fixture.change
    release_pr = fixture.Fixture.release_pr
    merge_release = fixture.Fixture.merge_release

    def prepare(self, fixture='keycloak'):
        data = json.loads((Path(__file__).parent / 'fixtures' / (fixture + '.json')).read_text())
        self.api.repo = data['repository']
        self.api.config = r.Config(branch=data['branch'], product=data['product'])
        os.environ['GITHUB_WORKFLOW_REF'] = self.api.repo + '/.github/workflows/release.yml@refs/heads/main'
        self.change(data['title'])
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, sha = self.merge_release()
        os.environ['RELEASE_MANIFEST_DATA'] = json.dumps(data['manifest_data']).replace('$RELEASE_SHA', sha)
        wanted, resolved = r.preflight(self.api, p['number'])
        self.assertEqual(sha, resolved)
        return wanted, sha, p

    def test_stable_pilot_manifests_source_is_not_artifact_or_deployment(self):
        wanted, sha, p = self.prepare()
        first = m.generate(self.api, wanted, sha)
        second = m.generate(self.api, wanted, sha)
        self.assertEqual(r.json_text(first), r.json_text(second))
        self.assertEqual(['EN-13', 'EN-44'], first['jira_keys'])
        self.assertEqual('source', first['release']['kind'])
        self.assertNotEqual(sha, first['release_pr']['head_sha'])
        self.assertNotIn('deployment', first)
        self.assertEqual('missing', first['artifacts']['state'])
        self.assertEqual('not_applicable', first['migrations']['state'])
        self.assertEqual(None, first['generator']['conclusion'])
        observed = [c for c in first['checks'] if c['state'] == 'available']
        self.assertTrue(observed)
        self.assertTrue(all(c['checked_sha'] == p['head']['sha'] for c in observed))
        self.assertTrue(all(c['kind'] == 'release-mechanics' for c in observed))

    def test_iac_declared_branch_and_constraint_are_not_resolved(self):
        wanted, sha, _ = self.prepare('terraform-runner')
        document = m.generate(self.api, wanted, sha)
        self.assertTrue(all(i['resolved'] is None and i['verification'] == 'declared'
                            for i in document['dependencies']['items']))
        dependency = document['dependencies']['items'][0]
        dependency['resolved'] = {'kind': 'git_commit', 'value': 'main'}
        with self.assertRaisesRegex(ValueError, 'exact version'):
            m.validate(document, self.api.repo, wanted['metadata'], sha, wanted['release_pr']['head']['sha'], 'v')
        dependency['resolved'] = {'kind': 'git_commit', 'value': 'b' * 40}
        m.validate(document, self.api.repo, wanted['metadata'], sha, wanted['release_pr']['head']['sha'], 'v')

    def test_missing_checks_and_real_failure_pending_skipped_cancelled_results(self):
        wanted, sha, p = self.prepare()
        self.api.statuses = [(p['head']['sha'], state, 'build') for state in ('failure', 'error', 'pending')]
        original = self.api.pages
        def pages(path, key=None):
            if '/check-runs?' in path and p['head']['sha'] in path:
                return [{'id': 200 + i, 'name': 'Product tests', 'head_sha': p['head']['sha'],
                         'status': status, 'conclusion': conclusion}
                        for i, (status, conclusion) in enumerate([
                            ('completed', 'failure'), ('completed', 'skipped'), ('completed', 'cancelled'),
                            ('in_progress', None), ('queued', None)])]
            return original(path, key)
        with patch.object(self.api, 'pages', side_effect=pages):
            document = m.generate(self.api, wanted, sha)
        self.assertEqual({'failure', 'error', 'pending', 'completed', 'in_progress', 'queued'},
                         {c['outcome']['status'] for c in document['checks'] if c['state'] == 'available'})
        self.assertEqual({'release-inputs', 'release-tests'},
                         {c['name'] for c in document['checks'] if c['state'] == 'missing' and c['kind'] == 'release-mechanics'})
        self.assertFalse(any(c.get('outcome', {}).get('status') == 'success' for c in document['checks']))

    def test_check_run_mismatched_sha_blocks_before_tag_creation(self):
        wanted, sha, p = self.prepare()
        original = self.api.pages
        def pages(path, key=None):
            if '/check-runs?' in path:
                return [{'head_sha': 'c' * 40}]
            return original(path, key)
        with patch.object(self.api, 'pages', side_effect=pages):
            with self.assertRaisesRegex(ValueError, 'check-run SHA mismatch'):
                r.publish(self.api, p['number'])
        self.assertFalse(self.api.tags)

    def test_identity_and_evidence_tampering_rejected(self):
        wanted, sha, p = self.prepare()
        document = m.generate(self.api, wanted, sha)
        for section, field, value in [('release', 'version', '9.0.0'), ('release', 'tag', 'v9.0.0'),
                                     ('release', 'sha', 'd' * 40), ('release_pr', 'head_sha', 'd' * 40),
                                     ('release_pr', 'merge_sha', 'd' * 40), ('generator', 'conclusion', 'success')]:
            with self.subTest(section=section, field=field):
                changed = copy.deepcopy(document)
                changed[section][field] = value
                with self.assertRaises(ValueError):
                    m.validate(changed, self.api.repo, wanted['metadata'], sha, p['head']['sha'], 'v')
        document['checks'][0]['checked_sha'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'evidence SHA mismatch'):
            m.validate(document, self.api.repo, wanted['metadata'], sha, p['head']['sha'], 'v')

    def test_valid_artifact_digest_is_declared_and_bound_to_release(self):
        wanted, sha, _ = self.prepare()
        data = {'artifacts': {'state': 'available', 'items': [{
            'type': 'container', 'reference': 'example.azurecr.io/service@sha256:' + 'f' * 64,
            'digest': 'sha256:' + 'f' * 64, 'release_sha': sha, 'verification': 'declared'}]}}
        with patch.dict(os.environ, RELEASE_MANIFEST_DATA=json.dumps(data)):
            document = m.generate(self.api, wanted, sha)
        self.assertEqual(data['artifacts'], document['artifacts'])
        for field, value in [('digest', sha), ('digest', 'sha256:bad'), ('verification', 'observed'),
                             ('release_sha', 'c' * 40), ('reference', 'https://user:secret@evil.test/file'),
                             ('reference', '//user:secret@evil.test/file'),
                             ('reference', 'https://evil.test/file?token=secret')]:
            with self.subTest(field=field, value=value):
                invalid = copy.deepcopy(data)
                invalid['artifacts']['items'][0][field] = value
                with patch.dict(os.environ, RELEASE_MANIFEST_DATA=json.dumps(invalid)):
                    with self.assertRaises(ValueError):
                        m.generate(self.api, wanted, sha)

    def test_bad_or_unsupported_input_blocks_without_publication_mutations(self):
        _, _, p = self.prepare()
        for raw in ['{', '[]', '{"artifacts":null}', '{"artifacts":{"state":"available","items":[]}}',
                    '{"migrations":{"state":"not_applicable","reason":""}}',
                    '{"sbom":{},"sbom":{}}', '{"deployment":{}}', 'x' * 65537]:
            with self.subTest(raw=raw[:60]), patch.dict(os.environ, RELEASE_MANIFEST_DATA=raw):
                with self.assertRaises(ValueError):
                    r.publish(self.api, p['number'])
                self.assertFalse(self.api.tags)
                self.assertFalse(self.api.records)

    def test_upload_and_digest_verification_before_publication_and_after(self):
        _, sha, p = self.prepare()
        original = self.api.request
        events = []
        def request(path, method='GET', data=None, missing=False):
            if path == '/releases/assets/10':
                events.append('verify')
            if method == 'PATCH' and data == {'draft': False}:
                self.assertEqual(['verify'], events)
                events.append('publish')
            return original(path, method, data, missing)
        with patch.object(self.api, 'request', side_effect=request):
            r.publish(self.api, p['number'])
        self.assertEqual(['verify', 'publish', 'verify'], events)
        document = json.loads(self.api.manifest_payload)
        self.assertEqual(sha, document['release']['sha'])
        self.assertNotIn('release-manifest.json', self.api.config.files)

    def test_upload_failure_and_integrity_failures_leave_blocking_draft(self):
        _, _, p = self.prepare()
        original = self.api.upload_manifest
        def corrupt(release_id, payload):
            asset = original(release_id, payload)
            asset['digest'] = 'sha256:' + '0' * 64
            return asset
        with patch.object(self.api, 'upload_manifest', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                r.publish(self.api, p['number'])
        self.assertTrue(self.api.records['v1.0.1']['draft'])
        with self.assertRaisesRegex(ValueError, 'Duplicate Git tag'):
            r.publish(self.api, p['number'])
        self.assertFalse(any(method in ('DELETE',) for _, method, _ in self.api.mutations))

    def test_upload_http_failure_leaves_draft(self):
        _, _, p = self.prepare()
        with patch.object(self.api, 'upload_manifest', side_effect=RuntimeError('Upload failed')):
            with self.assertRaisesRegex(RuntimeError, 'Upload failed'):
                r.publish(self.api, p['number'])
        self.assertTrue(self.api.records['v1.0.1']['draft'])
        self.assertFalse(self.api.assets)

    def test_asset_identity_state_size_and_digest_are_all_required(self):
        _, _, p = self.prepare()
        r.publish(self.api, p['number'])
        asset = self.api.assets[10]
        valid = dict(asset)
        for field, value in [('name', 'other.json'), ('id', 11), ('state', 'starter'),
                             ('size', asset['size'] + 1), ('digest', None)]:
            with self.subTest(field=field):
                asset.clear()
                asset.update(valid)
                asset[field] = value
                with self.assertRaises(ValueError):
                    m.verify_asset(self.api, 1, self.api.manifest_payload, 10)
        asset.clear()
        asset.update(valid)
        self.api.assets[11] = dict(asset, id=11)
        with self.assertRaisesRegex(ValueError, 'missing or conflicting'):
            m.verify_asset(self.api, 1, self.api.manifest_payload, 10)

    def test_absent_workflow_identity_or_failed_reads_block_before_mutations(self):
        _, _, p = self.prepare()
        with patch.dict(os.environ, GITHUB_RUN_ID=''):
            with self.assertRaisesRegex(ValueError, 'workflow identity'):
                r.publish(self.api, p['number'])
        with patch.object(self.api, 'pages', side_effect=RuntimeError('Permission denied')):
            with self.assertRaisesRegex(RuntimeError, 'Permission denied'):
                r.publish(self.api, p['number'])
        self.assertFalse(self.api.tags)

    def test_release_sha_ignores_workflow_sha_and_later_trunk(self):
        _, sha, p = self.prepare()
        later = self.change('docs: later trunk change')
        with patch.dict(os.environ, GITHUB_SHA=later):
            r.publish(self.api, p['number'])
        document = json.loads(self.api.manifest_payload)
        self.assertEqual(sha, document['release']['sha'])
        self.assertEqual(later, document['generator']['run_head_sha'])
        self.assertEqual('a' * 40, document['generator']['workflow_sha'])

    def test_source_tag_changed_during_upload_does_not_publish(self):
        _, _, p = self.prepare()
        original = self.api.upload_manifest
        def upload(release_id, payload):
            asset = original(release_id, payload)
            self.api.tags['v1.0.1']['object']['sha'] = 'b' * 40
            return asset
        with patch.object(self.api, 'upload_manifest', side_effect=upload):
            with self.assertRaisesRegex(ValueError, 'source tag mismatch'):
                r.publish(self.api, p['number'])
        self.assertTrue(self.api.records['v1.0.1']['draft'])

    def test_asset_conflict_prevents_upload(self):
        _, _, p = self.prepare()
        self.api.assets[10] = {'id': 10, 'name': 'release-manifest.json'}
        with patch.object(self.api, 'upload_manifest') as upload:
            with self.assertRaisesRegex(ValueError, 'already contains assets'):
                r.publish(self.api, p['number'])
            upload.assert_not_called()
        self.assertTrue(self.api.records['v1.0.1']['draft'])

    def test_published_asset_corruption_reports_partial_publication(self):
        _, _, p = self.prepare()
        original = self.api.request
        def request(path, method='GET', data=None, missing=False):
            result = original(path, method, data, missing)
            if method == 'PATCH' and data == {'draft': False}:
                self.api.assets[10]['size'] = 0
            return result
        with patch.object(self.api, 'request', side_effect=request):
            with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                r.publish(self.api, p['number'])
        self.assertFalse(self.api.records['v1.0.1']['draft'])
        with self.assertRaisesRegex(ValueError, 'Duplicate Git tag'):
            r.publish(self.api, p['number'])


class ManifestTransport(unittest.TestCase):
    def test_safe_registry_digest_paths_and_https_references_remain_valid(self):
        for ref in ['example.azurecr.io/service@sha256:' + 'f' * 64,
                    'localhost:5000/service@sha256:' + 'f' * 64,
                    'registry.example:5000/team/service@sha256:' + 'f' * 64,
                    'registry.terraform.io/hashicorp/azurerm', 'docs/sbom.json',
                    './docs/sbom.json', 'migrations/001.sql', 'https://storage.example/sbom.json']:
            with self.subTest(reference=ref):
                m.reference(ref)

    def test_credentials_and_queries_rejected_without_explicit_url_scheme(self):
        for ref in ['//user:token@storage.example/sbom.json?sig=secret',
                    '//user:token@storage.example/sbom.json', 'sbom.json?sig=secret',
                    'fixture-token@storage.example/sbom.json',
                    'user:token@storage.example/sbom.json', 'https://[fixture-secret]/sbom.json']:
            with self.subTest(reference=ref):
                with self.assertRaises(ValueError) as caught:
                    m.reference(ref)
                self.assertNotIn('fixture-secret', str(caught.exception))

    def test_input_urls_never_receive_credentials(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'example/service', 'GH_TOKEN': 'fake-token'}):
            api = r.GitHub()
        for url in ['https://evil.test/upload', 'https://api.github.com/repos/example/service.evil/statuses',
                    'https://uploads.github.com@evil.test/repos/example/service/releases/42/assets?name=release-manifest.json']:
            with self.subTest(url=url), patch.object(r.urllib.request.OpenerDirector, 'open') as request:
                with self.assertRaisesRegex(ValueError, 'Untrusted authenticated URL'):
                    api.json_request(url, 'POST', b'{}')
                request.assert_not_called()
    def test_upload_uses_fixed_github_host_and_native_token(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'example/service', 'GH_TOKEN': 'fake-token'}):
            api = r.GitHub()
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"id":10}'
        with patch.object(r.urllib.request.OpenerDirector, 'open', return_value=response) as request:
            self.assertEqual({'id': 10}, api.upload_manifest(42, b'{"schema_version":1}'))
        req = request.call_args.args[0]
        self.assertEqual('https://uploads.github.com/repos/example/service/releases/42/assets?name=release-manifest.json', req.full_url)
        self.assertEqual('Bearer fake-token', req.get_header('Authorization'))
        self.assertEqual(b'{"schema_version":1}', req.data)

    def test_authenticated_redirect_is_rejected(self):
        handler = r.NoRedirect()
        request = r.urllib.request.Request('https://uploads.github.com/file', headers={'Authorization': 'Bearer fake'})
        self.assertIsNone(handler.redirect_request(request, None, 302, 'Found', {}, 'https://evil.test/file'))

    def test_check_pagination_preserves_response_envelope(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'example/service', 'GH_TOKEN': 'fake-token'}):
            api = r.GitHub()
        with patch.object(api, 'request', side_effect=[{'check_runs': list(range(100))}, {'check_runs': [100]}]) as read:
            self.assertEqual(list(range(101)), api.pages('/commits/' + 'a' * 40 + '/check-runs?filter=all', key='check_runs'))
        self.assertTrue(read.call_args.args[0].endswith('&per_page=100&page=2'))
