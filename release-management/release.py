#!/usr/bin/env python3
"""Deterministic release inputs. Trusted GitHub-only release engine; PR code is always data."""
import argparse
import base64
import json
import os
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import quote, urlencode
import re
import subprocess
import sys
import urllib.error
import urllib.request

# Add only the pinned shared action directory, never the consumer checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest

VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')
TITLE = re.compile(r'(feat|fix|docs|chore|test|refactor|perf|build|ci|style|revert)(?:\(([a-zA-Z0-9_. /-]+)\))?(!)?: (\S[^\r\n]*)\Z')


class PublicationPending(RuntimeError):
    """An approved, reproducible release has neither published GitHub identity yet."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Config:
    trunk: str = 'main'
    version_file: str = 'version.txt'
    changelog_file: str = 'CHANGELOG.md'
    candidate_file: str = '.release/candidate.json'
    baseline_file: str = '.release/baseline.json'
    branch: str = 'release/managed'
    product: str = 'Release'
    tag_prefix: str = 'v'

    def __post_init__(self):
        paths = [self.version_file, self.changelog_file, self.candidate_file, self.baseline_file]
        for path in paths:
            parts = path.split('/')
            require(bool(re.fullmatch(r'[a-zA-Z0-9_./-]+', path)) and
                    all(part not in ('', '.', '..') and not part.lower().startswith('.git') and not part.startswith('-')
                        for part in parts), 'Release paths must be safe repository-relative file paths')
        require(len(set(paths)) == 4 and not any(
            a != b and b.startswith(a + '/') for a in paths for b in paths),
            'Release paths must be distinct and cannot overlap')
        for branch in (self.trunk, self.branch):
            require(bool(re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_./-]*', branch)) and
                    all(part not in ('', '.', '..') and not part.startswith('.') and
                        not part.endswith(('.', '.lock')) for part in branch.split('/')) and
                    '..' not in branch, 'Invalid release/trunk branch name')
        require(self.trunk != self.branch, 'Managed branch must differ from trunk')
        require(bool(re.fullmatch(r'[a-zA-Z0-9_-]*', self.tag_prefix)), 'Invalid tag prefix')
        require(bool(self.product.strip()) and len(self.product) <= 100 and
                all(ord(c) >= 32 and ord(c) != 127 for c in self.product), 'Invalid release display name')

    @property
    def files(self):
        return {self.version_file, self.changelog_file, self.candidate_file}

    @classmethod
    def environment(cls):
        return cls(**{field: os.environ.get('RELEASE_' + field.upper(), default)
                      for field, default in ((name, item.default) for name, item in cls.__dataclass_fields__.items())})


def exact_sha(value):
    require(isinstance(value, str) and bool(re.fullmatch(r'[0-9a-f]{40}', value)), 'Expected exact Git commit SHA')
    return value


def native_candidate(api, p):
    require(p['user']['login'] == 'github-actions[bot]' and p['user']['type'] == 'Bot' and
            p['head']['repo'] and p['head']['repo']['full_name'] == api.repo and
            p['head']['ref'] == api.config.branch, 'Release PR must be the native Actions bot candidate in this repository')


def outputs(**values):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            for key, value in values.items():
                value = str(value)
                require('\n' not in value and '\r' not in value, 'Invalid action output')
                out.write(f'{key}={value}\n')


def version(value):
    require(bool(VERSION.fullmatch(value)), 'Expected stable SemVer X.Y.Z (no prerelease or leading zeros)')
    return tuple(map(int, value.split('.')))


def bump(title):
    match = TITLE.fullmatch(title)
    require(bool(match), 'PR title must use Conventional PR-title syntax')
    kind, scope, breaking, _ = match.groups()
    require(scope != 'release', 'Scope release is reserved for the generated Release PR')
    return 3 if breaking else 2 if kind == 'feat' else 1 if kind == 'fix' else 0


def proposal(current, changes):
    parts = list(version(current))
    level = max((bump(c['title']) for c in changes), default=0)
    if not level:
        return None
    index = 3 - level
    parts[index] += 1
    for i in range(index + 1, 3):
        parts[i] = 0
    return '.'.join(map(str, parts))


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def fetch(api, *refs):
    # Checkout uses persist-credentials:false; Git authentication stays in a child
    # environment, never a URL, command argument, global config, or diagnostic.
    env = os.environ.copy()
    if isinstance(api, GitHub):
        origin = git('remote', 'get-url', 'origin')
        require(origin in (f'https://github.com/{api.repo}', f'https://github.com/{api.repo}.git'),
                'origin must be the consumer repository on GitHub')
        credential = base64.b64encode(f'x-access-token:{api.token}'.encode()).decode()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                   GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + credential, GIT_TERMINAL_PROMPT='0')
    subprocess.run(['git', 'fetch', '--quiet', '--no-tags', 'origin', *refs], env=env,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read(ref, path):
    # Preserve exact file contents, including trailing newlines.
    exact_sha(ref)
    entry = git('ls-tree', ref, '--', path).split()
    require(len(entry) >= 3 and entry[0] == '100644' and entry[1] == 'blob',
            f'Release file must be a regular non-executable blob: {path}')
    # Decode bytes without universal-newline conversion: CRLF must not equal LF.
    return subprocess.check_output(['git', 'show', f'{ref}:{path}']).decode('utf-8')


def exists(ref, path):
    return subprocess.run(['git', 'cat-file', '-e', f'{ref}:{path}'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def json_text(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + '\n'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Authenticated JSON/upload calls must never forward credentials.
        return None


class GitHub:
    def __init__(self, config=None):
        self.config = config or Config()
        self.repo = os.environ['GITHUB_REPOSITORY']
        require(bool(re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+', self.repo)), 'Invalid GitHub repository')
        self.root = f'https://api.github.com/repos/{self.repo}'
        self.token = os.environ['GH_TOKEN']
        require(bool(self.token), 'Native GITHUB_TOKEN is required')

    def request(self, path, method='GET', data=None, missing=False):
        require(path == '' or (path.startswith('/') and not path.startswith('//')), 'Invalid GitHub API path')
        url = self.root + path
        payload = json.dumps(data).encode() if data is not None else None
        return self.json_request(url, method, payload, missing=missing)

    def json_request(self, url, method, payload=None, missing=False, content_type='application/json'):
        # URLs are constructed by this engine; never use input/API upload_url.
        require(url == self.root or url.startswith(self.root + '/') or bool(re.fullmatch(
            re.escape(f'https://uploads.github.com/repos/{self.repo}/releases/') +
            r'[1-9][0-9]*/assets\?name=release-manifest\.json', url)), 'Untrusted authenticated URL')
        req = urllib.request.Request(url, data=payload, method=method, headers={
            'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': content_type,
        })
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            # Do not include response bodies or request headers in diagnostics.
            raise RuntimeError(f'GitHub {method} failed: HTTP {error.code}') from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('GitHub request failed; check connectivity and retry safely') from None

    def pages(self, path, key=None):
        result = []
        for page in range(1, 1001):
            rows = self.request(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
            if key is not None:
                rows = rows[key]
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise ValueError('GitHub pagination limit reached')

    def upload_manifest(self, release_id, payload):
        require(type(release_id) is int and release_id > 0, 'Invalid draft release id')
        url = f'https://uploads.github.com/repos/{self.repo}/releases/{release_id}/assets?name=release-manifest.json'
        return self.json_request(url, 'POST', payload, content_type='application/json')

    def pr(self, number):
        return self.request(f'/pulls/{int(number)}')

    def status(self, sha, state, description, context='release-inputs'):
        self.request(f'/statuses/{sha}', 'POST', {
            'state': state, 'context': context, 'description': description[:140],
            'target_url': f'https://github.com/{self.repo}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        })


def anchor(api, ref):
    current = read(ref, api.config.version_file).strip()
    version(current)
    if exists(ref, api.config.candidate_file):
        last = json.loads(read(ref, api.config.candidate_file))
        require(last['version'] == current, 'Version authority differs from last release metadata')
        sha = git('log', '--first-parent', '-1', '--format=%H', ref, '--', api.config.candidate_file)
        tag = api.request(f'/git/ref/tags/{api.config.tag_prefix}{current}', missing=True)
        record = api.request(f'/releases/tags/{api.config.tag_prefix}{current}', missing=True)
        if tag is None and record is None:
            prs = [p for p in api.pages(f'/commits/{sha}/pulls')
                   if p.get('merged_at') and p['merge_commit_sha'] == sha and p['base']['ref'] == api.config.trunk
                   and p['head']['ref'] == api.config.branch]
            require(len(prs) == 1, 'Previous metadata must identify exactly one approved Release PR')
            p, approved_sha = approved(api, prs[0]['number'])
            require(approved_sha == sha, 'Previous release approval/source mismatch')
            parents = git('rev-list', '--parents', '-n', '1', sha).split()[1:]
            require(len(parents) == 1, 'Previous approved Release PR must be squash-merged')
            try:
                merged_candidate(api, p, sha)
            except PublicationPending:
                raise ValueError('Earlier release publication is incomplete; cannot defer another release') from None
            raise PublicationPending('Previous approved release is awaiting publication; proposal deferred')
        require(tag is not None and tag['object']['type'] == 'commit' and tag['object']['sha'] == sha,
                'Previous release tag missing or inconsistent; reconcile partial release before proposing')
        # UI-created releases can retain main as the creation hint. GitHub ignores
        # that hint for existing tags; the immutable tag above proves the exact SHA.
        require(record is not None and record.get('draft') is False and record.get('prerelease') is False
                and record.get('immutable') is True and record.get('tag_name') == f'{api.config.tag_prefix}{current}'
                and record.get('target_commitish') in (sha, api.config.trunk),
                'Previous GitHub Release missing, incomplete or inconsistent; reconcile before proposing')
    else:
        baseline = json.loads(read(ref, api.config.baseline_file))
        require(baseline['version'] == current, 'Initial version differs from approved bootstrap baseline')
        sha = baseline['sha']
    require(sha == ref or sha in git('rev-list', '--first-parent', ref).splitlines(),
            'Release baseline must be on trunk first-parent history; verify the bootstrap boundary')
    exact_sha(sha)
    return current, sha


def candidate(api, ref):
    current, start = anchor(api, ref)
    changes = []
    for sha in git('rev-list', '--first-parent', '--reverse', f'{start}..{ref}').splitlines():
        prs = [p for p in api.pages(f'/commits/{sha}/pulls')
               if p.get('merged_at') and p['merge_commit_sha'] == sha and p['base']['ref'] == api.config.trunk]
        require(len(prs) == 1, f'Trunk commit {sha} must correspond to exactly one merged PR into trunk')
        p = prs[0]
        require(p['head']['ref'] != api.config.branch, 'Unrecorded release in source range')
        bump(p['title'])
        changes.append({'number': p['number'], 'title': p['title'], 'sha': sha})
    next_version = proposal(current, changes)
    if next_version is None:
        return None
    # Dates come from the last included source commit, never from the runner clock.
    date = git('show', '-s', '--format=%cs', ref)
    metadata = {'base_sha': ref, 'previous_version': current, 'version': next_version,
                'date': date, 'changes': changes}
    notes = f'## [{next_version}] {date}\n\n'
    for level, heading in [(3, 'Breaking changes'), (2, 'Features'), (1, 'Fixes'), (0, 'Other changes')]:
        entries = [c for c in changes if bump(c['title']) == level]
        if entries:
            notes += f'### {heading}\n\n'
            for c in entries:
                # Use a code span for titles, avoiding injected Markdown/HTML.
                title = c['title'].replace('`', "'").replace('<', '&lt;').replace('>', '&gt;')
                notes += f'- `{title}` ([#{c["number"]}](https://github.com/{api.repo}/pull/{c["number"]}), source `{c["sha"]}`)\n'
            notes += '\n'
    old = read(ref, api.config.changelog_file)
    position = re.search(r'^## \[', old, re.MULTILINE)
    require(position is not None, 'Historical changelog must have a version heading')
    require(f'## [{next_version}]' not in old, 'Proposed changelog version already exists')
    changelog = old[:position.start()] + notes + old[position.start():]
    return {'metadata': metadata, 'notes': notes, 'files': {
        api.config.version_file: next_version + '\n', api.config.changelog_file: changelog,
        api.config.candidate_file: json_text(metadata)}}


def validate_candidate(api, base, head, title, branch, head_repo):
    require(branch == api.config.branch and head_repo == api.repo, 'Release PR must use the reserved in-repository branch')
    wanted = candidate(api, base)
    require(wanted is not None, 'Release PR has no releasable changes')
    require(title == f'chore(release): {wanted["metadata"]["version"]}', 'Release PR title/version mismatch')
    changed = set(git('diff', '--name-only', base, head).splitlines())
    require(changed == api.config.files, 'Release PR may change only configured version, changelog and candidate metadata')
    for path, content in wanted['files'].items():
        require(read(head, path) == content, f'Non-reproducible Release PR file: {path}')
    return wanted


def validate_pr(api, p):
    require(p['base']['ref'] == api.config.trunk, 'PR must target configured trunk')
    base, head = exact_sha(p['base']['sha']), exact_sha(p['head']['sha'])
    # Fetch objects only; never checkout/execute untrusted PR code.
    fetch(api, base, f'refs/pull/{int(p["number"])}/head')
    if is_release(api, p):
        native_candidate(api, p)
        require(p.get('auto_merge') is None, 'Managed Release PR auto-merge is forbidden')
        return validate_candidate(api, base, head, p['title'], p['head']['ref'], p['head']['repo']['full_name'])
    bump(p['title'])
    merge_base = git('merge-base', base, head)
    changed = set(git('diff', '--name-only', merge_base, head).splitlines())
    require(not changed.intersection(api.config.files | {api.config.baseline_file}),
            'Normal PRs cannot alter release authority, history, candidate or bootstrap baseline')
    return None


def is_release(api, p):
    return (p['head']['ref'] == api.config.branch or p['head']['ref'].startswith('release/')
            or p['title'].startswith('chore(release):'))


def check_tooling(base, head):
    """Check candidate whitespace using Git data only; shared tests run in library CI."""
    subprocess.run(['git', 'diff', '--check', exact_sha(base), exact_sha(head)], check=True)


def propose(api, ref):
    require(api.request('')['default_branch'] == api.config.trunk, 'Configured trunk must be repository default branch')
    # Query the actual trunk each run; a queued push may no longer be the newest revision.
    require(api.request('/branches/' + quote(api.config.trunk, safe=''))['commit']['sha'] == ref, 'Stale proposal checkout; rerun on current trunk')
    pending = [p for p in api.pages('/pulls?' + urlencode({'state': 'open', 'base': api.config.trunk}))
               if is_release(api, p)]
    require(len(pending) <= 1, 'Competing release PRs exist; reconcile manually')
    if pending:
        require(pending[0]['head']['ref'] == api.config.branch and pending[0]['head']['repo']['full_name'] == api.repo,
                'Existing release PR is not the managed candidate')
        native_candidate(api, pending[0])
        require(pending[0].get('auto_merge') is None, 'Managed Release PR auto-merge is forbidden')
    try:
        wanted = candidate(api, ref)
    except PublicationPending as pending_publication:
        print(str(pending_publication))
        outputs(result='publication-pending')
        return
    if wanted is None:
        require(not pending, 'Existing release candidate no longer has releasable changes')
        print('No releasable changes; no Release PR')
        outputs(result='no-change')
        return
    branch = api.request(f'/git/ref/heads/{api.config.branch}', missing=True)
    old_sha = branch['object']['sha'] if branch else None
    if old_sha:
        fetch(api, 'refs/heads/' + api.config.branch)
    if old_sha and all(read(old_sha, p) == c for p, c in wanted['files'].items()):
        sha = old_sha
    else:
        blobs = [{'path': p, 'mode': '100644', 'type': 'blob', 'content': c} for p, c in wanted['files'].items()]
        tree = api.request('/git/trees', 'POST', {'base_tree': git('rev-parse', ref + '^{tree}'), 'tree': blobs})
        parents = [ref] if not old_sha else [old_sha, ref] if old_sha != ref else [ref]
        commit = api.request('/git/commits', 'POST', {
            'message': f'chore(release): {wanted["metadata"]["version"]}',
            'tree': tree['sha'], 'parents': parents})
        sha = commit['sha']
        # Never force-update even the candidate. Commits include its previous head as a parent.
        if branch:
            api.request(f'/git/refs/heads/{api.config.branch}', 'PATCH', {'sha': sha, 'force': False})
        else:
            api.request('/git/refs', 'POST', {'ref': f'refs/heads/{api.config.branch}', 'sha': sha})
    body = ('Human approval: review and squash-merge this PR to release this version. Never auto-merge.\n\n'
            f'Source inputs: `{ref}`. Release source will be the exact squash merge commit.\n\n' + wanted['notes'])
    title = f'chore(release): {wanted["metadata"]["version"]}'
    if pending:
        p = api.request(f'/pulls/{pending[0]["number"]}', 'PATCH', {'title': title, 'body': body})
    else:
        p = api.request('/pulls', 'POST', {'title': title, 'head': api.config.branch, 'base': api.config.trunk, 'body': body})
    # The trusted proposal run supplies both required statuses without relying on
    # native-token PR workflows. No candidate code is executed by this write token.
    for context in ['release-inputs', 'release-tests']:
        api.status(sha, 'pending', 'Trusted candidate checks running', context=context)
    try:
        current = api.pr(p['number'])
        require(current['head']['sha'] == sha and current['base']['sha'] == ref,
                'Candidate head or trunk changed before checks')
        validate_pr(api, current)
        check_tooling(ref, sha)
        current = api.pr(p['number'])
        require(current['head']['sha'] == sha and current['base']['sha'] == ref
                and api.request('/branches/' + quote(api.config.trunk, safe=''))['commit']['sha'] == ref,
                'Candidate head or trunk changed during checks; rerun proposal')
    except Exception:
        for context in ['release-inputs', 'release-tests']:
            api.status(sha, 'failure', 'Trusted candidate validation/checks failed', context=context)
        raise
    api.status(sha, 'success', 'Deterministic release metadata validated')
    api.status(sha, 'success', 'Shared deterministic candidate and mechanics checks passed', context='release-tests')
    outputs(result='candidate', pr=p['number'], head_sha=sha, version=wanted['metadata']['version'])
    print(f'Release PR #{p["number"]}: {title} ({sha})')


def approved(api, number):
    p = api.pr(number)
    require(p['merged'] and p['base']['ref'] == api.config.trunk and p['head']['ref'] == api.config.branch,
            'Publication requires a merged Release PR into trunk')
    native_candidate(api, p)
    require(p.get('auto_merge') is None, 'Managed Release PR auto-merge is forbidden')
    require(p['merged_by'] and p['merged_by']['type'] == 'User', 'Release PR merge must be performed by a human')
    reviews = {}
    for review in api.pages(f'/pulls/{number}/reviews'):
        if review['state'] not in ('COMMENTED', 'PENDING'):
            reviews[review['user']['login']] = review
    require(any(review['state'] == 'APPROVED' and review['user']['type'] == 'User' and
                review['commit_id'] == p['head']['sha'] for review in reviews.values()),
            'Release PR requires human approval of its exact final head commit')
    sha = p['merge_commit_sha']
    exact_sha(sha)
    return p, sha


def merged_candidate(api, p, sha):
    parents = git('rev-list', '--parents', '-n', '1', exact_sha(sha)).split()[1:]
    require(len(parents) == 1, 'Release PR must be squash-merged')
    wanted = validate_candidate(api, parents[0], sha, p['title'], api.config.branch, api.repo)
    head = exact_sha(p['head']['sha'])
    fetch(api, f'refs/pull/{int(p["number"])}/head')
    validate_candidate(api, parents[0], head, p['title'], api.config.branch, api.repo)
    require(git('rev-parse', sha + '^{tree}') == git('rev-parse', head + '^{tree}'),
            'Release merge tree must match the exact approved candidate head')
    return wanted


def preflight(api, number):
    require(os.environ.get('RELEASE_IMMUTABILITY_CONFIRMED') == 'true',
            'Admin must enable GitHub release immutability and confirm it before publication')
    p, sha = approved(api, number)
    require(api.request('')['default_branch'] == api.config.trunk, 'Configured trunk must be repository default branch')
    trunk = exact_sha(api.request('/branches/' + quote(api.config.trunk, safe=''))['commit']['sha'])
    fetch(api, trunk, sha, f'refs/pull/{int(number)}/head')
    require(sha in git('rev-list', '--first-parent', trunk).splitlines(),
            'Release merge must be on trunk first-parent history')
    wanted = merged_candidate(api, p, sha)
    v = wanted['metadata']['version']
    require(api.request(f'/git/ref/tags/{api.config.tag_prefix}{v}', missing=True) is None, 'Duplicate Git tag; refusing publication')
    require(api.request(f'/releases/tags/{api.config.tag_prefix}{v}', missing=True) is None, 'Duplicate GitHub Release; refusing publication')
    return dict(wanted, release_pr=p), sha


def publish(api, number):
    wanted, sha = preflight(api, number)
    v = wanted['metadata']['version']
    # Snapshot available evidence and validate before any publication mutation.
    document = manifest.generate(api, wanted, sha)
    payload = json_text(document).encode('utf-8')
    # POST creates only a fresh ref; no update/delete or duplicate recovery path.
    api.request('/git/refs', 'POST', {'ref': f'refs/tags/{api.config.tag_prefix}{v}', 'sha': sha})
    body = (wanted['notes'] + '\n### Release identity\n\n' +
            f'- Source: `{sha}`\n- Version: `{v}`\n- Tag: `{api.config.tag_prefix}{v}`\n' +
            f'- Approval: Release PR #{number}\n')
    # The already-created tag, not this creation hint, selects the source.
    # Using default trunk avoids workflow-write permission for older recovery SHAs
    # (that permission cannot be granted to native GITHUB_TOKEN).
    record = api.request('/releases', 'POST', {'tag_name': f'{api.config.tag_prefix}{v}', 'target_commitish': api.config.trunk,
                'name': f'{api.config.product} {v}', 'body': body, 'draft': True, 'prerelease': False})
    require(record.get('draft') is True and record.get('tag_name') == api.config.tag_prefix + v,
            'Created release must be the expected draft')
    release_id = record['id']
    require(type(release_id) is int and release_id > 0, 'Invalid draft release id')
    require(not api.pages(f'/releases/{release_id}/assets'), 'Draft already contains assets; refusing overwrite')
    asset = api.upload_manifest(release_id, payload)
    manifest.verify_asset(api, release_id, payload, asset['id'])
    source_tag = api.request(f'/git/ref/tags/{api.config.tag_prefix}{v}')
    require(source_tag['object']['type'] == 'commit' and source_tag['object']['sha'] == sha,
            'Draft release source tag mismatch; refusing publication')
    api.request(f'/releases/{record["id"]}', 'PATCH', {'draft': False})
    published = api.request(f'/releases/tags/{api.config.tag_prefix}{v}')
    tag = api.request(f'/git/ref/tags/{api.config.tag_prefix}{v}')
    require(published.get('immutable') is True,
            'GitHub Release is not immutable; admin configuration must be reconciled')
    require(published.get('draft') is False and published.get('prerelease') is False
            and published.get('tag_name') == f'{api.config.tag_prefix}{v}' and published.get('target_commitish') in (sha, api.config.trunk)
            and published.get('name') == f'{api.config.product} {v}'
            and published.get('body') == body and tag['object']['type'] == 'commit'
            and tag['object']['sha'] == sha, 'Published release identity/source/notes mismatch')
    require(published['id'] == release_id, 'Published release id mismatch')
    manifest.verify_asset(api, release_id, payload, asset['id'])
    outputs(result='published', pr=number, sha=sha, version=v, tag=api.config.tag_prefix + v,
            release_url=published['html_url'], immutable='true')
    print(f'Published {published["html_url"]}: {sha} -> {api.config.tag_prefix}{v} -> immutable GitHub Release')


def validate_statuses(api, number):
    p = api.pr(number)
    base = exact_sha(p['base']['sha'])
    head = exact_sha(p['head']['sha'])
    title = p['title']
    for context in ('release-inputs', 'release-tests'):
        api.status(head, 'pending', 'Trusted shared release validation running', context)
    try:
        require(not p.get('merged') and p.get('state', 'open') == 'open', 'Validation requires an open PR')
        validate_pr(api, p)
        if is_release(api, p):
            check_tooling(p['base']['sha'], head)
        current = api.pr(number)
        require(current['head']['sha'] == head and current['base']['sha'] == base and current['title'] == title,
                'PR head or trunk changed during validation; rerun validation')
    except Exception:
        for context in ('release-inputs', 'release-tests'):
            api.status(head, 'failure', 'Shared release input/mechanics validation failed', context)
        raise
    api.status(head, 'success', 'PR metadata and protected release files validated')
    api.status(head, 'success', 'Shared deterministic release policy/mechanics validated', 'release-tests')
    outputs(result='validated', pr=number, head_sha=head)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['propose', 'validate-pr', 'resolve', 'publish'])
    parser.add_argument('--pr', type=int)
    args = parser.parse_args()
    require(args.command == 'propose' or (args.pr is not None and args.pr > 0), 'Positive PR number is required')
    api = GitHub(Config.environment())
    if args.command == 'propose':
        propose(api, exact_sha(git('rev-parse', 'HEAD')))
    elif args.command == 'validate-pr':
        validate_statuses(api, args.pr)
    elif args.command == 'resolve':
        _, sha = approved(api, args.pr)
        outputs(result='resolved', pr=args.pr, sha=sha)
    else:
        publish(api, args.pr)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError, KeyError, UnicodeError) as error:
        # API bodies, request headers, subprocess output and token values stay out of logs.
        message = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'Release validation failed; inspect trusted configuration/history'
        print(message, file=sys.stderr)
        sys.exit(1)
