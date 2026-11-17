#!/usr/bin/env python3
"""Read-only release evidence collector for the aardex-release-readiness skill.

Prints JSON facts that GitHub already holds for a managed Release PR or a
published release. It issues GET requests only, through the caller's own `gh`
authentication. It does not validate, approve, score or write anything: the
release-management engine and GitHub rulesets own deterministic decisions.

Usage:
  collect_evidence.py --repo aardex/keycloak --pr 29
  collect_evidence.py --repo aardex/TerraformGithubRunner --tag v1.1.0
"""
import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

# Same pattern as release-management/manifest.py (JIRA); a test guards drift.
JIRA = re.compile(r'(?<![A-Za-z0-9_-])[A-Z][A-Z0-9]+-[1-9][0-9]*(?![A-Za-z0-9_-])')
ACTION_PIN = re.compile(r'aardex/AardexActions/release-management@([0-9A-Za-z._/-]+)')
GATE_PIN = re.compile(r'gate-policy-sha:\s*["\']?([0-9a-f]{40})')
CHANGELOG_HEADING = re.compile(r'^## \[([^\]]+)\]', re.MULTILINE)
RELEASE_FILES = ('version.txt', 'CHANGELOG.md', '.release/candidate.json',
                 '.release/baseline.json', '.release/gates.json')
MANIFEST_ASSET = 'release-manifest.json'
MAX_FILES_PER_PR = 300


class NotFound(Exception):
    pass


class Gh:
    """Minimal GET-only wrapper around `gh api`."""

    def _run(self, args, binary=False):
        proc = subprocess.run(['gh', 'api', '-X', 'GET', *args], capture_output=True, text=not binary)
        if proc.returncode != 0:
            err = proc.stderr if isinstance(proc.stderr, str) else proc.stderr.decode(errors='replace')
            if 'HTTP 404' in err:
                raise NotFound(args[-1])
            raise RuntimeError(err.strip()[:300])
        return proc.stdout

    def get(self, path):
        out = self._run(['-H', 'Accept: application/vnd.github+json', path])
        return json.loads(out) if out.strip() else None

    def pages(self, path):
        out = self._run(['--paginate', '--slurp', '-H', 'Accept: application/vnd.github+json', path])
        return json.loads(out) if out.strip() else []

    def raw(self, path):
        return self._run(['-H', 'Accept: application/octet-stream', path], binary=True)


def flatten(pages, key=None):
    items = []
    for page in pages:
        items.extend(page.get(key, []) if key else page)
    return items


class Collector:
    def __init__(self, api, repo):
        self.api, self.repo = api, repo
        self.errors, self.missing = [], []

    def _try(self, what, fn, default=None):
        try:
            return fn()
        except NotFound:
            self.missing.append(what)
            return default
        except RuntimeError as exc:  # never silently treat an API failure as absence
            self.errors.append({'what': what, 'error': str(exc)})
            return default

    def file_at(self, path, ref):
        data = self._try(f'{path}@{ref[:12]}', lambda: self.api.get(f'repos/{self.repo}/contents/{path}?ref={ref}'))
        if not data or 'content' not in data:
            return None
        return base64.b64decode(data['content']).decode('utf-8', errors='replace')

    def pr(self, number):
        p = self.api.get(f'repos/{self.repo}/pulls/{number}')
        return {
            'number': p['number'], 'title': p['title'], 'state': p['state'], 'draft': p.get('draft'),
            'author': p['user']['login'], 'author_type': p['user']['type'],
            'head_ref': p['head']['ref'], 'head_sha': p['head']['sha'], 'base_ref': p['base']['ref'],
            'merged': p.get('merged'), 'merge_sha': p.get('merge_commit_sha') if p.get('merged') else None,
            'merged_by': (p.get('merged_by') or {}).get('login'), 'merged_at': p.get('merged_at'),
            'url': p['html_url'],
        }

    def reviews(self, number, head_sha):
        items = flatten(self._try(f'reviews#{number}', lambda: self.api.pages(
            f'repos/{self.repo}/pulls/{number}/reviews?per_page=100'), default=[]))
        latest = {}
        for r in items:  # chronological; keep each reviewer's latest non-comment review
            if r.get('state') != 'COMMENTED':
                latest[r['user']['login']] = r
        return [{'reviewer': login, 'reviewer_type': r['user']['type'], 'state': r['state'],
                 'commit_id': r.get('commit_id'), 'on_head': r.get('commit_id') == head_sha,
                 'submitted_at': r.get('submitted_at')} for login, r in sorted(latest.items())]

    def checks(self, sha):
        status = self._try(f'status@{sha[:12]}', lambda: self.api.get(
            f'repos/{self.repo}/commits/{sha}/status'), default={}) or {}
        runs = flatten(self._try(f'check-runs@{sha[:12]}', lambda: self.api.pages(
            f'repos/{self.repo}/commits/{sha}/check-runs?per_page=100'), default=[]), 'check_runs')
        return {
            'sha': sha,
            'statuses': sorted(({'context': s['context'], 'state': s['state'],
                                 'creator': (s.get('creator') or {}).get('login'), 'updated_at': s.get('updated_at')}
                                for s in status.get('statuses', [])), key=lambda s: s['context']),
            'check_runs': sorted(({'name': r['name'], 'status': r['status'], 'conclusion': r.get('conclusion'),
                                   'app': (r.get('app') or {}).get('slug'), 'app_id': (r.get('app') or {}).get('id'),
                                   'completed_at': r.get('completed_at'), 'url': r.get('html_url')}
                                  for r in runs), key=lambda r: (r['name'], r['completed_at'] or '')),
        }

    def workflow_pins(self, ref):
        listing = self._try(f'.github/workflows@{ref[:12]}', lambda: self.api.get(
            f'repos/{self.repo}/contents/.github/workflows?ref={ref}'), default=[]) or []
        pins = {}
        for entry in listing:
            if not entry['name'].endswith(('.yml', '.yaml')):
                continue
            text = self.file_at(entry['path'], ref) or ''
            action, gate = sorted(set(ACTION_PIN.findall(text))), sorted(set(GATE_PIN.findall(text)))
            if action or gate:
                pins[entry['path']] = {'release_management': action, 'gate_policy_sha': gate}
        return pins

    def included_prs(self, changes):
        result = []
        for change in changes:
            n = change['number']
            files = flatten(self._try(f'files#{n}', lambda: self.api.pages(
                f'repos/{self.repo}/pulls/{n}/files?per_page=100'), default=[]))
            result.append({'number': n, 'title': change['title'], 'sha': change['sha'],
                           'jira_keys': sorted(set(JIRA.findall(change['title']))),
                           'files': [f['filename'] for f in files[:MAX_FILES_PER_PR]],
                           'files_truncated': len(files) > MAX_FILES_PER_PR})
        return result

    def release(self, tag):
        rel = self._try(f'release {tag}', lambda: self.api.get(f'repos/{self.repo}/releases/tags/{tag}'))
        if rel is None:
            return None
        ref = self._try(f'tag ref {tag}', lambda: self.api.get(f'repos/{self.repo}/git/ref/tags/{tag}'))
        tag_sha = None
        if ref:
            obj = ref['object']
            if obj['type'] == 'tag':  # annotated tag: dereference to the commit
                obj = self.api.get(f'repos/{self.repo}/git/tags/{obj["sha"]}')['object']
            tag_sha = obj['sha']
        assets = [{'name': a['name'], 'size': a['size'], 'state': a['state'], 'digest': a.get('digest')}
                  for a in rel.get('assets', [])]
        out = {'tag': tag, 'tag_sha': tag_sha, 'name': rel.get('name'), 'draft': rel.get('draft'),
               'prerelease': rel.get('prerelease'), 'immutable': rel.get('immutable'),
               'published_at': rel.get('published_at'), 'url': rel.get('html_url'), 'assets': assets,
               'manifest': None}
        asset = next((a for a in rel.get('assets', []) if a['name'] == MANIFEST_ASSET), None)
        if asset is None:
            self.missing.append(f'{MANIFEST_ASSET} on release {tag}')
            return out
        data = self._try(f'{MANIFEST_ASSET} download', lambda: self.api.raw(
            f'repos/{self.repo}/releases/assets/{asset["id"]}'))
        if data is not None:
            out['manifest'] = summarize_manifest(data, asset.get('digest'))
        return out


def summarize_manifest(data, github_digest):
    digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    doc = json.loads(data)
    sections = {k: (doc[k].get('state') if isinstance(doc.get(k), dict) else None)
                for k in ('artifacts', 'migrations', 'dependencies', 'sbom', 'provenance')}
    return {
        'sha256': digest, 'github_digest': github_digest,
        'digest_matches_github': github_digest == digest if github_digest else None,
        'schema_version': doc.get('schema_version'), 'release': doc.get('release'),
        'release_pr': doc.get('release_pr'), 'jira_keys': doc.get('jira_keys'),
        'change_numbers': [c['number'] for c in doc.get('changes', [])],
        'sections': sections,
        'section_reasons': {k: doc[k].get('reason') for k in sections if isinstance(doc.get(k), dict)},
        'checks': [{'name': c['name'], 'kind': c.get('kind'), 'checked_sha': c.get('checked_sha'),
                    'state': c.get('state'), **(c.get('outcome') or {})} for c in doc.get('checks', [])],
        'gate_evidence_present': 'gate_evidence' in doc,
        'generator': doc.get('generator'),
    }


def parse_json(text, what, collector):
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError as exc:
        collector.errors.append({'what': what, 'error': f'invalid JSON: {exc}'})
        return None


def collect(api, repo, pr=None, tag=None):
    c = Collector(api, repo)
    facts = {'collector': 'aardex-release-readiness/collect_evidence.py', 'repository': repo,
             'collected_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
             'note': 'Facts copied from GitHub. No validation, approval or readiness verdict.'}
    release = c.release(tag) if tag else None
    if pr is None and release and release.get('manifest') and release['manifest'].get('release_pr'):
        pr = release['manifest']['release_pr']['number']
    if pr is None:
        raise SystemExit('A --pr is required when the release has no manifest naming its Release PR.')

    p = c.pr(pr)
    head = p['head_sha']
    facts['release_pr'] = p
    facts['reviews'] = c.reviews(pr, head)
    files = {path: c.file_at(path, head) for path in RELEASE_FILES}
    candidate = parse_json(files['.release/candidate.json'], 'candidate.json', c)
    changelog = files['CHANGELOG.md']
    facts['release_files_at_head'] = {
        'version_txt': files['version.txt'].strip() if files['version.txt'] else None,
        'changelog_headings': CHANGELOG_HEADING.findall(changelog)[:5] if changelog else None,
        'candidate': candidate,
        'baseline': parse_json(files['.release/baseline.json'], 'baseline.json', c),
        'gates_policy': parse_json(files['.release/gates.json'], 'gates.json', c),
    }
    if candidate is not None and 'gate_snapshot' not in candidate:
        c.missing.append('gate_snapshot in candidate.json (no gate policy pinned for this candidate)')
    facts['workflow_pins'] = c.workflow_pins(head)
    pinned = sorted({sha for v in facts['workflow_pins'].values() for sha in v['gate_policy_sha']})
    facts['pinned_gate_policies'] = {sha: parse_json(c.file_at('.release/gates.json', sha), f'gates.json@{sha}', c)
                                     for sha in pinned}
    facts['checks'] = [c.checks(head)] + ([c.checks(p['merge_sha'])] if p['merge_sha'] else [])
    facts['included_prs'] = c.included_prs(candidate.get('changes', [])) if candidate else []
    if release is None and candidate and p['merged']:
        guess = f'v{candidate["version"]}'
        release = c.release(guess)
    facts['release'] = release
    facts['missing'] = sorted(set(c.missing))
    facts['api_errors'] = c.errors
    return facts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', required=True, help='owner/name')
    parser.add_argument('--pr', type=int, help='managed Release PR number')
    parser.add_argument('--tag', help='published release tag, e.g. v1.1.0')
    args = parser.parse_args(argv)
    if not args.pr and not args.tag:
        parser.error('give --pr and/or --tag')
    json.dump(collect(Gh(), args.repo, args.pr, args.tag), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
