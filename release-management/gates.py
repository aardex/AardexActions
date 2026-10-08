"""Small pinned consumer policy; read attested GitHub results, never run consumer code."""
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import quote, urlencode

POLICY_FILE = '.release/gates.json'
ACTIONS_APP = 15368


def require(condition, message):
    if not condition:
        raise ValueError('Release gates: ' + message)


def timestamp(value):
    require(isinstance(value, str) and bool(re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value)),
            'missing or invalid GitHub timestamp')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def identifier(value):
    require(type(value) is int and value > 0, 'invalid GitHub result identity')
    return value


def fingerprint(*records):
    # Only the digest is retained. Check output/body data never enters diagnostics
    # or the manifest; a retrospective edit still invalidates human approval.
    payload = json.dumps(records, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return 'sha256:' + hashlib.sha256(payload).hexdigest()


def policy(raw):
    def distinct(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate policy field')
            result[key] = value
        return result
    require(len(raw.encode('utf-8')) <= 16384, 'policy exceeds 16 KiB')
    document = json.loads(raw, object_pairs_hook=distinct)
    require(type(document) is dict and set(document) == {'workflows', 'checks'}, 'invalid policy fields')
    workflows, checks = document['workflows'], document['checks']
    require(type(workflows) is list and 1 <= len(workflows) <= 10 and
            type(checks) is list and len(checks) <= 10, 'invalid required gate lists')
    paths, names = set(), set()
    for gate in workflows:
        require(type(gate) is dict and set(gate) == {'path', 'job'}, 'invalid workflow gate')
        require(isinstance(gate['path'], str) and bool(re.fullmatch(
            r'\.github/workflows/[a-zA-Z0-9_-]+\.ya?ml', gate['path'])), 'invalid workflow path')
        require(isinstance(gate['job'], str) and bool(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9 _().-]{0,99}', gate['job'])),
                'invalid required job name')
        require(gate['path'] not in paths, 'duplicate workflow gate')
        paths.add(gate['path'])
    for gate in checks:
        require(type(gate) is dict and set(gate) == {'name', 'app_id'}, 'invalid App check gate')
        require(isinstance(gate['name'], str) and bool(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9 _().-]{0,99}', gate['name'])),
                'invalid App check name')
        identifier(gate['app_id'])
        require(gate['app_id'] != ACTIONS_APP and gate['name'] not in names, 'ambiguous App gate')
        names.add(gate['name'])
    return document


def approval(api, p):
    latest = {}
    for review in api.pages(f'/pulls/{p["number"]}/reviews'):
        if review['state'] not in ('COMMENTED', 'PENDING'):
            latest[review['user']['login']] = review
    approved = [timestamp(r['submitted_at']) for r in latest.values()
                if r['state'] == 'APPROVED' and r['user']['type'] == 'User' and r['commit_id'] == p['head']['sha']]
    require(approved, 'exact-head human approval required')
    cutoff = max(approved)
    require(cutoff <= timestamp(p['merged_at']), 'approval must precede human merge')
    return cutoff


def success(result, cutoff, earliest):
    require(result['status'] == 'completed' and result['conclusion'] == 'success',
            'required result is not completed with success')
    start, end = timestamp(result['started_at']), timestamp(result['completed_at'])
    require(earliest <= start <= end <= cutoff, 'stale result or result changed after approval')


def check_identity(api, check, sha, name, app_id):
    identifier(check['id'])
    require(check['name'] == name and check['head_sha'] == sha and check['app']['id'] == app_id,
            'check SHA, name or producer mismatch')
    identifier(check['check_suite']['id'])


def workflow_runs_path(path, source, trunk):
    # Deliberately only integrated, exact-SHA push validation. PR synthetic refs,
    # manual dispatch and other branches cannot supply this source gate.
    return '/actions/workflows/' + quote(path, safe='') + '/runs?' + urlencode(
        {'head_sha': source, 'event': 'push', 'branch': trunk})


def workflow_gate(api, gate, source, cutoff, earliest):
    query = workflow_runs_path(gate['path'], source, api.config.trunk)
    runs = api.pages(query, key='workflow_runs')
    require(runs, 'missing required workflow run: ' + gate['path'])
    run = max(runs, key=lambda item: identifier(item['id']))
    run_id = run['id']
    # Read the current attempt; never filter for success or reuse an older attempt.
    run = api.request(f'/actions/runs/{identifier(run["id"])}')
    require(run['id'] == run_id and run['path'] == gate['path'] and run['head_sha'] == source and run['head_branch'] == api.config.trunk
            and run['event'] == 'push' and run['repository']['full_name'] == api.repo
            and run['head_repository']['full_name'] == api.repo, 'workflow source or producer mismatch')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'required workflow is not successful')
    attempt = identifier(run['run_attempt'])
    jobs = api.pages(f'/actions/runs/{run["id"]}/attempts/{attempt}/jobs', key='jobs')
    jobs = [job for job in jobs if job['name'] == gate['job']]
    require(len(jobs) == 1, 'missing or ambiguous required job: ' + gate['job'])
    job = jobs[0]
    require(job['run_id'] == run['id'] and job['run_attempt'] == attempt and job['head_sha'] == source,
            'job run, attempt or SHA mismatch')
    success(job, cutoff, earliest)
    prefix = f'https://api.github.com/repos/{api.repo}/check-runs/'
    require(isinstance(job['check_run_url'], str) and bool(re.fullmatch(re.escape(prefix) + r'[1-9][0-9]*',
                                                                      job['check_run_url'])),
            'untrusted job check reference')
    check_id = int(job['check_run_url'][len(prefix):])
    check = api.request(f'/check-runs/{check_id}')
    require(check['id'] == check_id and check['check_suite']['id'] == run['check_suite_id'], 'job/check suite mismatch')
    check_identity(api, check, source, gate['job'], ACTIONS_APP)
    success(check, cutoff, earliest)
    require(check['started_at'] == job['started_at'] and check['completed_at'] == job['completed_at'],
            'job/check result mismatch')
    return {'kind': 'workflow-job', 'name': gate['job'], 'checked_sha': source, 'source_sha': source,
            'id': check_id, 'app_id': ACTIONS_APP, 'reference': prefix + str(check_id),
            'run_id': run['id'], 'attempt': attempt, 'workflow': gate['path'], 'pr': None,
            'completed_at': check['completed_at'], 'fingerprint': fingerprint(run, job, check)}


def app_gate(api, gate, p, source, cutoff, earliest):
    sha = p['head']['sha']
    checks = [c for c in api.pages(f'/commits/{sha}/check-runs?filter=all', key='check_runs') if c['name'] == gate['name']]
    require(checks, 'missing required App check: ' + gate['name'])
    check = max(checks, key=lambda item: identifier(item['id']))
    current = api.request(f'/check-runs/{identifier(check["id"])}')
    require(current == check, 'App check changed during verification')
    check_identity(api, check, sha, gate['name'], gate['app_id'])
    success(check, cutoff, earliest)
    suite = api.request(f'/check-suites/{check["check_suite"]["id"]}')
    require(suite['id'] == check['check_suite']['id'] and suite['head_sha'] == sha
            and suite['app']['id'] == gate['app_id'], 'App check source/suite identity mismatch')
    # GitHub removes suite.pull_requests entries for merged PRs. The caller has
    # already resolved/fetched this exact PR head and proved its full tree equals
    # the recorded integrated change; the attested scan addresses that Git object.
    return {'kind': 'app-check', 'name': gate['name'], 'checked_sha': sha, 'source_sha': source,
            'id': check['id'], 'app_id': gate['app_id'],
            'reference': f'https://api.github.com/repos/{api.repo}/check-runs/{check["id"]}',
            'run_id': None, 'attempt': None, 'workflow': None, 'pr': p['number'], 'completed_at': check['completed_at'],
            'fingerprint': fingerprint(check, {'id': suite['id'], 'app_id': suite['app']['id'],
                                             'head_sha': suite['head_sha'], 'pr': p['number']})}


def now():
    return datetime.now(timezone.utc)


def snapshot(api, metadata, policy_sha, r, cutoff=None):
    # The running isolated engine supplies its own Git helpers, including native
    # token fetch. Never import another copy of an entrypoint running as __main__.
    source = r.exact_sha(metadata['base_sha'])
    if not policy_sha:
        require(not r.exists(source, POLICY_FILE), 'policy exists but its reviewed SHA pin is missing')
        return None
    r.exact_sha(policy_sha)
    r.fetch(api, policy_sha)
    require(policy_sha in r.git('rev-list', '--first-parent', source).splitlines(), 'policy pin is not on source trunk history')
    raw = r.read(policy_sha, POLICY_FILE)
    configured = policy(raw)
    # Pin only the gate policy. Producer implementations evolve through consumer
    # PR review; attested execution identity/outcome does not certify their quality.
    require(r.read(source, POLICY_FILE) == raw, 'unapproved policy change: ' + POLICY_FILE)
    cutoff = cutoff or now()
    source_time = datetime.fromtimestamp(int(r.git('show', '-s', '--format=%ct', source)), timezone.utc)
    evidence = [workflow_gate(api, gate, source, cutoff, source_time) for gate in configured['workflows']]
    if configured['checks']:
        targets = []
        for change in metadata['changes']:
            included = api.pr(change['number'])
            require(included['number'] == change['number'] and included['merged'] and included['merge_commit_sha'] == change['sha']
                    and included['base']['ref'] == api.config.trunk, 'included PR source identity mismatch')
            head = r.exact_sha(included['head']['sha'])
            r.fetch(api, f'refs/pull/{change["number"]}/head')
            require(r.git('rev-parse', head + '^{tree}') == r.git('rev-parse', change['sha'] + '^{tree}'),
                    'included PR head does not prove the integrated source tree')
            targets.append((included, change['sha']))
        for target, target_source in targets:
            earliest = datetime.fromtimestamp(int(r.git('show', '-s', '--format=%ct', target['head']['sha'])), timezone.utc)
            evidence.extend(app_gate(api, gate, target, target_source, cutoff, earliest) for gate in configured['checks'])
    return {'policy_sha': policy_sha, 'source_sha': source, 'checks': evidence}


def verify(api, wanted, policy_sha, r):
    cutoff = approval(api, wanted['release_pr']) if policy_sha else None
    evidence = snapshot(api, wanted['metadata'], policy_sha, r, cutoff)
    if evidence is None:
        require('gate_snapshot' not in wanted['metadata'], 'approved candidate requires a policy pin')
        return None
    require(wanted['metadata'].get('gate_snapshot') == evidence, 'gate evidence differs from approved candidate snapshot')
    return dict(evidence, approved_at=cutoff.strftime('%Y-%m-%dT%H:%M:%SZ'))
