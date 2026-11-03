#!/usr/bin/env python3
"""Create-only Azure Blob plan transport. No plan bytes or tokens are logged."""
import datetime as dt
from email.utils import format_datetime, parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_PLAN = 32 * 1024 * 1024  # Single Put Blob; the create-only role cannot stage blocks.
TTL = dt.timedelta(days=7)
SIMPLE = re.compile(r'^[A-Za-z0-9_.-]{1,100}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$')
SHA = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
ACCOUNT = re.compile(r'^[a-z0-9]{3,24}$')
CONTAINER = re.compile(r'^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$')
VERSION = re.compile(r'^\d+\.\d+\.\d+$')
ROOT = re.compile(r'^(?:\.|[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*)$')


class PlanError(Exception):
    pass


def require(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise PlanError('Invalid plan context or input.')
    return value


def context(env):
    repo = require(env.get('GITHUB_REPOSITORY', ''), REPO)
    environment = require(env.get('PLAN_ENVIRONMENT', ''), SIMPLE)
    if environment in ('.', '..') or any(part in ('.', '..') for part in repo.split('/')):
        raise PlanError('Invalid plan context or input.')
    workspace = require(env.get('PLAN_WORKSPACE', ''), SIMPLE)
    commit = require(env.get('PLAN_COMMIT', ''), SHA)
    version = require(env.get('PLAN_TERRAFORM_VERSION', ''), VERSION)
    root = require(env.get('PLAN_ROOT', ''), ROOT)
    return {'repo': repo, 'environment': environment, 'workspace': workspace,
            'commit': commit, 'tfversion': version, 'root': root}


def validate_id(plan_id, ctx):
    parts = plan_id.split('/')
    if len(parts) != 6 or '/'.join(parts[:2]) != ctx['repo'] or parts[2] != ctx['environment']:
        raise PlanError('Invalid plan identifier for this repository or environment.')
    if not all(re.fullmatch(r'[1-9][0-9]{0,19}', part) for part in parts[3:5]):
        raise PlanError('Invalid plan identifier.')
    try:
        if str(uuid.UUID(parts[5], version=4)) != parts[5]:
            raise ValueError()
    except ValueError:
        raise PlanError('Invalid plan identifier.') from None
    return plan_id


def blob_name(plan_id):
    return plan_id + '.tfplan'


def token():
    try:
        tenant = str(uuid.UUID(os.environ.get('PLAN_STORAGE_TENANT_ID', '')))
        value = subprocess.run(['az', 'account', 'get-access-token', '--tenant', tenant, '--resource',
                                'https://storage.azure.com/', '--query', 'accessToken', '-o', 'tsv'],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, timeout=60).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        raise PlanError('Azure Storage authentication failed.') from None
    if not value or '\n' in value:
        raise PlanError('Azure Storage authentication failed.')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward an Azure bearer token to a redirect target.


class BlobStore:
    def __init__(self, account, bearer):
        self.account = require(account, ACCOUNT)
        self.bearer = bearer
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, container, name, *, body=None, headers=None):
        require(container, CONTAINER)
        path = urllib.parse.quote(name, safe='/')
        url = f'https://{self.account}.blob.core.windows.net/{container}/{path}'
        request_headers = {'Authorization': 'Bearer ' + self.bearer,
                           'x-ms-version': '2021-12-02',
                           'x-ms-date': format_datetime(dt.datetime.now(dt.timezone.utc), usegmt=True)}
        request_headers.update(headers or {})
        if body is not None:
            request_headers['Content-Length'] = str(len(body))
        req = urllib.request.Request(url, data=body, method=method, headers=request_headers)
        try:
            with self.opener.open(req, timeout=120) as response:
                data = response.read(MAX_PLAN + 1) if method == 'GET' else b''
                if len(data) > MAX_PLAN:
                    raise PlanError('Stored plan exceeds the size limit.')
                return dict(response.headers.items()), data
        except (urllib.error.URLError, OSError, ValueError):
            # Never log server response bodies, URL, authorization or request details.
            raise PlanError('Azure Blob operation failed or a conditional create was rejected.') from None

    def create(self, container, name, data, metadata=None):
        headers = {'If-None-Match': '*', 'x-ms-blob-type': 'BlockBlob',
                   'Content-Type': 'application/octet-stream'}
        for key, value in (metadata or {}).items():
            headers['x-ms-meta-' + key] = value
        return self.request('PUT', container, name, body=data, headers=headers)

    def head(self, container, name):
        return self.request('HEAD', container, name)[0]

    def get(self, container, name, etag):
        return self.request('GET', container, name, headers={'If-Match': etag})[1]


def lower_headers(headers):
    return {key.lower(): value for key, value in headers.items()}


def publish(store, env, plan_path, *, plan_id=None):
    ctx = context(env)
    run = require(env.get('GITHUB_RUN_ID', ''), re.compile(r'^[1-9][0-9]{0,19}$'))
    attempt = require(env.get('GITHUB_RUN_ATTEMPT', ''), re.compile(r'^[1-9][0-9]{0,19}$'))
    plan_id = plan_id or f"{ctx['repo']}/{ctx['environment']}/{run}/{attempt}/{uuid.uuid4()}"
    validate_id(plan_id, ctx)
    if plan_id.split('/')[3:5] != [run, attempt]:
        raise PlanError('Plan identifier does not match this run.')
    try:
        with open(plan_path, 'rb') as stream:
            payload = stream.read(MAX_PLAN + 1)
    except OSError:
        raise PlanError('Saved plan is unavailable.') from None
    if not payload or len(payload) > MAX_PLAN:
        raise PlanError('Saved plan is empty or exceeds the 32 MiB limit.')
    digest = hashlib.sha256(payload).hexdigest()
    if digest != require(env.get('PLAN_SHA256', ''), DIGEST):
        raise PlanError('Saved plan changed after the review summary.')
    metadata = {**ctx, 'sha256': digest, 'runid': run, 'attempt': attempt,
                'createdutc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    store.create(env['PLAN_CONTAINER'], blob_name(plan_id), payload, metadata)
    return plan_id, digest


def acquire(store, env, output_dir):
    ctx = context(env)
    plan_id = validate_id(env.get('PLAN_ID', ''), ctx)
    expected = require(env.get('PLAN_SHA256', ''), DIGEST)
    headers = lower_headers(store.head(env['PLAN_CONTAINER'], blob_name(plan_id)))
    metadata = {key[10:]: value for key, value in headers.items() if key.startswith('x-ms-meta-')}
    for key, value in {**ctx, 'sha256': expected, 'runid': plan_id.split('/')[3],
                       'attempt': plan_id.split('/')[4]}.items():
        if metadata.get(key) != value:
            raise PlanError('Stored plan metadata does not match the requested plan.')
    try:
        now = parsedate_to_datetime(headers['date'])
        created = parsedate_to_datetime(headers['last-modified'])
        age = now - created
        etag = headers['etag']
        local_now = dt.datetime.now(dt.timezone.utc)
        if (not etag or age < dt.timedelta(0) or age >= TTL or
                abs((local_now - now).total_seconds()) > 120):
            raise ValueError()
        # Map the server's remaining lifetime to the runner clock, conservatively.
        expires_at = int((local_now + TTL - age).timestamp()) - 2
        if expires_at <= int(local_now.timestamp()):
            raise ValueError()
    except (KeyError, ValueError, TypeError, OverflowError):
        raise PlanError('Stored plan is expired or has invalid storage metadata.') from None
    data = store.get(env['PLAN_CONTAINER'], blob_name(plan_id), etag)
    if not data or hashlib.sha256(data).hexdigest() != expected:
        raise PlanError('Stored plan checksum does not match the reviewed checksum.')
    # Write locally before claiming, so failures cannot strand a claim unnecessarily.
    fd, path = tempfile.mkstemp(prefix='reviewed-tfplan-', dir=output_dir)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        store.create(env['EVENT_CONTAINER'], plan_id + '.claim', b'claimed\n')
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return plan_id, path, expires_at


def record(store, env):
    ctx = context(env)
    plan_id = validate_id(env.get('PLAN_ID', ''), ctx)
    status = env.get('APPLY_STATUS', '')
    if status not in ('success', 'failed'):
        raise PlanError('Invalid apply status.')
    record_data = json.dumps({'status': status, 'run_id': require(env.get('GITHUB_RUN_ID', ''),
                             re.compile(r'^[1-9][0-9]{0,19}$'))}, separators=(',', ':')).encode()
    store.create(env['EVENT_CONTAINER'], plan_id + '.result', record_data)
    return status


def emit_output(name, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(f'{name}={value}\n')


def main():
    env = os.environ
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ('publish', 'acquire', 'record'):
            raise PlanError('Invalid plan storage operation.')
        for key in ('PLAN_CONTAINER', 'EVENT_CONTAINER'):
            require(env.get(key, ''), CONTAINER)
        store = BlobStore(env.get('PLAN_STORAGE_ACCOUNT', ''), token())
        if sys.argv[1] == 'publish':
            plan_id, digest = publish(store, env, 'tfplan.tfplan')
            emit_output('plan-id', plan_id)
            emit_output('sha256', digest)
            with open(env['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
                stream.write(f"\nStored plan ID: `{plan_id}`  \nSHA-256: `{digest}`  \n"
                             f"Commit: `{env['PLAN_COMMIT']}`; environment: `{env['PLAN_ENVIRONMENT']}`; "
                             f"workspace: `{env['PLAN_WORKSPACE']}`; root: `{env['PLAN_ROOT']}`; "
                             f"Terraform: `{env['PLAN_TERRAFORM_VERSION']}`.\n")
        elif sys.argv[1] == 'acquire':
            plan_id, path, expires_at = acquire(store, env, env['RUNNER_TEMP'])
            try:
                emit_output('plan-path', path)
                emit_output('plan-id', plan_id)
                emit_output('expires-at', str(expires_at))
            except Exception:
                Path(path).unlink(missing_ok=True)
                raise
        else:
            record(store, env)
    except Exception:
        print('::error::Secure plan operation failed; consult the restricted troubleshooting guide.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
