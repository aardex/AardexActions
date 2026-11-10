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
trap 'rm -f "$summary" "$summary.excerpt"' EXIT
# Terraform JSON and diagnostics stay in the pipe; neither is written to the log or disk.
if terraform show -json tfplan.tfplan 2>/dev/null | jq -er '
  def category:
    if . == ["no-op"] or . == ["read"] then "ignored"
    elif . == ["create"] then "create"
    elif . == ["update"] then "update"
    elif . == ["delete"] then "delete"
    elif . == ["forget"] then "forget"
    elif . == ["create", "delete"] or . == ["delete", "create"] then "replace"
    else error("unsupported action") end;
  if type != "object" or (.format_version | type != "string") or ((.resource_changes // []) | type != "array") then error("invalid plan") else . end |
  [(.resource_changes // [])[] | .change.actions | category] as $actions |
  "### Terraform plan\n\n| Resource action | Count |\n| --- | ---: |\n" +
  (["create", "update", "delete", "replace", "forget"] | map(. as $kind | "| " + $kind + " | " + ([$actions[] | select(. == $kind)] | length | tostring) + " |") | join("\n")) +
  "\n\nReplacement is counted once, separately from create and delete. Counts exclude addresses, values, outputs, and variables."
' > "$summary" 2>/dev/null; then
  if cat "$summary" >> "$GITHUB_STEP_SUMMARY"; then
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then printf 'counts-ready=true\n' >> "$GITHUB_OUTPUT"; fi
  fi
else
  unavailable 'plan could not be summarized'
fi

case "${PLAN_SUMMARY_MODE:-counts-only}" in
  counts-only) ;;
  human-readable)
    # Publish at most 180000 raw bytes. HTML escaping can expand one byte to five
    # characters; this keeps the final step summary below GitHub's 1 MiB limit.
    # Oversized plans are truncated, not omitted, so the reviewed-plan handoff
    # still has a human excerpt; the saved tfplan remains complete in Blob.
    excerpt="$summary"
    truncated=false
    # head closes the pipe after the bounded read; with pipefail, Terraform may
    # exit 141 (SIGPIPE) even though the saved plan is valid. Capture both
    # statuses and treat SIGPIPE as success only when the output was truncated.
    set +o pipefail
    terraform show -no-color tfplan.tfplan 2>/dev/null | head -c 180001 > "$summary"
    show_pipe_status=("${PIPESTATUS[@]}")
    set -o pipefail
    terraform_status=${show_pipe_status[0]:-1}
    head_status=${show_pipe_status[1]:-1}
    size=$(wc -c < "$summary")
    if (( size > 180000 )); then
      if (( head_status != 0 || (terraform_status != 0 && terraform_status != 141) )); then
        show_status=1
      else
        show_status=0
        excerpt="${summary}.excerpt"
        if head -c 180000 "$summary" > "$excerpt"; then
          truncated=true
        else
          show_status=1
        fi
      fi
    elif (( terraform_status != 0 || head_status != 0 || size == 0 )); then
      show_status=1
    else
      show_status=0
    fi
    if (( show_status != 0 )); then
      printf '\nHuman-readable plan unavailable. Counts remain available when generated.\n' >> "$GITHUB_STEP_SUMMARY"
    else
      if (
        if [[ "$truncated" == true ]]; then
          printf '\n<details>\n<summary>Human-readable Terraform plan (truncated; may contain sensitive data)</summary>\n\n<pre><code>\n' || exit 1
        else
          printf '\n<details>\n<summary>Human-readable Terraform plan (may contain sensitive data)</summary>\n\n<pre><code>\n' || exit 1
        fi
        sed -e 's/\&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' "$excerpt" || exit 1
        if [[ "$truncated" == true ]]; then
          printf '\n[... excerpt truncated at 180000 bytes; the saved plan is complete ...]\n' || exit 1
        fi
        printf '\n</code></pre>\n</details>\n' || exit 1
      ) >> "$GITHUB_STEP_SUMMARY"; then
        if [[ "$truncated" == true ]]; then
          printf '\nHuman-readable plan excerpt truncated at 180000 bytes; counts and the saved plan remain complete.\n' >> "$GITHUB_STEP_SUMMARY"
        fi
        if [[ -n "${GITHUB_OUTPUT:-}" ]]; then printf 'human-ready=true\n' >> "$GITHUB_OUTPUT"; fi
      fi
    fi
    ;;
  *)
    printf '\nUnsupported plan summary mode; only aggregate counts are shown.\n' >> "$GITHUB_STEP_SUMMARY"
    printf '%s\n' '::warning::Unsupported plan summary mode; only aggregate counts are shown.'
    ;;
esac
