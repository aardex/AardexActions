# Operations and observability

These are job-scoped composite actions, not a persistent service. There is no repository-defined on-call rota, monitoring dashboard, alert policy, SLO or production runbook. The consumer repository and target platforms own runtime monitoring and incident response; request those links from the responsible owner rather than inventing them here.

Available evidence at this revision:

- GitHub Actions step/job status and logs in the **consumer** workflow run. Failures in setup, build, test, publish or deploy are surfaced there; check the action ref and the failing step before troubleshooting. Do not share raw logs until reviewed for credentials or generated config.
- Terraform deploy/destroy upload `tfplan`/`tfdestroy` artifacts containing saved plan, JSON and `result.txt`, retention 15 days. Upload and `terraform show` use `if: always()` and may report additional errors when planning failed. Artifacts can expose sensitive infrastructure data; follow consumer access rules.
- `terraform-docs` uploads generated documentation; .NET actions run tests, and .NET App Service/Java actions can send coverage to Codecov when configured. Container App deploy uses Trivy with HIGH/CRITICAL exit-code 1 unless `skip-check` is true. A scan passing is not a production health check.
- After a target-side deployment, consult Azure App Service/Functions/Container Apps, ACR, GitHub Packages or the relevant consumer's telemetry for runtime state. This repository neither configures those signals nor proves deployment health from a completed job.

For triage, start with [troubleshooting](troubleshooting.md); for the action's exact parameters see its `action.yml`. Incident escalation, resource inventory, alert routing and recovery authority must come from the consumer/organization owner.
