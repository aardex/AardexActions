#!/usr/bin/env bash
# Resolve a project override or create an explicit no-exceptions config in the
# checkout. Upstream scanners otherwise auto-discover repository/home configs.
set -euo pipefail

kind=${1:?Usage: resolve_scan_config.sh KIND [PROJECT_FILE]}
project_file=${2:-}

if [[ -n "$project_file" && ( "$project_file" == *$'\n'* || "$project_file" == *$'\r'* || ! -f "$project_file" ) ]]; then
  echo '::error::Configured scanner file must exist and have a single-line path.' >&2
  exit 1
fi

# Checkov merges auto-discovered configs even with --config-file supplied.
# An explicit empty file alone is NOT sufficient to override skips/baselines.
# Refuse any unselected implicit config rather than silently weaken the scan.
if [[ "$kind" == checkov ]]; then
  for dir in "${SCAN_DIRECTORY:-.}" . "${HOME:-/nonexistent}"; do
    for path in "$dir/.checkov.yaml" "$dir/.checkov.yml"; do
      if [[ -f "$path" ]] && { [[ -z "$project_file" ]] || [[ ! "$project_file" -ef "$path" ]]; }; then
        echo "::error::Checkov auto-discovers $path; pass it explicitly as config-file or remove it before scanning." >&2
        exit 1
      fi
    done
  done
fi

if [[ -n "$project_file" ]]; then
  printf '%s\n' "$project_file"
  exit 0
fi

# The default skip lists exclude this generated directory from scanning.
if [[ -L .security-reports ]]; then
  echo '::error::.security-reports cannot be a symbolic link.' >&2
  exit 1
fi
mkdir -p .security-reports
# Python supplies a portable random filename with the .yaml extension that
# Trivy needs to recognize its structured ignore format (BSD mktemp does not
# replace Xs followed by a suffix).
file=$(python3 - "$kind" <<'PY'
import os
import sys
import tempfile
fd, path = tempfile.mkstemp(prefix=sys.argv[1] + '.', suffix='.yaml', dir='.security-reports')
os.close(fd)
# Docker actions mount the checkout at a different absolute path; use a
# checkout-relative filename so the inner container can read the same file.
print(os.path.relpath(path, os.getcwd()))
PY
)
case "$kind" in
  checkov) printf 'skip-check: []\n' > "$file" ;;
  trivy-config) printf '{}\n' > "$file" ;;
  trivy-ignore) printf 'vulnerabilities: []\nmisconfigurations: []\nsecrets: []\n' > "$file" ;;
  *) rm -f "$file"; echo "::error::Unknown scan configuration kind: $kind" >&2; exit 1 ;;
esac
printf '%s\n' "$file"
