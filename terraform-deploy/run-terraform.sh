#!/usr/bin/env bash
# Terraform output is sensitive. Publish only fixed guidance and the process status.
case "${1:-}" in
  init)
    stage=init; output=init-result.txt
    advice='Check backend access, provider and module access, and runner connectivity.' ;;
  validate)
    stage=validate; output=validate-result.txt
    advice='Check configuration and provider schema compatibility in a restricted environment.' ;;
  plan)
    stage=plan; output=result.txt
    advice='Check target access, state locking, and configuration in a restricted environment.' ;;
  apply)
    stage=apply; output=apply-result.txt
    advice='Changes may be partial. Inspect target and state before any retry.' ;;
  *)
    printf '%s\n' 'Invalid Terraform stage.' >&2
    exit 2 ;;
esac
shift
umask 077
# Replace any prior captured output so an existing file cannot retain permissive modes.
if rm -f -- "$output" 2>/dev/null; then
  if "$@" > "$output" 2>&1; then
    exit 0
  else
    status=$?
  fi
else
  status=$?
fi

printf '::error::Terraform %s failed (exit status %d). %s See terraform-deploy README: Failure diagnostics.\n' "$stage" "$status" "$advice"
# A summary write failure must not replace the original Terraform exit status.
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  { printf '### Terraform %s failed\n\nExit status %d. %s See terraform-deploy README: Failure diagnostics.\n' "$stage" "$status" "$advice" >> "$GITHUB_STEP_SUMMARY"; } 2>/dev/null || :
fi
exit "$status"
