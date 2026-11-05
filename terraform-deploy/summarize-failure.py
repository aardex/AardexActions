#!/usr/bin/env python3
"""Append a bounded, escaped stderr excerpt without writing it to the log."""
import html
import os
import re
import sys

MAX_BYTES = 32000

with open(sys.argv[1], 'rb') as stream:
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(max(0, size - MAX_BYTES))
    excerpt = stream.read(MAX_BYTES).decode('utf-8', errors='replace')

excerpt = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', excerpt)
with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
    if size > MAX_BYTES:
        summary.write(f'\nDiagnostic truncated to the last {MAX_BYTES} bytes.\n')
    summary.write('\n<details>\n<summary>Terraform error (may contain sensitive data)</summary>\n\n'
                  '<pre><code>\n' + html.escape(excerpt, quote=False) + '\n</code></pre>\n</details>\n')
