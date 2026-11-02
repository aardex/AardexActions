#!/usr/bin/env bash
# Only fixed labels and integer counts may leave this process.
set -o pipefail

unavailable() {
  printf '### Terraform plan\n\nSanitized overview unavailable (%s). No plan details were published.\n' "$1" >> "$GITHUB_STEP_SUMMARY"
}

if [[ "${PLAN_OUTCOME:-}" != success ]]; then
  unavailable 'plan did not succeed'
  exit 0
fi
if [[ ! -f tfplan.tfplan ]]; then
  unavailable 'saved plan is missing'
  exit 0
fi

umask 077
summary=$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/terraform-summary.XXXXXXXX") || exit 1
trap 'rm -f "$summary"' EXIT
# Terraform JSON and diagnostics stay in the pipe; neither is written to the log or disk.
if terraform show -json tfplan.tfplan 2>/dev/null | jq -er '
  def category:
    if . == ["no-op"] or . == ["read"] then "ignored"
    elif . == ["create"] then "create"
    elif . == ["update"] then "update"
    elif . == ["delete"] then "delete"
    elif . == ["create", "delete"] or . == ["delete", "create"] then "replace"
    else error("unsupported action") end;
  if type != "object" or (.format_version | type != "string") or ((.resource_changes // []) | type != "array") then error("invalid plan") else . end |
  [(.resource_changes // [])[] | .change.actions | category] as $actions |
  "### Terraform plan\n\n| Resource action | Count |\n| --- | ---: |\n" +
  (["create", "update", "delete", "replace"] | map(. as $kind | "| " + $kind + " | " + ([$actions[] | select(. == $kind)] | length | tostring) + " |") | join("\n")) +
  "\n\nReplacement is counted once, separately from create and delete. Addresses, values, outputs, and variables are omitted."
' > "$summary" 2>/dev/null; then
  cat "$summary" >> "$GITHUB_STEP_SUMMARY"
else
  unavailable 'plan could not be summarized'
fi
