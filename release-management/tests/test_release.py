"""Only disposable local Git repositories and in-memory APIs; no credentials/network."""
import json
import hashlib
import io
import os
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import release as r


def cmd(*args, data=None):
    return subprocess.check_output(args, input=data, text=True).strip()


class FakeGitHub:
    repo = 'example/service'
    config = r.Config()

    def __init__(self):
        self.prs = []
        self.tags = {}
        self.records = {}
        self.statuses = []
        self.mutations = []
        self.trees = {}
        self.immutable = True
        self.assets = {}
        self.manifest_payload = None

    def pages(self, path, key=None):
        if path.endswith('/reviews'):
            p = self.pr(int(path.split('/')[2]))
            return [{'state': 'APPROVED', 'commit_id': p['head']['sha'],
                     'user': {'login': 'reviewer', 'type': 'User'}}]
        if path.endswith('/statuses'):
            sha = path.split('/')[2]
            return [{'id': i + 1, 'state': state, 'context': context}
                    for i, (target, state, context) in enumerate(self.statuses) if target == sha]
        if '/check-runs?' in path:
            assert key == 'check_runs'
            return []
        if path.startswith('/releases/') and path.endswith('/assets'):
            return list(self.assets.values())
        if path.startswith('/commits/'):
            sha = path.split('/')[2]
            return [p for p in self.prs if p.get('merge_commit_sha') == sha]
        if path.startswith('/pulls?'):
            return [p for p in self.prs if not p['merged']]
        raise AssertionError(path)

    def upload_manifest(self, release_id, payload):
        assert self.records[next(iter(self.records))]['draft'] is True
        assert not self.assets
        self.manifest_payload = payload
        asset = {'id': 10, 'name': 'release-manifest.json', 'state': 'uploaded',
                 'size': len(payload), 'digest': 'sha256:' + hashlib.sha256(payload).hexdigest()}
        self.assets[10] = asset
        self.mutations.append(('upload-manifest', 'POST', None))
        return asset

    def pr(self, number):
        return next(p for p in self.prs if p['number'] == number)

    def status(self, sha, state, description, context='release-inputs'):
        self.statuses.append((sha, state, context))

    def request(self, path, method='GET', data=None, missing=False):
        if method != 'GET':
            self.mutations.append((path, method, data))
        if path == '':
            return {'default_branch': self.config.trunk}
        if path == '/actions/runs/100/attempts/1':
            return {'id': 100, 'run_attempt': 1, 'head_sha': r.git('rev-parse', self.config.trunk),
                    'path': '.github/workflows/release.yml',
                    'repository': {'full_name': self.repo}, 'status': 'in_progress', 'conclusion': None}
        if path.startswith('/releases/assets/'):
            return self.assets[int(path.rsplit('/', 1)[1])]
        if path == '/branches/' + r.quote(self.config.trunk, safe=''):
            return {'commit': {'sha': r.git('rev-parse', self.config.trunk)}}
        if path.startswith('/git/ref/tags/'):
            return self.tags.get(path.rsplit('/', 1)[1])
        if path.startswith('/releases/tags/'):
            return self.records.get(path.rsplit('/', 1)[1])
        if path == '/git/ref/heads/' + self.config.branch:
            result = subprocess.run(['git', 'rev-parse', '--verify', self.config.branch], capture_output=True, text=True)
            return {'object': {'sha': result.stdout.strip()}} if result.returncode == 0 else None
        if path == '/git/trees':
            with tempfile.TemporaryDirectory() as temp:
                env = dict(os.environ, GIT_INDEX_FILE=temp + '/index')
                subprocess.run(['git', 'read-tree', data['base_tree']], env=env, check=True)
                for entry in data['tree']:
                    blob = cmd('git', 'hash-object', '-w', '--stdin', data=entry['content'])
                    subprocess.run(['git', 'update-index', '--add', '--cacheinfo', '100644', blob, entry['path']], env=env, check=True)
                sha = subprocess.check_output(['git', 'write-tree'], env=env, text=True).strip()
            return {'sha': sha}
        if path == '/git/commits':
            args = ['git', 'commit-tree', data['tree']]
            for parent in data['parents']:
                args.extend(['-p', parent])
            return {'sha': cmd(*args, data=data['message'])}
        if path == '/git/refs':
            ref = data['ref']
            if ref.startswith('refs/tags/'):
                name = ref.split('/')[-1]
                if name in self.tags:
                    raise ValueError('Duplicate ref')
                self.tags[name] = {'object': {'sha': data['sha'], 'type': 'commit'}}
            else:
                cmd('git', 'update-ref', ref, data['sha'])
            return {}
        if path == '/git/refs/heads/' + self.config.branch:
            assert data['force'] is False
            old = r.git('rev-parse', self.config.branch)
            subprocess.run(['git', 'merge-base', '--is-ancestor', old, data['sha']], check=True)
            cmd('git', 'update-ref', 'refs/heads/' + self.config.branch, data['sha'])
            return {}
        if path == '/releases':
            record = dict(data, id=1)
            self.records[data['tag_name']] = record
            return record
        if path == '/releases/1':
            record = next(iter(self.records.values()))
            record.update(data, immutable=self.immutable, html_url='https://github.com/example/service/releases/tag/' + record['tag_name'])
            return record
        if path == '/pulls':
            p = {'number': len(self.prs) + 1, 'title': data['title'], 'body': data['body'],
                 'merged': False, 'base': {'ref': self.config.trunk, 'sha': r.git('rev-parse', self.config.trunk)},
                 'head': {'ref': self.config.branch, 'sha': r.git('rev-parse', self.config.branch), 'repo': {'full_name': self.repo}},
                 'user': {'login': 'github-actions[bot]', 'type': 'Bot'}}
            self.prs.append(p)
            cmd('git', 'update-ref', f'refs/pull/{p["number"]}/head', p['head']['sha'])
            return p
        if path.startswith('/pulls/'):
            p = self.pr(int(path.split('/')[2]))
            p.update(data)
            p['head']['sha'] = r.git('rev-parse', self.config.branch)
            p['base']['sha'] = r.git('rev-parse', self.config.trunk)
            cmd('git', 'update-ref', f'refs/pull/{p["number"]}/head', p['head']['sha'])
            return p
        raise AssertionError((path, method))


class Fixture(unittest.TestCase):
    def setUp(self):
        # Mock only the Git whitespace check; all candidate mechanics run against
        # disposable real Git and an in-memory GitHub API.
        self.tooling = patch.object(r, 'check_tooling', create=True)
        self.check_tooling = self.tooling.start()
        self.addCleanup(self.tooling.stop)
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        self.network = patch.object(r.urllib.request, 'urlopen', side_effect=AssertionError('Network forbidden in fixture'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.opener = patch.object(r.urllib.request.OpenerDirector, 'open', side_effect=AssertionError('Network forbidden in fixture'))
        self.opener.start()
        self.addCleanup(self.opener.stop)
        clean_env = {k: v for k, v in os.environ.items() if k not in
                     ('GH_TOKEN', 'GITHUB_TOKEN', 'GITHUB_OUTPUT') and not k.startswith('RELEASE_')}
        clean_env.update(RELEASE_IMMUTABILITY_CONFIRMED='true', GIT_CONFIG_GLOBAL='/dev/null',
                         GIT_CONFIG_NOSYSTEM='1', GITHUB_RUN_ID='100', GITHUB_RUN_ATTEMPT='1',
                         GITHUB_WORKFLOW_REF='example/service/.github/workflows/release.yml@refs/heads/main',
                         GITHUB_WORKFLOW_SHA='a' * 40)
        self.env = patch.dict(os.environ, clean_env, clear=True)
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.temp.name)
        cmd('git', '-c', 'init.templateDir=', 'init', '-q', '-b', 'main')
        cmd('git', 'config', 'core.autocrlf', 'false')
        cmd('git', 'config', 'core.hooksPath', '/dev/null')
        cmd('git', 'config', 'commit.gpgsign', 'false')
        cmd('git', 'config', 'user.email', 'fixture@example.invalid')
        cmd('git', 'config', 'user.name', 'Fixture')
        cmd('git', 'remote', 'add', 'origin', self.temp.name)
        Path('version.txt').write_text('1.0.0\n')
        Path('CHANGELOG.md').write_text('# History\n\n## [1.0.0] 2025-09-04\n\n- Original historical content\n')
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'Historical baseline')
        initial = r.git('rev-parse', 'HEAD')
        Path('.release').mkdir()
        Path('.release/baseline.json').write_text(json.dumps({'sha': initial, 'version': '1.0.0'}))
        self.api = FakeGitHub()
        self.change('chore(ci): install release baseline')

    def tearDown(self):
        os.chdir(self.old)
        self.temp.cleanup()
        self.env.stop()

    def change(self, title):
        Path('source.txt').write_text(title + str(len(self.api.prs)))
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'Intermediate developer message need not be conventional')
        sha = r.git('rev-parse', 'HEAD')
        p = {'number': len(self.api.prs) + 1, 'title': title, 'merged': True,
             'merged_at': '2026-10-05T10:00:00Z', 'merge_commit_sha': sha,
             'head': {'ref': 'feature/test'}, 'base': {'ref': self.api.config.trunk}}
        self.api.prs.append(p)
        return sha

    def release_pr(self):
        return next(p for p in self.api.prs if not p['merged'])

    def merge_release(self):
        p = self.release_pr()
        base = r.git('rev-parse', 'HEAD')
        for path in self.api.config.files:
            Path(path).write_text(r.read(r.git('rev-parse', self.api.config.branch), path))
        cmd('git', 'add', *sorted(self.api.config.files))
        tree = r.git('write-tree')
        sha = cmd('git', 'commit-tree', tree, '-p', base, data=p['title'] + '\n\nHuman squash merge')
        cmd('git', 'reset', '--hard', sha)
        p.update(merged=True, merged_at='2026-10-05T11:00:00Z', merge_commit_sha=sha,
                 merged_by={'type': 'User'})
        return p, sha

    def test_create_update_same_pr_and_highest_bump(self):
        self.change('fix: correct policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        number, old = p['number'], p['head']['sha']
        self.assertEqual('chore(release): 1.0.1', p['title'])
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertEqual(old, self.release_pr()['head']['sha'])
        self.change('feat: new login')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertEqual(number, self.release_pr()['number'])
        self.assertEqual('chore(release): 1.1.0', p['title'])
        self.assertEqual(1, len([p for p in self.api.prs if not p['merged']]))
        self.assertEqual('1.1.0\n', r.read(p['head']['sha'], 'version.txt'))
        history = r.read(p['head']['sha'], 'CHANGELOG.md')
        self.assertIn('fix: correct policy', history)
        self.assertIn('feat: new login', history)
        self.assertTrue(history.endswith('## [1.0.0] 2025-09-04\n\n- Original historical content\n'))
        self.assertEqual('1.0.0\n', Path('version.txt').read_text())
        self.assertEqual('success', self.api.statuses[-1][1])

    def test_no_bump_no_pr_or_branch(self):
        self.change('docs: clarify setup')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertFalse(self.api.mutations)
        self.assertFalse([p for p in self.api.prs if not p['merged']])

    def test_reproducible_candidate(self):
        sha = self.change('feat!: change login contract')
        a = r.candidate(self.api, sha)
        b = r.candidate(self.api, sha)
        self.assertEqual(a, b)
        self.assertEqual('2.0.0', a['metadata']['version'])
        self.assertEqual(sha, a['metadata']['base_sha'])

    def test_duplicate_candidates_fail(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.api.prs.append(dict(self.release_pr(), number=999))
        with self.assertRaisesRegex(ValueError, 'Competing'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_stale_candidate_cannot_release(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.change('docs: new docs')
        p, _ = self.merge_release()
        with self.assertRaisesRegex(ValueError, 'Non-reproducible'):
            r.preflight(self.api, p['number'])

    def test_approved_exact_sha_and_duplicate_tag(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, sha = self.merge_release()
        wanted, actual = r.preflight(self.api, p['number'])
        self.assertEqual(sha, actual)
        self.assertEqual('1.0.1', wanted['metadata']['version'])
        self.api.tags['v1.0.1'] = {'object': {'type': 'commit', 'sha': sha}}
        with self.assertRaisesRegex(ValueError, 'Duplicate Git tag'):
            r.preflight(self.api, p['number'])

    def test_inconsistent_version_fails(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, _ = self.merge_release()
        Path('version.txt').write_text('9.9.9\n')
        cmd('git', 'add', 'version.txt')
        cmd('git', 'commit', '--amend', '--no-edit', '-q')
        p['merge_commit_sha'] = r.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'version.txt'):
            r.preflight(self.api, p['number'])

    def test_ordinary_merge_and_bot_merge_never_publish(self):
        with self.assertRaisesRegex(ValueError, 'merged Release PR'):
            r.approved(self.api, self.api.prs[0]['number'])
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, _ = self.merge_release()
        p['merged_by']['type'] = 'Bot'
        with self.assertRaisesRegex(ValueError, 'human'):
            r.preflight(self.api, p['number'])

    def test_recovery_uses_merge_even_from_later_trunk(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, _ = self.merge_release()
        self.change('docs: subsequent merge')
        _, sha = r.preflight(self.api, p['number'])
        self.assertEqual(p['merge_commit_sha'], sha)

    def pending_publication(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        return self.merge_release()

    def complete_publication(self, sha):
        self.api.tags['v1.0.1'] = {'object': {'type': 'commit', 'sha': sha}}
        self.api.records['v1.0.1'] = {'tag_name': 'v1.0.1', 'target_commitish': sha,
                                    'draft': False, 'prerelease': False, 'immutable': True}

    def test_approved_release_without_records_defers_successfully(self):
        self.pending_publication()
        before = len(self.api.mutations), len(self.api.statuses)
        with redirect_stdout(io.StringIO()) as output:
            r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertEqual('Previous approved release is awaiting publication; proposal deferred\n', output.getvalue())
        self.assertEqual(before, (len(self.api.mutations), len(self.api.statuses)))
        self.assertFalse([p for p in self.api.prs if not p['merged']])

    def test_normal_pr_during_publication_also_defers(self):
        self.pending_publication()
        self.change('feat: follow up')
        before = len(self.api.mutations)
        with redirect_stdout(io.StringIO()) as output:
            r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertIn('awaiting publication; proposal deferred', output.getvalue())
        self.assertEqual(before, len(self.api.mutations))
        self.assertFalse([p for p in self.api.prs if not p['merged']])

    def test_completed_publication_retries_with_intervening_pr(self):
        _, released_sha = self.pending_publication()
        intervening_sha = self.change('feat: follow up')
        r.propose(self.api, intervening_sha)
        self.complete_publication(released_sha)
        r.propose(self.api, intervening_sha)
        p = self.release_pr()
        metadata = json.loads(r.read(p['head']['sha'], '.release/candidate.json'))
        self.assertEqual('1.1.0', metadata['version'])
        self.assertEqual([{'number': p['number'] - 1, 'title': 'feat: follow up',
                           'sha': intervening_sha}], metadata['changes'])
        self.assertIn('feat: follow up', p['body'])
        self.assertNotIn('fix: policy', p['body'])

    def test_tag_only_partial_publication_fails(self):
        _, sha = self.pending_publication()
        self.api.tags['v1.0.1'] = {'object': {'type': 'commit', 'sha': sha}}
        with self.assertRaisesRegex(ValueError, 'Previous GitHub Release missing'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_release_only_publication_fails(self):
        _, sha = self.pending_publication()
        self.api.records['v1.0.1'] = {'tag_name': 'v1.0.1', 'target_commitish': sha,
                                    'draft': False, 'prerelease': False, 'immutable': True}
        with self.assertRaisesRegex(ValueError, 'Previous release tag missing'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_wrong_tag_sha_fails(self):
        _, sha = self.pending_publication()
        self.complete_publication(sha)
        self.api.tags['v1.0.1']['object']['sha'] = 'a' * 40
        with self.assertRaisesRegex(ValueError, 'Previous release tag missing or inconsistent'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_draft_or_conflicting_release_record_fails(self):
        _, sha = self.pending_publication()
        for changes in ({'draft': True}, {'prerelease': True}, {'immutable': False},
                        {'tag_name': 'v9.9.9'}, {'target_commitish': 'a' * 40}):
            with self.subTest(changes=changes):
                self.complete_publication(sha)
                self.api.records['v1.0.1'].update(changes)
                with self.assertRaisesRegex(ValueError, 'Previous GitHub Release'):
                    r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_immutable_bootstrap_with_main_creation_hint_uses_exact_tag(self):
        _, sha = self.pending_publication()
        self.complete_publication(sha)
        self.api.records['v1.0.1']['target_commitish'] = 'main'
        self.change('chore(ci): simplify publication boundary')
        self.assertIsNone(r.candidate(self.api, r.git('rev-parse', 'HEAD')))
        # Never resolve the moving branch as source or tolerate the wrong tag.
        self.api.tags['v1.0.1']['object']['sha'] = r.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'Previous release tag missing or inconsistent'):
            r.candidate(self.api, r.git('rev-parse', 'HEAD'))

    def test_missing_records_do_not_accept_arbitrary_metadata(self):
        self.pending_publication()
        self.api.prs.pop()  # No corresponding approved merged Release PR.
        with self.assertRaisesRegex(ValueError, 'approved Release PR'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_pending_version_disagreement_fails(self):
        self.pending_publication()
        Path('version.txt').write_text('9.9.9\n')
        self.change('chore: unauthorized version edit')
        with self.assertRaisesRegex(ValueError, 'Version authority differs'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_pending_metadata_must_be_reproducible(self):
        p, _ = self.pending_publication()
        Path('CHANGELOG.md').write_text(Path('CHANGELOG.md').read_text() + '\nFabricated notes\n')
        cmd('git', 'add', 'CHANGELOG.md')
        cmd('git', 'commit', '--amend', '--no-edit', '-q')
        p['merge_commit_sha'] = r.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'Non-reproducible Release PR file: CHANGELOG.md'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_pending_metadata_requires_exact_head_approval(self):
        self.pending_publication()
        original_pages = self.api.pages
        def stale_approval(path):
            if path.endswith('/reviews'):
                return [{'state': 'APPROVED', 'commit_id': 'a' * 40,
                         'user': {'login': 'reviewer', 'type': 'User'}}]
            return original_pages(path)
        with patch.object(self.api, 'pages', side_effect=stale_approval):
            with self.assertRaisesRegex(ValueError, 'exact final head'):
                r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_exact_generated_markdown_entry(self):
        sha = self.change('fix: correct policy')
        wanted = r.candidate(self.api, sha)
        expected = f'- `fix: correct policy` ([#2](https://github.com/example/service/pull/2), source `{sha}`)\n'
        self.assertEqual(expected, next(line + '\n' for line in wanted['notes'].splitlines()
                                       if 'fix: correct policy' in line))
        self.assertIn(expected, wanted['files']['CHANGELOG.md'])

    def test_candidate_statuses_follow_exact_head_checks(self):
        self.change('fix: policy')
        def assert_not_ready(*args):
            self.assertFalse(any(state == 'success' for _, state, _ in self.api.statuses))
        self.check_tooling.side_effect = assert_not_ready
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        head = self.release_pr()['head']['sha']
        self.check_tooling.assert_called_once_with(r.git('rev-parse', 'HEAD'), head)
        for context in ['release-inputs', 'release-tests']:
            self.assertEqual(['pending', 'success'],
                             [state for sha, state, name in self.api.statuses if sha == head and name == context])
        self.api.statuses.clear()
        self.change('feat: next candidate input')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        updated_head = self.release_pr()['head']['sha']
        self.assertNotEqual(head, updated_head)
        self.assertTrue(all(sha == updated_head for sha, _, _ in self.api.statuses))
        self.assertEqual({'release-inputs', 'release-tests'},
                         {context for _, state, context in self.api.statuses if state == 'success'})

    def test_failed_tooling_never_marks_candidate_ready(self):
        self.change('fix: policy')
        self.check_tooling.side_effect = subprocess.CalledProcessError(1, 'fixture-check')
        with self.assertRaises(subprocess.CalledProcessError):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))
        head = self.release_pr()['head']['sha']
        self.assertFalse(any(state == 'success' for _, state, _ in self.api.statuses))
        self.assertEqual({'release-inputs', 'release-tests'},
                         {context for sha, state, context in self.api.statuses if sha == head and state == 'failure'})

    def test_changed_head_during_checks_is_not_marked_ready(self):
        self.change('fix: policy')
        def move_head(*args):
            self.release_pr()['head']['sha'] = 'a' * 40
        self.check_tooling.side_effect = move_head
        with self.assertRaisesRegex(ValueError, 'Candidate head or trunk changed'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertFalse(any(state == 'success' for _, state, _ in self.api.statuses))

    def test_direct_trunk_commit_fails(self):
        self.change('fix: policy')
        self.api.prs.pop()
        with self.assertRaisesRegex(ValueError, 'exactly one merged PR'):
            r.candidate(self.api, r.git('rev-parse', 'HEAD'))

    def test_github_only_source_tag_release_mapping(self):
        self.change('fix: correct policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, sha = self.merge_release()
        # No Azure configuration or evidence file exists in this fixture.
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(os.environ, {'RELEASE_IMMUTABILITY_CONFIRMED': 'true',
                    'GITHUB_RUN_ID': '100', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_WORKFLOW_REF': 'example/service/.github/workflows/release.yml@refs/heads/main',
                    'GITHUB_WORKFLOW_SHA': 'a' * 40}):
                r.publish(self.api, p['number'])
        self.assertEqual(sha, self.api.tags['v1.0.1']['object']['sha'])
        record = self.api.records['v1.0.1']
        self.assertEqual(self.api.config.trunk, record['target_commitish'])
        self.assertFalse(record['draft'])
        self.assertFalse(record['prerelease'])
        self.assertTrue(record['immutable'])
        self.assertEqual('Release 1.0.1', record['name'])
        for item in [sha, '1.0.1', 'v1.0.1', f'Release PR #{p["number"]}', 'fix: correct policy']:
            self.assertIn(item, record['body'])
        self.assertEqual(r.candidate(self.api, p['base']['sha'])['notes'],
                         record['body'].split('\n### Release identity')[0])
        self.assertNotIn('Image:', record['body'])
        self.assertNotIn('Digest:', record['body'])
        with self.assertRaisesRegex(ValueError, 'Duplicate Git tag'):
            r.publish(self.api, p['number'])
        self.change('feat: next feature')
        wanted = r.candidate(self.api, r.git('rev-parse', 'HEAD'))
        self.assertEqual('1.1.0', wanted['metadata']['version'])
        self.assertNotIn('fix: correct policy', wanted['notes'])

    def test_published_release_must_be_immutable(self):
        p, _ = self.pending_publication()
        self.api.immutable = False
        with self.assertRaisesRegex(ValueError, 'GitHub Release is not immutable'):
            r.publish(self.api, p['number'])
        with self.assertRaisesRegex(ValueError, 'Duplicate Git tag'):
            r.publish(self.api, p['number'])

    def test_published_identity_readback_must_agree(self):
        p, _ = self.pending_publication()
        original = self.api.request
        def conflicting_tag(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == '/releases/1':
                self.api.tags['v1.0.1']['object']['sha'] = 'a' * 40
            return result
        with patch.object(self.api, 'request', side_effect=conflicting_tag):
            with self.assertRaisesRegex(ValueError, 'Published release identity'):
                r.publish(self.api, p['number'])

    def test_partial_tag_creation_failure_stays_fail_closed(self):
        p, _ = self.pending_publication()
        original = self.api.request
        def fail_release(path, *args, **kwargs):
            if path == '/releases':
                raise RuntimeError('Fixture GitHub outage')
            return original(path, *args, **kwargs)
        with patch.object(self.api, 'request', side_effect=fail_release):
            with self.assertRaisesRegex(RuntimeError, 'Fixture GitHub outage'):
                r.publish(self.api, p['number'])
        self.assertIn('v1.0.1', self.api.tags)
        self.assertFalse(self.api.records)
        with self.assertRaisesRegex(ValueError, 'Duplicate Git tag'):
            r.publish(self.api, p['number'])
        with self.assertRaisesRegex(ValueError, 'Previous GitHub Release'):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))

    def test_exact_three_file_candidate(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        self.assertEqual(self.api.config.files, set(r.git('diff', '--name-only', p['base']['sha'], p['head']['sha']).splitlines()))
        cmd('git', 'switch', '-q', self.api.config.branch)
        Path('unapproved.txt').write_text('Unexpected fourth file')
        cmd('git', 'add', 'unapproved.txt')
        cmd('git', 'commit', '-qm', 'extra candidate file')
        with self.assertRaisesRegex(ValueError, 'may change only'):
            r.validate_candidate(self.api, p['base']['sha'], r.git('rev-parse', 'HEAD'),
                                 p['title'], self.api.config.branch, self.api.repo)

    def test_approval_of_old_candidate_does_not_authorize_new_one(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, _ = self.merge_release()
        with patch.object(self.api, 'pages', return_value=[{'state': 'APPROVED',
                'commit_id': 'a' * 40, 'user': {'login': 'reviewer', 'type': 'User'}}]):
            with self.assertRaisesRegex(ValueError, 'exact final head'):
                r.approved(self.api, p['number'])

    def test_unconfirmed_immutability_blocks_publication(self):
        with patch.dict(os.environ, {'RELEASE_IMMUTABILITY_CONFIRMED': 'false'}):
            with self.assertRaisesRegex(ValueError, 'enable GitHub release immutability'):
                r.preflight(self.api, 1)

    def test_duplicate_github_release_fails_before_publication(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p, _ = self.merge_release()
        self.api.records['v1.0.1'] = {'draft': False}
        with self.assertRaisesRegex(ValueError, 'Duplicate GitHub Release'):
            r.preflight(self.api, p['number'])

    def test_release_merge_commit_is_rejected(self):
        self.change('fix: policy')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        sha = cmd('git', 'commit-tree', r.git('rev-parse', self.api.config.branch + '^{tree}'),
                  '-p', r.git('rev-parse', 'HEAD'), '-p', p['head']['sha'], data='Merge release PR')
        cmd('git', 'reset', '--hard', sha)
        p.update(merged=True, merge_commit_sha=sha, merged_by={'type': 'User'})
        with self.assertRaisesRegex(ValueError, 'squash-merged'):
            r.preflight(self.api, p['number'])

    def test_normal_pr_titles_and_release_authority_protection(self):
        base = r.git('rev-parse', 'HEAD')
        cmd('git', 'switch', '-qc', 'feature/test')
        Path('source.txt').write_text('Changed behavior')
        cmd('git', 'add', 'source.txt')
        cmd('git', 'commit', '-qm', 'Unconventional developer commit')
        head = r.git('rev-parse', 'HEAD')
        cmd('git', 'update-ref', 'refs/pull/99/head', head)
        p = {'number': 99, 'title': 'fix: correct behavior',
             'base': {'ref': 'main', 'sha': base}, 'head': {'sha': head, 'ref': 'feature/test'}}
        self.assertIsNone(r.validate_pr(self.api, p))
        p['title'] = 'Please release this'
        with self.assertRaisesRegex(ValueError, 'Conventional'):
            r.validate_pr(self.api, p)
        p['title'] = 'fix: correct behavior'
        Path('version.txt').write_text('1.0.1')
        cmd('git', 'add', 'version.txt')
        cmd('git', 'commit', '-qm', 'Manual version bump')
        p['head']['sha'] = r.git('rev-parse', 'HEAD')
        cmd('git', 'update-ref', 'refs/pull/99/head', p['head']['sha'])
        with self.assertRaisesRegex(ValueError, 'Normal PRs cannot alter'):
            r.validate_pr(self.api, p)


    def normal_pr(self):
        base = r.git('rev-parse', 'HEAD')
        cmd('git', 'switch', '-qc', 'feature/untrusted')
        Path('source.txt').write_text('Normal PR source')
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'Developer commit')
        head = r.git('rev-parse', 'HEAD')
        cmd('git', 'update-ref', 'refs/pull/99/head', head)
        p = {'number': 99, 'title': 'fix: behavior', 'merged': False,
             'base': {'ref': self.api.config.trunk, 'sha': base},
             'head': {'ref': 'feature/untrusted', 'sha': head}}
        self.api.prs.append(p)
        return p

    def test_normal_pr_receives_both_required_statuses(self):
        p = self.normal_pr()
        r.validate_statuses(self.api, p['number'])
        self.assertEqual([(p['head']['sha'], state, context)
                          for state in ('pending', 'success')
                          for context in ('release-inputs', 'release-tests')], self.api.statuses)

    def test_invalid_normal_pr_fails_both_statuses(self):
        p = self.normal_pr()
        p['title'] = 'Invalid title'
        with self.assertRaisesRegex(ValueError, 'Conventional'):
            r.validate_statuses(self.api, p['number'])
        self.assertEqual({'release-inputs', 'release-tests'},
                         {context for _, state, context in self.api.statuses if state == 'failure'})
        self.assertFalse(any(state == 'success' for _, state, _ in self.api.statuses))

    def test_all_protected_files_are_rejected_for_normal_pr(self):
        p = self.normal_pr()
        for path in self.api.config.files | {self.api.config.baseline_file}:
            with self.subTest(path=path):
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text('Untrusted release metadata')
                cmd('git', 'add', '.')
                cmd('git', 'commit', '-qm', 'Untrusted change')
                p['head']['sha'] = r.git('rev-parse', 'HEAD')
                cmd('git', 'update-ref', 'refs/pull/99/head', p['head']['sha'])
                with self.assertRaisesRegex(ValueError, 'Normal PRs cannot alter'):
                    r.validate_pr(self.api, p)

    def test_untrusted_pr_code_is_data_only(self):
        p = self.normal_pr()
        Path('release.py').write_text("from pathlib import Path\nPath('EXECUTED').write_text('unsafe')\n")
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'Malicious Python in PR')
        p['head']['sha'] = r.git('rev-parse', 'HEAD')
        cmd('git', 'update-ref', 'refs/pull/99/head', p['head']['sha'])
        cmd('git', 'switch', '-q', 'main')
        before = r.git('rev-parse', 'HEAD')
        original = r.subprocess.run
        with patch.object(r.subprocess, 'run', wraps=original) as run:
            r.validate_statuses(self.api, 99)
        self.assertEqual(before, r.git('rev-parse', 'HEAD'))
        self.assertFalse(Path('EXECUTED').exists())
        self.assertTrue(all(call.args[0][0] == 'git' for call in run.call_args_list))
        self.assertFalse(any('checkout' in call.args[0] or 'switch' in call.args[0]
                             for call in run.call_args_list))

    def test_managed_candidate_requires_native_bot(self):
        self.change('fix: behavior')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        p['user'] = {'login': 'human', 'type': 'User'}
        with self.assertRaisesRegex(ValueError, 'native Actions bot'):
            r.validate_pr(self.api, p)

    def test_managed_candidate_rejects_fork(self):
        self.change('fix: behavior')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        p['head']['repo']['full_name'] = 'attacker/service'
        with self.assertRaisesRegex(ValueError, 'native Actions bot'):
            r.validate_pr(self.api, p)

    def test_auto_merge_rejected(self):
        self.change('fix: behavior')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        p['auto_merge'] = {'enabled_by': {'type': 'User'}}
        with self.assertRaisesRegex(ValueError, 'auto-merge'):
            r.validate_pr(self.api, p)

    def test_latest_review_revokes_approval(self):
        p, _ = self.pending_publication()
        reviews = [{'state': 'APPROVED', 'commit_id': p['head']['sha'],
                    'user': {'login': 'human', 'type': 'User'}},
                   {'state': 'CHANGES_REQUESTED', 'commit_id': p['head']['sha'],
                    'user': {'login': 'human', 'type': 'User'}}]
        with patch.object(self.api, 'pages', return_value=reviews):
            with self.assertRaisesRegex(ValueError, 'exact final head'):
                r.approved(self.api, p['number'])

    def test_bot_approval_rejected(self):
        p, _ = self.pending_publication()
        reviews = [{'state': 'APPROVED', 'commit_id': p['head']['sha'],
                    'user': {'login': 'automation[bot]', 'type': 'Bot'}}]
        with patch.object(self.api, 'pages', return_value=reviews):
            with self.assertRaisesRegex(ValueError, 'exact final head'):
                r.approved(self.api, p['number'])

    def test_crlf_candidate_is_not_byte_identical(self):
        self.change('fix: behavior')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        p = self.release_pr()
        cmd('git', 'switch', '-q', self.api.config.branch)
        Path('version.txt').write_bytes(b'1.0.1\r\n')
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'CRLF tamper')
        with self.assertRaisesRegex(ValueError, 'Non-reproducible'):
            r.validate_candidate(self.api, p['base']['sha'], r.git('rev-parse', 'HEAD'),
                                 p['title'], self.api.config.branch, self.api.repo)

    def test_symlink_release_file_is_rejected(self):
        p = Path('version.txt')
        p.unlink()
        p.symlink_to('/outside/version.txt')
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'Symlink version')
        with self.assertRaisesRegex(ValueError, 'regular non-executable blob'):
            r.candidate(self.api, r.git('rev-parse', 'HEAD'))

    def test_publication_uses_approved_tree_not_only_merged_metadata(self):
        p, _ = self.pending_publication()
        cmd('git', 'switch', '-q', self.api.config.branch)
        Path('source.txt').write_text('Unapproved source content')
        cmd('git', 'add', '.')
        cmd('git', 'commit', '-qm', 'Different approved head')
        p['head']['sha'] = r.git('rev-parse', 'HEAD')
        cmd('git', 'update-ref', f'refs/pull/{p["number"]}/head', p['head']['sha'])
        cmd('git', 'switch', '-q', 'main')
        with self.assertRaisesRegex(ValueError, 'may change only'):
            r.preflight(self.api, p['number'])

    def test_custom_configuration_full_lifecycle(self):
        config = r.Config(trunk='trunk/stable', version_file='meta/VERSION',
                          changelog_file='meta/HISTORY.md', candidate_file='meta/candidate.json',
                          baseline_file='meta/bootstrap.json', branch='automation/candidate',
                          product='Example Service', tag_prefix='service-')
        cmd('git', 'branch', '-m', config.trunk)
        self.api.config = config
        for p in self.api.prs:
            p['base']['ref'] = config.trunk
        Path('meta').mkdir()
        Path('version.txt').rename(config.version_file)
        Path('CHANGELOG.md').rename(config.changelog_file)
        Path('.release/baseline.json').rename(config.baseline_file)
        self.change('chore: configure release paths')
        self.change('fix: first shared consumer release')
        base = r.git('rev-parse', 'HEAD')
        r.propose(self.api, base)
        p = self.release_pr()
        self.assertEqual(config.files, set(r.git('diff', '--name-only', base, p['head']['sha']).splitlines()))
        p, sha = self.merge_release()
        r.publish(self.api, p['number'])
        self.assertEqual(sha, self.api.tags['service-1.0.1']['object']['sha'])
        self.assertEqual('Example Service 1.0.1', self.api.records['service-1.0.1']['name'])
        self.change('feat: next release')
        r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertEqual('chore(release): 1.1.0', self.release_pr()['title'])

    def test_output_contract_and_no_change(self):
        output = str(Path(self.temp.name, 'outputs'))
        with patch.dict(os.environ, {'GITHUB_OUTPUT': output}):
            r.propose(self.api, r.git('rev-parse', 'HEAD'))
            self.assertEqual('result=no-change\n', Path(output).read_text())
            self.change('fix: behavior')
            r.propose(self.api, r.git('rev-parse', 'HEAD'))
            self.assertIn('result=candidate\n', Path(output).read_text())
            self.assertIn('head_sha=' + self.release_pr()['head']['sha'], Path(output).read_text())
            p, sha = self.merge_release()
            r.publish(self.api, p['number'])
        for value in ['result=published', 'sha=' + sha, 'version=1.0.1', 'tag=v1.0.1',
                      'immutable=true', 'release_url=https://github.com/example/service/releases/tag/v1.0.1']:
            self.assertIn(value + '\n', Path(output).read_text())

    def test_native_token_recovery_after_trunk_workflow_change(self):
        p, sha = self.pending_publication()
        Path('.github/workflows').mkdir(parents=True)
        Path('.github/workflows/product.yml').write_text('name: Product CI\n')
        self.change('chore(ci): update product workflow after release merge')
        original = self.api.request
        def native_token_api(path, method='GET', data=None, missing=False):
            if path == '/releases' and method == 'POST':
                self.assertEqual(self.api.config.trunk, data['target_commitish'])
                self.assertEqual(sha, self.api.tags['v1.0.1']['object']['sha'])
            return original(path, method, data, missing)
        with patch.object(self.api, 'request', side_effect=native_token_api):
            r.publish(self.api, p['number'])
        self.assertEqual(sha, self.api.tags['v1.0.1']['object']['sha'])
        self.assertIn(f'Source: `{sha}`', self.api.records['v1.0.1']['body'])

    def test_mismatched_default_trunk_blocks_before_mutations(self):
        self.change('fix: behavior')
        original = self.api.request
        def wrong_default(path, *args, **kwargs):
            return {'default_branch': 'other'} if path == '' else original(path, *args, **kwargs)
        with patch.object(self.api, 'request', side_effect=wrong_default):
            with self.assertRaisesRegex(ValueError, 'repository default branch'):
                r.propose(self.api, r.git('rev-parse', 'HEAD'))
        self.assertFalse(self.api.mutations)



class Configuration(unittest.TestCase):
    def test_unsafe_paths_rejected_before_git_or_api(self):
        for field in ('version_file', 'changelog_file', 'candidate_file', 'baseline_file'):
            for path in ('../outside', '/tmp/file', './version', 'a//b', 'a/../b',
                         '.git/config', '.github/workflows/release.yml', '-option', 'file:name',
                         'a\\b', 'name\nother'):
                with self.subTest(field=field, path=path):
                    with self.assertRaises(ValueError):
                        r.Config(**{field: path})

    def test_overlapping_paths_and_branches_rejected(self):
        for config in ({'version_file': 'CHANGELOG.md'}, {'version_file': '.release'},
                       {'branch': 'main'}, {'trunk': '../bad'}, {'branch': '-option'},
                       {'branch': 'release/x.lock'}, {'branch': 'release/a..b'},
                       {'tag_prefix': '../v'}, {'tag_prefix': 'v/ref'}, {'product': 'Name\nInjected'}):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    r.Config(**config)

    def test_isolated_python_ignores_consumer_module_shadowing(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'json.py').write_text("raise RuntimeError('UNTRUSTED_MODULE_EXECUTED')\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith('RELEASE_')}
            env['RELEASE_VERSION_FILE'] = '../invalid'
            result = subprocess.run([sys.executable, '-I', str(ROOT / 'release.py'), 'validate-pr', '--pr', '99'],
                                    cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            self.assertIn('safe repository-relative', result.stderr)
            self.assertNotIn('UNTRUSTED_MODULE_EXECUTED', result.stderr)

    def test_api_errors_never_log_token_or_response(self):
        env = {'GITHUB_REPOSITORY': 'example/service', 'GH_TOKEN': 'fixture-secret-value'}
        with patch.dict(os.environ, env):
            api = r.GitHub()
            errors = [r.urllib.error.HTTPError(api.root, 403, 'fixture-secret-value', {}, None),
                      r.urllib.error.URLError('fixture-secret-value')]
            for error in errors:
                with patch.object(r.urllib.request.OpenerDirector, 'open', side_effect=error):
                    with self.assertRaises(RuntimeError) as caught:
                        api.request('/pulls/99')
                    self.assertNotIn(env['GH_TOKEN'], str(caught.exception))
                if isinstance(error, r.urllib.error.HTTPError):
                    error.close()

    def test_fetch_credentials_are_not_command_arguments_or_persistent(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'example/service', 'GH_TOKEN': 'fixture-secret-value'}):
            api = r.GitHub()
            with patch.object(r, 'git', return_value='https://github.com/example/service.git'), \
                 patch.object(r.subprocess, 'run') as run:
                r.fetch(api, 'a' * 40)
            args = run.call_args.args[0]
            env = run.call_args.kwargs['env']
            self.assertNotIn('fixture-secret-value', ' '.join(args))
            self.assertEqual('http.https://github.com/.extraheader', env['GIT_CONFIG_KEY_0'])
            self.assertNotIn('GIT_CONFIG_VALUE_0', os.environ)
            self.assertEqual(subprocess.DEVNULL, run.call_args.kwargs['stderr'])



class ToolingChecks(unittest.TestCase):
    @patch.object(r.subprocess, 'run')
    def test_only_git_data_is_checked(self, run):
        base, head = 'a' * 40, 'b' * 40
        r.check_tooling(base, head)
        run.assert_called_once_with(['git', 'diff', '--check', base, head], check=True)


class Semver(unittest.TestCase):
    def propose(self, *titles):
        return r.proposal('1.2.3', [{'title': t} for t in titles])

    def test_feat_minor(self):
        self.assertEqual('1.3.0', self.propose('feat(auth): add login'))

    def test_fix_patch(self):
        self.assertEqual('1.2.4', self.propose('fix: correct policy'))

    def test_breaking_major(self):
        self.assertEqual('2.0.0', self.propose('refactor(auth)!: remove password grant'))

    def test_non_release_types(self):
        self.assertIsNone(self.propose('docs: setup', 'chore: tidy', 'test: coverage', 'refactor: simplify', 'perf: optimize', 'ci: checks'))

    def test_highest_bump(self):
        self.assertEqual('2.0.0', self.propose('fix: bug', 'feat: feature', 'fix!: remove old contract'))

    def test_bad_title_and_version(self):
        for title in ['Add login', 'fix:no space', 'feat: multiline\nbody', 'chore(release): 1.0.0']:
            with self.assertRaises(ValueError):
                self.propose(title)
        for v in ['1.0.01', '1.0.0-rc.1', 'latest', '1.0.0\n', '1.0.1٢']:
            with self.assertRaises(ValueError):
                r.version(v)


if __name__ == '__main__':
    unittest.main()
