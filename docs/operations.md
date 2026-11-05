# Operations and observability

These are job-scoped composite actions, not a persistent service. There is no repository-defined on-call rota, monitoring dashboard, alert policy, SLO or production runbook. The consumer repository and target platforms own runtime monitoring and incident response; request those links from the responsible owner rather than inventing them here.

Available evidence at this revision:

- GitHub Actions step/job status and logs in the **consumer** workflow run. Failures in setup, build, test, publish or deploy are surfaced there; check the action ref and the failing step before troubleshooting. Do not share raw logs until reviewed for credentials or generated config.
- Terraform deploy defaults to a sanitized count summary and can optionally publish a human-readable plan. Failed init, validate and plan steps automatically publish a bounded stderr excerpt that may contain sensitive data. The saved plan and full captured output remain on the runner; see its [failure diagnostics](../terraform-deploy/README.md#failure-diagnostics) and [restricted review procedure](../terraform-deploy/README.md#restricted-detailed-review). Existing historical artifacts remain subject to their retention. Terraform destroy still uploads `tfdestroy` artifacts containing saved plan, JSON and `result.txt` for 15 days; they can expose sensitive infrastructure data.
- `terraform-docs` uploads generated documentation; .NET actions run tests, and .NET App Service/Java actions can send coverage to Codecov when configured. Container App deploy uses Trivy with HIGH/CRITICAL exit-code 1 unless `skip-check` is true. A scan passing is not a production health check.
- After a target-side deployment, consult Azure App Service/Functions/Container Apps, ACR, GitHub Packages or the relevant consumer's telemetry for runtime state. This repository neither configures those signals nor proves deployment health from a completed job.

For triage, start with [troubleshooting](troubleshooting.md); for the action's exact parameters see its `action.yml`. Incident escalation, resource inventory, alert routing and recovery authority must come from the consumer/organization owner.
