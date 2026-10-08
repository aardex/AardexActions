"""Publication regressions: disposable Git and attested GitHub-shaped pilot fixtures."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_release as fixture
import release as r
import gates as g
import manifest as m


class GatePublication(unittest.TestCase):
    setUp = fixture.Fixture.setUp
    tearDown = fixture.Fixture.tearDown
    change = fixture.Fixture.change
    release_pr = fixture.Fixture.release_pr
    merge_release = fixture.Fixture.merge_release

    def prepare(self, pilot='keycloak'):
        data = json.loads((Path(__file__).parent / 'fixtures' / (pilot + '.json')).read_text())
        self.api.repo = data['repository']
        self.api.config = r.Config(branch=data['branch'], product=data['product'])
        os.environ['GITHUB_WORKFLOW_REF'] = self.api.repo + '/.github/workflows/release.yml@refs/heads/main'
        jobs = [('consumer-checks.yml', 'consumer-checks')]
        if pilot == 'terraform-runner':
            jobs += [('terraform-validate.yml', 'terraform-fmt'), ('terraform-documentation.yml', 'terraform-docs')]
        self.policy = {'workflows': [{'path': '.github/workflows/' + path, 'job': job} for path, job in jobs],
                       'checks': [{'name': 'GitGuardian Security Checks', 'app_id': 46505}]}
        Path('.github/workflows').mkdir(parents=True)
        for gate in self.policy['workflows']:
            Path(gate['path']).write_text('name: ' + gate['job'] + '\n# synthetic trusted workflow\n')
        Path('.release/gates.json').write_text(json.dumps(self.policy))
        policy_sha = self.change('chore(EN-43): install reviewed gate policy')
        self.api.config = replace(self.api.config, gate_policy_sha=policy_sha)
        self.source = self.change('fix(EN-43): pilot source')
        # Each included source PR has a different immutable head with equal tree.
        for p in self.api.prs:
            if p.get('merged'):
                p['head']['sha'] = fixture.cmd('git', 'commit-tree', r.git('rev-parse', p['merge_commit_sha'] + '^{tree}'),
                                              '-p', r.git('rev-parse', p['merge_commit_sha'] + '^'), data='PR head')
                p['head']['repo'] = {'full_name': self.api.repo}
                fixture.cmd('git', 'update-ref', f'refs/pull/{p["number"]}/head', p['head']['sha'])
        self.p = None
        self.runs, self.jobs, self.checks, self.suites = {}, {}, {}, {}
        for i, gate in enumerate(self.policy['workflows'], 1):
            run = {'id': i, 'run_attempt': 1, 'head_sha': self.source, 'head_branch': 'main',
                   'event': 'push', 'path': gate['path'], 'check_suite_id': i,
                   'repository': {'full_name': self.api.repo}, 'head_repository': {'full_name': self.api.repo},
                   'status': 'completed', 'conclusion': 'success'}
            self.runs[gate['path']] = [run]
            check = self.make_check(i, gate['job'], self.source, 15368, i)
            self.jobs[i] = [{'id': i, 'name': gate['job'], 'run_id': i, 'run_attempt': 1,
                             'head_sha': self.source, 'status': 'completed', 'conclusion': 'success',
                             'started_at': check['started_at'], 'completed_at': check['completed_at'],
                             'check_run_url': f'https://api.github.com/repos/{self.api.repo}/check-runs/{i}'}]
        for i, p in enumerate(self.api.prs, 20):
            if 'sha' in p['head']:
                check = self.make_check(i, 'GitGuardian Security Checks', p['head']['sha'], 46505, i)
                self.suites[i] = {'id': i, 'head_sha': p['head']['sha'], 'app': {'id': 46505},
                                  'pull_requests': []}
        self.original_pages, self.original_request = self.api.pages, self.api.request
        self.addCleanup(patch.stopall)
        patch.object(self.api, 'pages', side_effect=self.pages).start()
        patch.object(self.api, 'request', side_effect=self.request).start()
        patch.object(g, 'now', return_value=g.timestamp('2099-01-01T10:10:00Z')).start()
        r.propose(self.api, self.source)
        self.p, self.sha = self.merge_release()
        self.p['merged_at'] = '2099-01-01T12:00:00Z'
        self.api.mutations.clear()
        return self.p

    def make_check(self, id_, name, sha, app_id, suite_id):
        check = {'id': id_, 'name': name, 'head_sha': sha, 'app': {'id': app_id},
                 'check_suite': {'id': suite_id}, 'status': 'completed', 'conclusion': 'success',
                 'started_at': '2099-01-01T10:00:00Z', 'completed_at': '2099-01-01T10:01:00Z'}
        self.checks[id_] = check
        return check

    def pages(self, path, key=None):
        if path.endswith('/reviews'):
            return [{'state': 'APPROVED', 'commit_id': self.p['head']['sha'], 'submitted_at': '2099-01-01T11:00:00Z',
                     'user': {'login': 'reviewer', 'type': 'User'}}]
        if path.startswith('/actions/workflows/'):
            from urllib.parse import unquote
            workflow = unquote(path.split('/runs?')[0][len('/actions/workflows/'):])
            return self.runs.get(workflow, [])
        if path.startswith('/actions/runs/') and path.endswith('/jobs'):
            return self.jobs[int(path.split('/')[3])]
        if '/check-runs?' in path:
            return [c for c in self.checks.values() if c['head_sha'] == path.split('/')[2]]
        return self.original_pages(path, key)

    def request(self, path, method='GET', data=None, missing=False):
        if path.startswith('/actions/runs/') and 'attempts' not in path:
            return next(run for runs in self.runs.values() for run in runs if run['id'] == int(path.split('/')[3]))
        if path.startswith('/check-runs/'):
            return self.checks[int(path.split('/')[2])]
        if path.startswith('/check-suites/'):
            return self.suites[int(path.split('/')[2])]
        return self.original_request(path, method, data, missing)

    def assert_blocked(self):
        with self.assertRaises((ValueError, RuntimeError)):
            r.publish(self.api, self.p['number'])
        self.assertEqual([], self.api.mutations)
        self.assertFalse(self.api.tags)
        self.assertFalse(self.api.records)

    def test_missing_required_workflow_blocks_before_any_mutation(self):
        self.prepare()
        self.runs['.github/workflows/consumer-checks.yml'] = []
        self.assert_blocked()

    def test_required_failed_workflow_blocks_before_any_mutation(self):
        self.prepare('terraform-runner')
        self.runs['.github/workflows/terraform-validate.yml'][0]['conclusion'] = 'failure'
        self.assert_blocked()

    def assert_valid_pilot(self, pilot):
        self.prepare(pilot)
        r.publish(self.api, self.p['number'])
        document = json.loads(self.api.manifest_payload)
        evidence = document['gate_evidence']
        self.assertEqual(self.api.config.gate_policy_sha, evidence['policy_sha'])
        self.assertEqual(self.source, evidence['source_sha'])
        jobs = [c for c in evidence['checks'] if c['kind'] == 'workflow-job']
        self.assertEqual(1 if pilot == 'keycloak' else 3, len(jobs))
        self.assertTrue(all(c['checked_sha'] == self.source for c in jobs))
        self.assertTrue(all(c['checked_sha'] != self.sha for c in jobs))
        self.assertEqual(3, len([c for c in evidence['checks'] if c['kind'] == 'app-check']))
        self.assertEqual(['EN-43'], document['jira_keys'])
        self.assertEqual(1, document['schema_version'])
        self.assertTrue(self.api.records['v1.0.1']['immutable'])
        from test_schema import Draft202012Validator
        if Draft202012Validator is not None:
            Draft202012Validator(m.SCHEMA).validate(document)

    def test_manifest_gate_evidence_identity_and_schema_are_validated(self):
        self.prepare()
        r.publish(self.api, self.p['number'])
        document = json.loads(self.api.manifest_payload)
        metadata = json.loads(r.read(self.p['head']['sha'], self.api.config.candidate_file))
        for path, value in [(['policy_sha'], 'd' * 40), (['source_sha'], 'd' * 40),
                            (['checks', 0, 'fingerprint'], 'sha256:' + 'f' * 64),
                            (['checks', 0, 'checked_sha'], 'd' * 40),
                            (['checks', 0, 'app_id'], 999), (['checks', 0, 'run_id'], None),
                            (['checks', 0, 'fingerprint'], 'bad'), (['checks', 0, 'reference'], 'https://evil.test/'),
                            (['checks', 1, 'pr'], 999), (['checks', 1, 'source_sha'], 'd' * 40)]:
            invalid = copy.deepcopy(document)
            target = invalid['gate_evidence']
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.validate(invalid, self.api.repo, metadata, self.sha, self.p['head']['sha'], 'v')
        document.pop('gate_evidence')
        with self.assertRaisesRegex(ValueError, 'evidence missing'):
            m.validate(document, self.api.repo, metadata, self.sha, self.p['head']['sha'], 'v')

    def test_gate_evidence_cannot_be_supplied_as_manifest_declaration(self):
        with self.assertRaises(ValueError):
            m.supplemental('{"gate_evidence":{}}')

    def test_keycloak_required_gates_and_manifest_compatibility(self):
        self.assert_valid_pilot('keycloak')

    def test_terraform_required_gates_and_manifest_compatibility(self):
        self.assert_valid_pilot('terraform-runner')

    def test_non_success_job_or_check_never_succeeds(self):
        self.prepare('terraform-runner')
        for target in (self.jobs[1][0], self.checks[1]):
            original = copy.deepcopy(target)
            for status, conclusion in [('completed', 'failure'), ('completed', 'skipped'),
                                       ('completed', 'cancelled'), ('completed', 'stale'),
                                       ('completed', 'neutral'), ('queued', None), ('in_progress', None),
                                       ('pending', None), ('completed', 'timed_out')]:
                with self.subTest(target='job' if target is self.jobs[1][0] else 'check', outcome=conclusion):
                    target.update(status=status, conclusion=conclusion)
                    self.assert_blocked()
                target.clear()
                target.update(original)

    def test_latest_failed_run_or_current_rerun_cannot_reuse_old_success(self):
        self.prepare()
        run = self.runs['.github/workflows/consumer-checks.yml'][0]
        self.runs['.github/workflows/consumer-checks.yml'].append(dict(run, id=11, conclusion='failure'))
        self.assert_blocked()
        self.runs['.github/workflows/consumer-checks.yml'].pop()
        run.update(run_attempt=2, status='in_progress', conclusion=None)
        self.assert_blocked()

    def test_earlier_job_attempt_cannot_supply_current_attempt(self):
        self.prepare()
        self.runs['.github/workflows/consumer-checks.yml'][0]['run_attempt'] = 2
        self.assert_blocked()

    def test_wrong_workflow_sha_event_branch_repository_path(self):
        self.prepare()
        run = self.runs['.github/workflows/consumer-checks.yml'][0]
        original = copy.deepcopy(run)
        for key, value in [('head_sha', 'd' * 40), ('event', 'pull_request'), ('head_branch', 'feature/untrusted'),
                           ('path', '.github/workflows/fake.yml'), ('repository', {'full_name': 'attacker/fork'}),
                           ('head_repository', {'full_name': 'attacker/fork'})]:
            with self.subTest(key=key):
                run[key] = value
                self.assert_blocked()
            run.clear()
            run.update(original)

    def test_job_and_check_identity_and_producer_must_match(self):
        self.prepare()
        for target, key, value in [(self.jobs[1][0], 'head_sha', 'f' * 40),
                                   (self.jobs[1][0], 'run_id', 99), (self.jobs[1][0], 'run_attempt', 2),
                                   (self.jobs[1][0], 'check_run_url', 'https://evil.test/check-runs/1'),
                                   (self.checks[1], 'head_sha', 'f' * 40),
                                   (self.checks[1], 'app', {'id': 999}), (self.checks[1], 'id', 999),
                                   (self.checks[1], 'name', 'consumer-checks-renamed'),
                                   (self.checks[1], 'check_suite', {'id': 99})]:
            original = copy.deepcopy(target)
            with self.subTest(key=key):
                target[key] = value
                self.assert_blocked()
            target.clear()
            target.update(original)

    def test_missing_and_ambiguous_jobs_block(self):
        self.prepare()
        jobs = self.jobs[1]
        self.jobs[1] = []
        self.assert_blocked()
        self.jobs[1] = jobs + [copy.deepcopy(jobs[0])]
        self.assert_blocked()

    def test_results_before_source_or_after_approval_block(self):
        self.prepare()
        for target in (self.jobs[1][0], self.checks[20]):
            original = copy.deepcopy(target)
            for key, value in [('started_at', '2000-01-01T10:00:00Z'),
                               ('completed_at', '2099-01-01T11:01:00Z'), ('completed_at', None)]:
                with self.subTest(key=key):
                    target[key] = value
                    self.assert_blocked()
                target.clear()
                target.update(original)

    def test_app_missing_failure_wrong_producer_or_association(self):
        self.prepare()
        check = self.checks.pop(20)
        self.assert_blocked()
        self.checks[20] = check
        for target, key, value in [(check, 'app', {'id': 999}), (check, 'conclusion', 'failure'),
                                   (check, 'name', 'GitGuardian renamed'),
                                   (self.suites[20], 'head_sha', 'd' * 40),
                                   (self.suites[20], 'app', {'id': 999}),
                                   (self.suites[20], 'id', 999)]:
            original = copy.deepcopy(target)
            with self.subTest(key=key):
                target[key] = value
                self.assert_blocked()
            target.clear()
            target.update(original)

    def test_app_newer_failed_result_cannot_reuse_previous_success(self):
        self.prepare()
        older = self.checks[20]
        self.checks[200] = dict(older, id=200, conclusion='failure')
        self.assert_blocked()

    def test_retrospective_success_edit_with_unchanged_completion_time_blocks(self):
        self.prepare()
        self.checks[20]['output'] = {'summary': 'Changed after human approval'}
        self.assert_blocked()

    def test_new_successful_attempt_requires_new_candidate_approval(self):
        self.prepare()
        self.runs['.github/workflows/consumer-checks.yml'][0]['run_attempt'] = 2
        self.jobs[1][0]['run_attempt'] = 2
        self.assert_blocked()

    def test_new_successful_check_cannot_replace_approved_identity(self):
        self.prepare()
        self.checks[200] = dict(self.checks[20], id=200)
        self.assert_blocked()

    def test_included_pr_wrong_sha_or_unproved_merge_tree_blocks(self):
        self.prepare()
        p = self.api.prs[0]
        original = copy.deepcopy(p)
        p['merge_commit_sha'] = 'd' * 40
        self.assert_blocked()
        p.clear()
        p.update(original)
        p['head']['sha'] = self.source
        self.assert_blocked()

    def test_policy_pin_absent_wrong_not_ancestor_or_unapproved_change(self):
        self.prepare()
        config = self.api.config
        for pin in ('', self.p['head']['sha']):
            self.api.config = replace(config, gate_policy_sha=pin)
            self.assert_blocked()
        self.api.config = config
        original_read = r.read
        for path in (g.POLICY_FILE, '.github/workflows/consumer-checks.yml'):
            def read(sha, target):
                raw = original_read(sha, target)
                return raw + ' ' if sha == self.source and target == path else raw
            with self.subTest(path=path), patch.object(r, 'read', side_effect=read):
                self.assert_blocked()
        with self.assertRaises(ValueError):
            replace(config, gate_policy_sha='main')

    def test_real_unapproved_policy_change_cannot_produce_candidate(self):
        self.prepare()
        fixture.cmd('git', 'reset', '--hard', self.source)
        self.api.prs.remove(self.p)
        Path(g.POLICY_FILE).write_text(json.dumps(dict(self.policy, checks=[])))
        unapproved = self.change('chore(ci): weaken policy without repinning')
        with self.assertRaisesRegex(ValueError, 'unapproved policy'):
            r.propose(self.api, unapproved)
        self.assertFalse(self.api.mutations)

    def test_policy_repin_changes_candidate_and_requires_reapproval(self):
        self.prepare()
        # Same source/workflow policy content at a different reviewed trunk pin
        # still changes the approval-bound candidate metadata.
        self.api.config = replace(self.api.config, gate_policy_sha=self.source)
        self.assert_blocked()

    def test_github_read_failures_leave_no_release_mutations(self):
        self.prepare()
        for method in ('pages', 'request'):
            original = getattr(self, method)
            def fail(path, *args, **kwargs):
                if path.startswith(('/actions/workflows/', '/check-runs/', '/check-suites/')):
                    raise RuntimeError('GitHub read failed')
                return original(path, *args, **kwargs)
            with self.subTest(method=method), patch.object(self.api, method, side_effect=fail):
                self.assert_blocked()

    def test_change_during_manifest_collection_blocks_before_tag(self):
        self.prepare()
        original_generate = m.generate
        def generate(*args, **kwargs):
            document = original_generate(*args, **kwargs)
            self.jobs[1][0]['conclusion'] = 'cancelled'
            return document
        with patch.object(m, 'generate', side_effect=generate):
            self.assert_blocked()

    def test_change_during_upload_keeps_draft_and_refuses_publication(self):
        self.prepare()
        original_upload = self.api.upload_manifest
        def upload(*args):
            asset = original_upload(*args)
            self.checks[20]['conclusion'] = 'failure'
            return asset
        with patch.object(self.api, 'upload_manifest', side_effect=upload):
            with self.assertRaises(ValueError):
                r.publish(self.api, self.p['number'])
        self.assertTrue(self.api.records['v1.0.1']['draft'])
        self.assertFalse(any(method == 'PATCH' for _, method, _ in self.api.mutations))

    def test_untrusted_declared_status_cannot_replace_attested_workflow(self):
        self.prepare()
        self.api.statuses.append((self.source, 'success', 'consumer-checks'))
        self.runs['.github/workflows/consumer-checks.yml'] = []
        self.assert_blocked()

    def test_policy_is_small_closed_and_nonempty(self):
        valid = {'workflows': [{'path': '.github/workflows/consumer-checks.yml', 'job': 'consumer-checks'}], 'checks': []}
        self.assertEqual(valid, g.policy(json.dumps(valid)))
        for raw in ['{}', '[]', '{"workflows":[],"checks":[]}',
                    '{"workflows":[],"checks":[],"checks":[]}',
                    json.dumps(dict(valid, allow_failure=True)),
                    json.dumps(dict(valid, workflows=valid['workflows'] * 2)),
                    json.dumps(dict(valid, checks=[{'name': 'fake', 'app_id': 15368}])),
                    json.dumps(dict(valid, workflows=[{'path': '../../evil.yml', 'job': 'fake'}]))]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                g.policy(raw)


if __name__ == '__main__':
    unittest.main()
