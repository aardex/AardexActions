"""Version 1 source-release evidence snapshot; no readiness or deployment policy."""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import gates

SCHEMA = json.loads(Path(__file__).with_name('release-manifest.schema.json').read_text())
JIRA = re.compile(r'(?<![A-Za-z0-9_-])[A-Z][A-Z0-9]+-[1-9][0-9]*(?![A-Za-z0-9_-])')
SECTIONS = ('artifacts', 'migrations', 'dependencies', 'sbom', 'provenance')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def shape(value, schema, path='$'):
    """Validate the keywords used by our fixed schema (not a general schema engine)."""
    if '$ref' in schema:
        return shape(value, SCHEMA['$defs'][schema['$ref'].split('/')[-1]], path)
    if 'anyOf' in schema:
        for choice in schema['anyOf']:
            try:
                shape(value, choice, path)
                return
            except ValueError:
                pass
        raise ValueError(f'Manifest schema mismatch at {path}')
    if 'const' in schema:
        require(type(value) is type(schema['const']) and value == schema['const'], f'Manifest constant mismatch at {path}')
    if 'enum' in schema:
        require(value in schema['enum'], f'Manifest enum mismatch at {path}')
    if 'type' in schema:
        types = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool, 'null': type(None)}
        require(type(value) is types[schema['type']], f'Manifest type mismatch at {path}')
    if isinstance(value, dict):
        properties = schema['properties']
        require(set(schema['required']) <= set(value) <= set(properties), f'Manifest fields mismatch at {path}')
        for key, item in value.items():
            shape(item, properties[key], path + '.' + key)
    if isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), f'Manifest empty collection at {path}')
        for index, item in enumerate(value):
            shape(item, schema['items'], f'{path}[{index}]')
    if isinstance(value, str):
        require(schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', 10000), f'Manifest string length at {path}')
        require(not any(ord(c) < 32 or ord(c) == 127 for c in value), f'Manifest control character at {path}')
        if 'pattern' in schema:
            require(re.search(schema['pattern'], value) is not None, f'Manifest pattern mismatch at {path}')
    if type(value) is int:
        require(value >= schema.get('minimum', value), f'Manifest integer mismatch at {path}')


def jira_keys(changes):
    # The engine already resolved the included titles; no PR/Jira enrichment.
    return sorted({key for change in changes for key in JIRA.findall(change['title'])})


def reference(value):
    try:
        url = urlsplit(value)
    except ValueError:
        raise ValueError('Invalid evidence reference') from None
    require(not url.username and not url.password and not url.query
            and not re.match(r'^[^/]+@', value),
            'Evidence references must not contain credentials or query strings')
    if url.netloc or '://' in value:
        require(url.scheme == 'https' and url.hostname, 'Network evidence references must use HTTPS')


def validate(document, repository, metadata, sha, head, tag_prefix):
    shape(document, SCHEMA)
    identity = document['release']
    require(identity == {'kind': 'source', 'repository': repository, 'version': metadata['version'],
                         'tag': tag_prefix + metadata['version'], 'sha': sha}, 'Manifest release identity mismatch')
    require(document['changes'] == metadata['changes'], 'Manifest included changes mismatch')
    require(document['release_pr']['head_sha'] == head and document['release_pr']['merge_sha'] == sha,
            'Manifest Release PR SHA mismatch')
    require(document['release_pr']['reference'] == f'https://github.com/{repository}/pull/{document["release_pr"]["number"]}',
            'Manifest Release PR reference mismatch')
    require(document['jira_keys'] == jira_keys(metadata['changes']), 'Manifest Jira keys mismatch')
    require(('gate_evidence' in document) == ('gate_snapshot' in metadata), 'Manifest approved gate evidence missing or unexpected')
    if 'gate_evidence' in document:
        evidence = document['gate_evidence']
        require({key: evidence[key] for key in ('policy_sha', 'source_sha', 'checks')} == metadata['gate_snapshot'],
                'Manifest gate evidence differs from approved snapshot')
        require(evidence['source_sha'] == metadata['base_sha'], 'Gate source identity mismatch')
        cutoff = gates.timestamp(evidence['approved_at'])
        included = {c['number']: c['sha'] for c in metadata['changes']}
        for check in evidence['checks']:
            require(check['reference'] == f'https://api.github.com/repos/{repository}/check-runs/{check["id"]}',
                    'Gate reference mismatch')
            require(gates.timestamp(check['completed_at']) <= cutoff, 'Gate evidence changed after approval')
            if check['kind'] == 'workflow-job':
                require(check['checked_sha'] == check['source_sha'] == metadata['base_sha']
                        and check['app_id'] == gates.ACTIONS_APP and check['run_id'] is not None
                        and check['attempt'] is not None and check['pr'] is None
                        and isinstance(check['workflow'], str) and bool(re.fullmatch(
                            r'\.github/workflows/[a-zA-Z0-9_-]+\.ya?ml', check['workflow'])),
                        'Workflow gate evidence identity mismatch')
            else:
                require(check['run_id'] is None and check['attempt'] is None and check['workflow'] is None
                        and check['app_id'] != gates.ACTIONS_APP, 'App gate evidence identity mismatch')
                require(check['pr'] in included and check['source_sha'] == included[check['pr']],
                        'Included PR gate source mismatch')
    generator = document['generator']
    require(generator['workflow_ref'].startswith(repository + '/.github/workflows/'), 'Generator workflow repository mismatch')
    require(generator['status'] != 'completed' and generator['conclusion'] is None,
            'Publisher cannot attest its own final success')
    require(generator['reference'] == f'https://github.com/{repository}/actions/runs/{generator["run_id"]}/attempts/{generator["attempt"]}',
            'Generator evidence reference mismatch')
    for check in document['checks']:
        require(check['checked_sha'] in (sha, head), 'Check evidence SHA mismatch')
        if check['state'] == 'available':
            expected_ref = (f'https://api.github.com/repos/{repository}/check-runs/{check["id"]}'
                            if check['kind'] == 'github-check' else
                            f'https://api.github.com/repos/{repository}/commits/{check["checked_sha"]}/statuses')
            require(check['reference'] == expected_ref, 'Check evidence reference mismatch')
            outcome = check['outcome']
            if check['kind'] != 'github-check':
                require(outcome['status'] in ('success', 'failure', 'error', 'pending') and outcome['conclusion'] is None,
                        'Invalid commit status outcome')
            else:
                require(outcome['status'] in ('queued', 'in_progress', 'completed', 'waiting', 'pending', 'requested'),
                        'Invalid check-run status')
                require((outcome['status'] == 'completed') == (outcome['conclusion'] is not None),
                        'Check completion/conclusion mismatch')
            reference(check['reference'])
    for section in SECTIONS:
        record = document[section]
        if record['state'] != 'available':
            continue
        for item in record['items']:
            require(item['release_sha'] == sha, 'Declared evidence release SHA mismatch')
            reference(item['reference'])
            if section == 'artifacts' and '@sha256:' in item['reference']:
                require(item['reference'].rsplit('@', 1)[1] == item['digest'], 'Artifact reference/digest mismatch')
            if section == 'dependencies' and item['resolved'] is not None:
                resolved = item['resolved']
                patterns = {'git_commit': r'[0-9a-f]{40}', 'digest': r'sha256:[0-9a-f]{64}',
                            'version': r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'}
                require(re.fullmatch(patterns[resolved['kind']], resolved['value']) is not None,
                        'Dependency resolution must be an exact version, commit or digest')


def supplemental(raw):
    def distinct(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate manifest data key')
            result[key] = value
        return result
    require(len(raw.encode('utf-8')) <= 65536, 'Manifest data exceeds 64 KiB')
    try:
        supplied = json.loads(raw, object_pairs_hook=distinct) if raw else {}
    except json.JSONDecodeError:
        raise ValueError('Invalid manifest data JSON') from None
    require(isinstance(supplied, dict) and set(supplied) <= set(SECTIONS), 'Unexpected manifest data sections')
    return {name: supplied.get(name, {'state': 'missing', 'reason': 'Not collected by the source release publisher'})
            for name in SECTIONS}


def collect_checks(api, head, sha):
    checks = []
    for checked_sha in sorted({head, sha}):
        statuses = api.pages(f'/commits/{checked_sha}/statuses')
        contexts = set()
        for status in statuses:
            contexts.add(status['context'])
            kind = 'release-mechanics' if status['context'] in ('release-inputs', 'release-tests') else 'github-status'
            checks.append({'state': 'available', 'kind': kind, 'name': status['context'],
                           'checked_sha': checked_sha, 'verification': 'observed',
                           'reference': f'https://api.github.com/repos/{api.repo}/commits/{checked_sha}/statuses',
                           'id': status['id'],
                           'outcome': {'status': status['state'], 'conclusion': None}})
        if checked_sha == head:
            for name in ('release-inputs', 'release-tests'):
                if name not in contexts:
                    checks.append({'state': 'missing', 'kind': 'release-mechanics', 'name': name,
                                   'checked_sha': checked_sha, 'reason': 'No commit status collected on the approved head'})
        runs = api.pages(f'/commits/{checked_sha}/check-runs?filter=all', key='check_runs')
        for run in runs:
            require(run['head_sha'] == checked_sha, 'GitHub check-run SHA mismatch')
            checks.append({'state': 'available', 'kind': 'github-check', 'name': run['name'], 'id': run['id'],
                           'checked_sha': run['head_sha'], 'verification': 'observed',
                           'reference': f'https://api.github.com/repos/{api.repo}/check-runs/{run["id"]}',
                           'outcome': {'status': run['status'], 'conclusion': run['conclusion']}})
        if not runs:
            checks.append({'state': 'missing', 'kind': 'github-check', 'name': 'Check runs',
                           'checked_sha': checked_sha, 'reason': 'No check runs collected on this SHA'})
    return sorted(checks, key=lambda c: (c['checked_sha'], c['kind'], c['name'], c.get('id', 0)))


def generate(api, wanted, sha, gate_evidence=None):
    metadata, p = wanted['metadata'], wanted['release_pr']
    try:
        run_id, attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
        workflow_ref, workflow_sha = os.environ['GITHUB_WORKFLOW_REF'], os.environ['GITHUB_WORKFLOW_SHA']
    except (KeyError, ValueError):
        raise ValueError('Publisher workflow identity is required') from None
    require(run_id > 0 and attempt > 0, 'Invalid publisher run identity')
    run = api.request(f'/actions/runs/{run_id}/attempts/{attempt}')
    require(run['id'] == run_id and run['run_attempt'] == attempt
            and run['repository']['full_name'].lower() == api.repo.lower(), 'Publisher workflow run identity mismatch')
    require(workflow_ref.split('@')[0] == api.repo + '/' + run['path'].split('@')[0],
            'Publisher workflow reference mismatch')
    document = {
        'schema_version': 1,
        'release': {'kind': 'source', 'repository': api.repo, 'version': metadata['version'],
                    'tag': api.config.tag_prefix + metadata['version'], 'sha': sha},
        'release_pr': {'number': p['number'], 'reference': f'https://github.com/{api.repo}/pull/{p["number"]}',
                       'head_sha': p['head']['sha'], 'merge_sha': sha, 'tree_match': True},
        'changes': metadata['changes'], 'jira_keys': jira_keys(metadata['changes']),
        'generator': {'run_id': run_id, 'attempt': attempt, 'workflow_ref': workflow_ref,
                      'workflow_sha': workflow_sha, 'run_head_sha': run['head_sha'],
                      'reference': f'https://github.com/{api.repo}/actions/runs/{run_id}/attempts/{attempt}',
                      'status': run['status'], 'conclusion': run['conclusion']},
        'checks': collect_checks(api, p['head']['sha'], sha),
        **supplemental(os.environ.get('RELEASE_MANIFEST_DATA', '')),
    }
    if gate_evidence is not None:
        document['gate_evidence'] = gate_evidence
    validate(document, api.repo, metadata, sha, p['head']['sha'], api.config.tag_prefix)
    return document


def verify_asset(api, release_id, payload, asset_id):
    require(type(asset_id) is int and asset_id > 0, 'Invalid manifest asset id')
    matches = [a for a in api.pages(f'/releases/{release_id}/assets') if a['name'] == 'release-manifest.json']
    require(len(matches) == 1 and matches[0]['id'] == asset_id, 'Manifest asset missing or conflicting')
    # Authenticated fixed GitHub API metadata, including server-computed digest.
    asset = api.request(f'/releases/assets/{asset_id}')
    require(asset.get('id') == asset_id and asset.get('name') == 'release-manifest.json'
            and asset.get('state') == 'uploaded' and asset.get('size') == len(payload)
            and asset.get('digest') == 'sha256:' + hashlib.sha256(payload).hexdigest(),
            'Manifest asset integrity mismatch; reconcile partial publication manually')
