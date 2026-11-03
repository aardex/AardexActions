#!/usr/bin/env bash
# Default output contains only fixed labels and counts; human-readable mode is opt-in.
set -o pipefail

unavailable() {
  printf '### Terraform plan\n\nSanitized overview unavailable (%s). No aggregate counts were published.\n' "$1" >> "$GITHUB_STEP_SUMMARY"
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
  "\n\nReplacement is counted once, separately from create and delete. Counts exclude addresses, values, outputs, and variables."
' > "$summary" 2>/dev/null; then
  cat "$summary" >> "$GITHUB_STEP_SUMMARY"
else
  unavailable 'plan could not be summarized'
fi

case "${PLAN_SUMMARY_MODE:-counts-only}" in
  counts-only) ;;
  human-readable)
    # Keep the final escaped section below GitHub's 1 MiB per-step limit, even
    # when every input byte expands to &amp;. A large or failed show is omitted.
    if terraform show -no-color tfplan.tfplan 2>/dev/null | head -c 180001 > "$summary"; then
      show_status=0
    else
      show_status=1
    fi
    size=$(wc -c < "$summary")
    if (( size > 180000 )); then
      printf '\nHuman-readable plan omitted: output exceeds 180000 bytes. Counts are shown when available.\n' >> "$GITHUB_STEP_SUMMARY"
    elif (( show_status != 0 || size == 0 )); then
      printf '\nHuman-readable plan unavailable. Counts remain available when generated.\n' >> "$GITHUB_STEP_SUMMARY"
    else
      {
        printf '\n<details>\n<summary>Human-readable Terraform plan (may contain sensitive data)</summary>\n\n<pre><code>\n'
        sed -e 's/\&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$summary"
        printf '\n</code></pre>\n</details>\n'
      } >> "$GITHUB_STEP_SUMMARY"
    fi
    ;;
  *)
    printf '\nUnsupported plan summary mode; only aggregate counts are shown.\n' >> "$GITHUB_STEP_SUMMARY"
    printf '%s\n' '::warning::Unsupported plan summary mode; only aggregate counts are shown.'
    ;;
esac
