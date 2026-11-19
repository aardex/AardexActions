import base64
import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'stewards' / 'release-readiness'))
import collect_evidence as ce  # noqa: E402

REPO = 'aardex/example'
HEAD = 'a' * 40
MERGE = 'b' * 40
POLICY = 'c' * 40


def content(text):
    return {'content': base64.b64encode(text.encode()).decode()}


class FakeApi:
    """In-memory GitHub API keyed by request path; missing paths are 404."""

    def __init__(self, routes, fail=()):
        self.routes, self.fail, self.calls = routes, set(fail), []

    def _lookup(self, path):
        self.calls.append(path)
        if path in self.fail:
            raise RuntimeError('HTTP 502: upstream')
        if path not in self.routes:
            raise ce.NotFound(path)
        return self.routes[path]

    def get(self, path):
        return self._lookup(path)

    def pages(self, path):
        return self._lookup(path)

    def raw(self, path):
        return self._lookup(path)


def candidate(**extra):
    doc = {'version': '1.2.0', 'previous_version': '1.1.0', 'base_sha': HEAD, 'date': '2026-11-01',
           'changes': [{'number': 7, 'sha': 'd' * 40, 'title': 'feat(EN-46): add thing'}]}
    doc.update(extra)
    return json.dumps(doc)


def routes(merged=True, cand=None, manifest=None, workflow='uses: aardex/AardexActions/release-management@' + 'e' * 40):
    pr = {'number': 9, 'title': 'chore(release): 1.2.0', 'state': 'closed' if merged else 'open', 'draft': False,
          'user': {'login': 'github-actions[bot]', 'type': 'Bot'}, 'head': {'ref': 'release/managed', 'sha': HEAD},
          'base': {'ref': 'main'}, 'merged': merged, 'merge_commit_sha': MERGE, 'merged_by': {'login': 'alice'},
          'merged_at': '2026-11-02T00:00:00Z', 'html_url': 'https://github.com/aardex/example/pull/9'}
    r = {
        f'repos/{REPO}/pulls/9': pr,
        f'repos/{REPO}/pulls/9/reviews?per_page=100': [[
            {'user': {'login': 'alice', 'type': 'User'}, 'state': 'APPROVED', 'commit_id': 'f' * 40},
            {'user': {'login': 'alice', 'type': 'User'}, 'state': 'COMMENTED', 'commit_id': HEAD},
            {'user': {'login': 'bob', 'type': 'User'}, 'state': 'APPROVED', 'commit_id': HEAD},
        ]],
        f'repos/{REPO}/contents/version.txt?ref={HEAD}': content('1.2.0\n'),
        f'repos/{REPO}/contents/CHANGELOG.md?ref={HEAD}': content('# History\n\n## [1.2.0]\n\n## [1.1.0]\n'),
        f'repos/{REPO}/contents/.release/candidate.json?ref={HEAD}': content(cand or candidate()),
        f'repos/{REPO}/contents/.release/baseline.json?ref={HEAD}': content('{"version":"1.0.0","sha":"' + HEAD + '"}'),
        f'repos/{REPO}/contents/.github/workflows?ref={HEAD}': [{'name': 'release.yml', 'path': '.github/workflows/release.yml'},
                                                              {'name': 'notes.txt', 'path': '.github/workflows/notes.txt'}],
        f'repos/{REPO}/contents/.github/workflows/release.yml?ref={HEAD}': content(workflow),
        f'repos/{REPO}/commits/{HEAD}/status': {'statuses': [{'context': 'release-tests', 'state': 'success',
                                                              'creator': {'login': 'github-actions[bot]'}}]},
        f'repos/{REPO}/commits/{HEAD}/check-runs?per_page=100': [{'check_runs': [
            {'name': 'consumer-checks', 'status': 'completed', 'conclusion': 'success', 'app': {'slug': 'github-actions', 'id': 15368}}]}],
        f'repos/{REPO}/commits/{MERGE}/status': {'statuses': []},
        f'repos/{REPO}/commits/{MERGE}/check-runs?per_page=100': [{'check_runs': []}],
        f'repos/{REPO}/pulls/7/files?per_page=100': [[{'filename': 'db/migrations/001.sql'}, {'filename': 'README.md'}]],
    }
    if manifest is not None:
        data = json.dumps(manifest).encode()
        r[f'repos/{REPO}/releases/tags/v1.2.0'] = {
            'name': 'Example 1.2.0', 'draft': False, 'prerelease': False, 'immutable': True,
            'assets': [{'id': 5, 'name': 'release-manifest.json', 'size': len(data), 'state': 'uploaded',
                        'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}]}
        r[f'repos/{REPO}/git/ref/tags/v1.2.0'] = {'object': {'type': 'commit', 'sha': MERGE}}
        r[f'repos/{REPO}/releases/assets/5'] = data
    return r


MANIFEST = {'schema_version': 1, 'release': {'tag': 'v1.2.0', 'sha': MERGE},
            'release_pr': {'number': 9, 'head_sha': HEAD, 'merge_sha': MERGE},
            'changes': [{'number': 7}], 'jira_keys': ['EN-46'],
            'artifacts': {'state': 'missing', 'reason': 'not collected'},
            'migrations': {'state': 'not_applicable', 'reason': 'none'},
            'checks': [{'name': 'release-tests', 'kind': 'github-status', 'checked_sha': HEAD,
                        'state': 'available', 'outcome': {'status': 'completed', 'conclusion': 'success'}}]}


class CollectTests(unittest.TestCase):
    def test_merged_release_pr_with_manifest(self):
        facts = ce.collect(FakeApi(routes(manifest=MANIFEST)), REPO, pr=9)
        files = facts['release_files_at_head']
        self.assertEqual(files['version_txt'], '1.2.0')
        self.assertEqual(files['changelog_headings'], ['1.2.0', '1.1.0'])
        self.assertEqual(files['candidate']['version'], '1.2.0')
        # Latest non-comment review per reviewer; alice's approval is on an older head.
        self.assertEqual([(r['reviewer'], r['on_head']) for r in facts['reviews']], [('alice', False), ('bob', True)])
        self.assertEqual(facts['workflow_pins'], {'.github/workflows/release.yml': {
            'release_management': ['e' * 40], 'gate_policy_sha': []}})
        self.assertEqual(facts['included_prs'][0]['jira_keys'], ['EN-46'])
        self.assertIn('db/migrations/001.sql', facts['included_prs'][0]['files'])
        manifest = facts['release']['manifest']
        self.assertTrue(manifest['digest_matches_github'])
        self.assertEqual(manifest['sections']['migrations'], 'not_applicable')
        self.assertIsNone(manifest['sections']['sbom'])
        self.assertEqual(facts['release']['tag_sha'], MERGE)
        self.assertIn('gate_snapshot in candidate.json (no gate policy pinned for this candidate)', facts['missing'])
        self.assertEqual(facts['api_errors'], [])

    def test_tag_only_resolves_release_pr_from_manifest(self):
        facts = ce.collect(FakeApi(routes(manifest=MANIFEST)), REPO, tag='v1.2.0')
        self.assertEqual(facts['release_pr']['number'], 9)

    def test_missing_manifest_and_unpublished_release_are_reported_not_invented(self):
        api = FakeApi(routes(merged=False))
        facts = ce.collect(api, REPO, pr=9)
        self.assertIsNone(facts['release'])
        self.assertIsNone(facts['release_pr']['merge_sha'])
        self.assertEqual(len(facts['checks']), 1)
        self.assertFalse(any('releases/tags' in call for call in api.calls))  # open PR: no release lookup

    def test_published_release_without_manifest_asset(self):
        r = routes()
        r[f'repos/{REPO}/releases/tags/v1.2.0'] = {'assets': [], 'immutable': True}
        r[f'repos/{REPO}/git/ref/tags/v1.2.0'] = {'object': {'type': 'commit', 'sha': MERGE}}
        facts = ce.collect(FakeApi(r), REPO, pr=9)
        self.assertIsNone(facts['release']['manifest'])
        self.assertIn('release-manifest.json on release v1.2.0', facts['missing'])

    def test_api_failure_is_an_error_not_absence(self):
        api = FakeApi(routes(), fail={f'repos/{REPO}/commits/{HEAD}/check-runs?per_page=100'})
        facts = ce.collect(api, REPO, pr=9)
        self.assertEqual(facts['checks'][0]['check_runs'], [])
        self.assertEqual(facts['api_errors'][0]['what'], f'check-runs@{HEAD[:12]}')
        self.assertNotIn(f'check-runs@{HEAD[:12]}', facts['missing'])

    def test_pinned_gate_policy_and_snapshot(self):
        cand = candidate(gate_snapshot={'policy_sha': POLICY, 'source_sha': MERGE, 'checks': []})
        r = routes(cand=cand, workflow=f'gate-policy-sha: {POLICY}\n')
        r[f'repos/{REPO}/contents/.release/gates.json?ref={POLICY}'] = content('{"workflows":[]}')
        facts = ce.collect(FakeApi(r), REPO, pr=9)
        self.assertEqual(facts['pinned_gate_policies'], {POLICY: {'workflows': []}})
        self.assertFalse(any(m.startswith('gate_snapshot') for m in facts['missing']))

    def test_invalid_candidate_json_is_reported(self):
        facts = ce.collect(FakeApi(routes(cand='{not json')), REPO, pr=9)
        self.assertIsNone(facts['release_files_at_head']['candidate'])
        self.assertEqual(facts['api_errors'][0]['what'], 'candidate.json')

    def test_jira_pattern_matches_release_engine(self):
        sys.path.insert(0, str(ROOT / 'release-management'))
        import manifest
        self.assertEqual(ce.JIRA.pattern, manifest.JIRA.pattern)


if __name__ == '__main__':
    unittest.main()
