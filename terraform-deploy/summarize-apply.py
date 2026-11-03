#!/usr/bin/env python3
"""Render bounded Terraform apply diagnostics without logging captured output."""
import html
import os
from pathlib import Path
import re

MAX_BYTES = 180000  # HTML escaping expands at most fivefold, below 1 MiB.


def cell(value):
    value = value[:512].replace('\r', ' ').replace('\n', ' ')
    return html.escape(value, quote=False).replace('|', '&#124;')


def render():
    outcome = os.environ.get('APPLY_OUTCOME', '')
    if outcome not in ('success', 'failure', 'cancelled'):
        outcome = 'unknown'
    exit_code = os.environ.get('APPLY_EXIT_CODE', '')
    if not exit_code.isascii() or not exit_code.isdigit() or int(exit_code) > 255:
        exit_code = 'unavailable'
    mode = os.environ.get('APPLY_SUMMARY_MODE', 'counts-only')
    fields = [('Status', outcome), ('Exit code', exit_code)]
    for label, key in [('Environment', 'APPLY_ENVIRONMENT'), ('Commit', 'APPLY_COMMIT'),
                       ('Plan ID', 'APPLY_PLAN_ID')]:
        if os.environ.get(key):
            fields.append((label, os.environ[key]))
    excerpt = None
    size = 0
    path = Path('apply-result.txt')
    if exit_code != 'unavailable' and os.environ.get('APPLY_OUTPUT_READY') == 'true' and path.is_file():
        with path.open('rb') as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - MAX_BYTES))
            excerpt = stream.read(MAX_BYTES).decode('utf-8', errors='replace')
        excerpt = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', excerpt)
    if outcome == 'success' and exit_code == '0' and excerpt is not None:
        counts = re.search(r'(?m)^Apply complete! Resources: ([0-9]{1,20}) added, '
                           r'([0-9]{1,20}) changed, ([0-9]{1,20}) destroyed\.[ \t]*$', excerpt)
        if counts:
            fields.append(('Resources', f'{counts[1]} added, {counts[2]} changed, {counts[3]} destroyed'))
    summary = '### Terraform apply\n\n| Field | Value |\n| --- | --- |\n'
    summary += ''.join(f'| {label} | <code>{cell(value)}</code> |\n' for label, value in fields)

    if mode == 'human-readable':
        if excerpt is None:
            summary += '\nApply output unavailable.\n'
        else:
            if size > MAX_BYTES:
                summary += f'\nOutput truncated to the last {MAX_BYTES} bytes.\n'
            summary += ('\n<details>\n<summary>Terraform apply output (may contain sensitive data)</summary>\n\n'
                        '<pre><code>\n' + html.escape(excerpt, quote=False) + '\n</code></pre>\n</details>\n')
    elif mode != 'counts-only':
        summary += '\nUnsupported apply summary mode; only status is shown.\n'

    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
        stream.write(summary)


if __name__ == '__main__':
    render()
