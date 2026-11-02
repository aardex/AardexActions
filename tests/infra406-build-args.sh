#!/usr/bin/env bash
# Local regression tests: synthetic values only; no network or Docker access.
set -euo pipefail
root_dir=$(cd "$(dirname "$0")/.." && pwd)
action="$root_dir/azure-publish-docker/action.yml"
guard=$(sed -n '/^    - name: Reject NuGet token build arguments in secret mode$/,/^    - name: Build and push Docker image /p' "$action" | sed -n '/^      run: |$/,/^    - name: Build and push Docker image /p' | sed '1d;$d;s/^        //')
[[ -n "$guard" ]] || { echo 'Unable to locate guard' >&2; exit 1; }
grep -Fq "if: \${{ inputs.nuget-secret-mode == 'true' }}" "$action"
grep -Fq "inputs.nuget-secret-mode != 'true' && format('NUGET_PAT={0}', inputs.github-token) || ''" "$action"
grep -Fq '${{ inputs.build-args }}' "$action"

run_case() {
  local expected="$1" label="$2" input="$3" result output
  result=0
  output=$(EXTRA_BUILD_ARGS="$input" bash -e -o pipefail -c "$guard" 2>&1) || result=$?
  if [[ "$output" == *synthetic_secret* ]]; then
    printf 'FAIL: %s exposed the fixture value\n' "$label" >&2
    exit 1
  fi
  if [[ "$expected" == reject && "$result" == 0 ]] || [[ "$expected" == accept && "$result" != 0 ]]; then
    printf 'FAIL: %s (expected %s; exit %s)\n' "$label" "$expected" "$result" >&2
    exit 1
  fi
  printf 'PASS: %s\n' "$label"
}
run_case reject 'unquoted' 'NUGET_PAT=synthetic_secret'
run_case reject 'quoted' '"NUGET_PAT=synthetic_secret"'
run_case reject 'whitespace padded' '  "  NUGET_PAT=synthetic_secret  "  '
run_case reject 'tab padded' $'\t"\tNUGET_PAT=synthetic_secret"\t'
run_case reject 'bare key' 'NUGET_PAT'
run_case reject 'quoted bare key' '"NUGET_PAT"'
run_case reject 'second record' $'APP_VERSION=1.2.3\n"NUGET_PAT=synthetic_secret"'
run_case reject 'quoted multiline key' $'" \n NUGET_PAT=synthetic_secret\n"'
run_case reject 'quoted key with CSV fields' '"NUGET_PAT=synthetic_secret",EXTRA=1'
run_case reject 'UTF-8 BOM before key' $'"\357\273\277NUGET_PAT=synthetic_secret"'
run_case reject 'non-breaking space before key' $'"\302\240NUGET_PAT=synthetic_secret"'
run_case reject 'CRLF records' $'APP_VERSION=1.2.3\r\n"NUGET_PAT=synthetic_secret"'
run_case reject 'mixed record delimiters cannot hide a key' $'APP_VERSION=1.2.3,"NUGET_PAT_SUFFIX=value"\n"""NUGET_PAT=public"""\r"APP=hello\nNUGET_PAT=synthetic_secret"\r\n'
run_case reject 'non-ASCII prefix cannot hide a key' $'é"APP=foo\nNUGET_PAT=synthetic_secret"'
run_case reject 'unterminated CSV quote' '"APP_VERSION=1.2.3'
run_case accept 'ordinary unquoted arguments' $'APP_VERSION=1.2.3\nMODE=release'
run_case accept 'ordinary quoted argument' '"LABEL=hello,world"'
run_case accept 'ordinary multiline quoted value' $'"DESCRIPTION=hello\nNUGET_PAT=public-text\nworld"'
run_case accept 'quoted value with escaped quotes' '"DESCRIPTION=says ""hello"""'
run_case accept 'escaped quotes within multiline value' $'"DESCRIPTION=""quoted""\nNUGET_PAT=public-text"'
run_case accept 'quoted value with unicode' '"DESCRIPTION=café"'
run_case accept 'non-ASCII key is distinct' 'éNUGET_PAT=public-text'
run_case accept 'ordinary value containing name' 'MESSAGE=NUGET_PAT=public-text'
run_case accept 'non-sensitive similar key' 'NUGET_PAT_SUFFIX=public'
run_case accept 'comma stays in ordinary value' 'MESSAGE=hello,NUGET_PAT=public-text'
