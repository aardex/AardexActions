#!/usr/bin/env python3
"""CI-only AST, action metadata, Bash syntax and local Markdown link validation."""
import ast
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import unquote

import yaml
from jsonschema import Draft202012Validator
import manifest
import gates

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def check():
    Draft202012Validator.check_schema(manifest.SCHEMA)
    for path in ROOT.glob('examples/gates-*.json'):
        gates.policy(path.read_text())
    example = json.loads((ROOT / 'examples/release-manifest.json').read_text())
    Draft202012Validator(manifest.SCHEMA).validate(example)
    manifest.validate(example, example['release']['repository'],
                      {'version': example['release']['version'], 'changes': example['changes']},
                      example['release']['sha'], example['release_pr']['head_sha'], 'v')
    for path in ROOT.rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    action = yaml.safe_load((ROOT / 'action.yml').read_text())
    assert action['runs']['using'] == 'composite'
    inputs = action['inputs']
    assert 'github-token' not in inputs, 'Credential overrides are outside the public interface'
    assert set(inputs) == {
        'command', 'pr', 'trunk-branch', 'version-file', 'changelog-file',
        'candidate-file', 'baseline-file', 'managed-branch', 'release-name', 'tag-prefix',
        'immutability-confirmed', 'manifest-data', 'gate-policy-sha',
    }
    assert inputs['command']['required'] is True
    assert set(action['outputs']) == {'result', 'pr', 'head-sha', 'version', 'sha', 'tag', 'release-url', 'immutable'}
    step, = action['runs']['steps']
    assert step['id'] == 'engine' and step['shell'] == 'bash'
    assert step['env']['GH_TOKEN'] == '${{ github.token }}', 'Use the consumer native GITHUB_TOKEN directly'
    # Data enters through environment variables, never shell expression interpolation.
    assert '${{' not in step['run'], 'Never interpolate context or secret expressions into shell code'
    assert 'GH_TOKEN' not in step['run'] and 'GITHUB_TOKEN' not in step['run'], 'Keep token values out of shell code'
    assert 'python3 -I "$RELEASE_ACTION_PATH/release.py"' in step['run']
    for name in re.findall(r'inputs\.([\w-]+)', str(step['env'])):
        assert name in inputs, name
    for output in action['outputs'].values():
        assert re.fullmatch(r'\$\{\{ steps\.engine\.outputs\.[a-z_]+ \}\}', output['value'])
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp, 'action.sh')
        script.write_text(step['run'])
        subprocess.run(['bash', '-n', str(script)], check=True)

    count = 0
    for source in [REPO / 'README.md', REPO / 'docs/development.md', *ROOT.rglob('*.md')]:
        for target in re.findall(r'\[[^\]\n]*\]\(([^)\s]+)\)', source.read_text()):
            if re.match(r'^[a-z]+:', target):
                continue
            pathname, _, anchor = unquote(target).partition('#')
            resolved = (source.parent / pathname).resolve() if pathname else source
            assert resolved.exists(), f'{source.relative_to(REPO)}: missing {target}'
            if anchor and resolved.suffix == '.md':
                headings = re.findall(r'^#+\s+(.+)$', resolved.read_text(), re.MULTILINE)
                slugs = {re.sub(r'[^\w\- ]', '', h.replace('`', '').lower()).replace(' ', '-') for h in headings}
                assert anchor in slugs, f'{source.relative_to(REPO)}: missing heading {target}'
            count += 1
    print(f'Manifest schema/example, AST, composite metadata, Bash syntax and {count} local documentation links passed')


if __name__ == '__main__':
    check()
