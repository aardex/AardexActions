# Terraform deploy to Azure

This composite action supports legacy deploys and an opt-in reviewed plan/apply handoff. See [deployment and approval boundaries](../docs/deployment.md) and [configuration/data handling](../docs/configuration.md) before running it.

| Input | Required | Default / behavior |
| --- | --- | --- |
| `execution-mode` | No | `legacy` (default), `reviewed-plan`, or `reviewed-apply` |
| `azure-credentials` | Yes | Service-principal JSON with `clientId`, `clientSecret`, `tenantId`, `subscriptionId` |
| `github-token` | Yes | Token with read access to referenced private GitHub modules |
| `azure-subscription` | No | Overrides `subscriptionId` from credentials |
| `directory` | No | `terraform` |
| `apply` | No | `'false'`; `'true'` applies the saved plan with `-auto-approve` |
| `needs-approval` | No | Declared as `'true'` but **unused**; does not pause or protect apply |
| `tfvars-content` | No | Writes `terraform.tfvars` in `directory` when nonempty |
| `plan-args` | No | Additional whitespace-split flags for `terraform plan` |
| `plan-summary-mode` | No | `counts-only` (default); opt in to `human-readable` only after assessing plan visibility and exposure |
| `apply-summary-mode` | No | `counts-only` (default); opt in to `human-readable` only after assessing apply output exposure |
| `plan-storage` | No | `none` (default); `azure-blob` stores a plan for reviewed apply and requires `apply: 'false'` |
| `plan-storage-account` | For Blob mode | Private plan-storage account name |
| `plan-storage-container`, `plan-events-container` | No | `tfplans` and `tfplan-events` respectively |
| `plan-environment` | For Blob mode | Target environment bound into plan metadata and identifier |
| `plan-id` | For reviewed apply | Plan ID copied from the reviewed plan summary |

`legacy` preserves existing plan and same-job optional apply behavior, including the existing Blob opt-in. `reviewed-plan` requires `apply: 'false'`, `plan-storage: azure-blob`, `plan-summary-mode: human-readable`, a storage account and environment; it never applies. `reviewed-apply` requires `apply: 'false'`, storage settings and the plan ID. It reads the commit, workspace, root, Terraform version and checksum from the stored metadata, checks out that commit, then delegates to the saved-plan action without generating a plan. `plan-storage` can be its default `none` or `azure-blob`. Unsupported or conflicting values fail before Azure login. The caller must supply the intended environment and Terraform directory independently, and must allow the action to check out the stored commit in the workspace.

The unified action delegates reviewed apply to `terraform-apply-saved` pinned at `53c4effaa17146b2beb1e1c44f19f6c7667c63ea`. This preserves the existing Blob/claim contract without a second apply implementation. Maintain this pin when reviewing changes to the saved-apply implementation or the shared apply-summary renderer; both paths must use the same renderer revision. The plan outputs include `plan-id`, `plan-sha256`, `plan-commit`, `plan-workspace`, and `plan-root`; the job summary also identifies the Terraform version. During apply those values are derived from Blob metadata, displayed in the run summary and checked against the downloaded plan and actual execution context.

Uses Terraform 1.13.3, runs `terraform init -upgrade -input=false`, `terraform validate -no-color`, then saves `tfplan.tfplan`. The binary plan and captured Terraform output (`init-result.txt`, `validate-result.txt`, `result.txt` and `apply-result.txt`) remain on the runner and are not uploaded by this action. `terraform show -json` is streamed directly into a filter. By default the job summary contains only fixed action categories and aggregate resource counts; replacements count once, separately from creates and deletes. The counts omit addresses, resource types, indices, values, outputs and variables. Unsupported action combinations, an invalid or missing plan, or a failed plan produce a generic unavailable message instead. The plan's exit status controls the step; apply runs only after a successful plan and preceding steps. The action no longer explicitly echoes plan arguments. Azure login and other consumer steps can still produce logs that require access controls and review. Do not put secrets or variable values in `plan-args`: GitHub Actions may expose step environment values; use the protected `tfvars-content` input instead.

### Optional human-readable plan and security

Set `plan-summary-mode: 'human-readable'` to add `terraform show -no-color tfplan.tfplan` in a collapsible section below the counts. **This publishes the human-readable plan to the consumer workflow run summary and may expose secrets and infrastructure identifiers.** Terraform redacts values it recognizes as sensitive; unmarked, transformed or provider-specific values can appear. The plan can contain resource addresses, attribute values, output values and identifiers. A private repository alone does not make this output safe: use this mode only if every user and integration able to view the run is authorized for all plan contents and the owner accepts that exposure. Prefer the default when that cannot be established. A public consumer repository is unsuitable for sensitive plan output. See [Terraform sensitive-data guidance](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).

The summary appears on the workflow run page, not behind an additional per-secret access boundary. Verify the consumer repository's effective reader and integration access and retention rules; environment approvals do not create a separate confidentiality boundary for the summary. GitHub documents that summaries automatically mask known secrets, but [redaction is not guaranteed](https://docs.github.com/en/actions/reference/security/secure-use), especially for structured, transformed, generated or unregistered values. Do not rely on it to make a plan safe. If sensitive information is published, follow the incident process: [delete the workflow run](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary) to remove its summaries and rotate exposed credentials as appropriate.

GitHub limits a [step summary to 1 MiB](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary); an upload failure does not fail the job. To preserve the count summary, this action publishes at most the first 180000 bytes of the human-readable plan and marks the excerpt as truncated when the plan is larger; it omits the section only when the plan cannot be rendered. It buffers at most 180001 bytes in a private runner-local temporary file and removes it on normal exit; the Markdown is escaped before publication. Runner termination may leave temporary files on persistent runners. The limit is conservative to account for HTML escaping. The complete saved plan remains in secure Blob storage; the truncated excerpt is only the human summary. Unknown modes produce a warning and only the counts; secure Blob publication fails for an unsupported mode or unavailable required summary. No saved plan, JSON plan or full captured CLI-output artifact is uploaded by this action.

### Apply results and diagnostics

Both legacy and reviewed apply use the same summary renderer. After a successful or failed apply it reports the status, process exit code and available environment, checked-out commit and plan ID. The default `counts-only` mode also reports Terraform's resource counts when available, without publishing captured output. `human-readable` additionally publishes an HTML-escaped excerpt of the last 180000 bytes of captured apply output in a collapsible section; long output is marked as truncated. Raw output is not uploaded as an artifact or stored in Blob. Summary rendering is best effort and never changes the Terraform exit status; if the apply never started or captured output is unavailable, no stale output is shown.

**Human-readable apply output can contain secrets or other sensitive values Terraform and GitHub do not mask.** Enable it only when everyone who can view the workflow run is authorized to see that output, and apply the same access and retention review as for human-readable plans. Runner termination can prevent summary or cleanup steps from running. An apply failure can leave partial changes; inspect the target and state before any retry.

### Secure saved-plan handoff

Blob storage is opt-in. It requires the independently provisioned private storage and the existing authenticated Azure service principal described in the [reviewed apply contract](../terraform-apply-saved/README.md). The plan ID and checksum are visible in the original review summary. The unified apply resolves the checksum from Blob metadata and verifies the bytes against it; it no longer compares against an independently supplied checksum. Someone able to replace both a plan and its metadata could therefore substitute a plan. The binary and its metadata are uploaded with a conditional create; a failed upload fails the action. For Blob mode, `apply: 'true'` is rejected rather than silently changing the existing immediate-apply behavior. Existing `plan-storage: none` consumers retain their original behavior. `apply: 'true'` without storage still immediately applies the local plan as before.

### Failure diagnostics

A failed init, validate, plan or apply produces a GitHub error annotation and job-summary entry with the stage, numeric exit status and stage-specific next steps. On failure, init, validate and plan also automatically publish a collapsible excerpt of Terraform's standard error in the job summary, limited to the last 32000 bytes and HTML-escaped. Standard output is not included in this excerpt. No input is required. The original exit status is preserved, including when summary generation fails. Empty or unavailable stderr, a failure preparing the capture, earlier setup failure or runner termination can leave no excerpt. This also applies to init in the saved-plan apply action. Apply diagnostics retain the separate behavior described above.

**Failure diagnostics can expose secrets and other sensitive data** to anyone who can view the workflow run. Terraform errors and provider messages can include values that Terraform does not identify as sensitive; truncation, HTML escaping and GitHub secret masking do not guarantee redaction. Treat the job summary as sensitive and review its access and retention. No full captured output, binary plan or JSON plan is uploaded as an artifact by this action. Temporary stderr is removed on normal exit; abrupt runner termination can leave local files on persistent runners.

An authorized operator can use the run link, selected revision, timestamp, environment, failing stage and exit status to investigate using the consumer's restricted telemetry and access procedures:

- **Init:** check backend authorization and connectivity, module/provider access and runner network health.
- **Validate:** check configuration and provider/schema compatibility against the same revision and Terraform version in a controlled environment.
- **Plan:** check backend state-lock activity, target authorization and provider/target service health.
- **Apply:** changes may be partial. Inspect the target, state and relevant Azure Activity Logs or other authorized target-side audit records before deciding on recovery; do not automatically retry.

Use only telemetry the operator is authorized to access, such as restricted Azure Activity Logs, identity sign-in records, backend logs and runner-platform health where available. These sources may not capture the cause. An ephemeral hosted runner does not provide a way to retrieve the original captured CLI diagnostics after the job; no raw output is exported by this action. If additional evidence is needed, arrange an owner-authorized, controlled reproduction appropriate to the failing stage and target. A new run is different evidence and can have state or target effects; do not reproduce an apply against a shared environment without explicit authorization. Do not paste raw output, plans, variables or credentials into logs, artifacts or tickets.

### Restricted detailed review

In default mode this action does not publish a detailed plan. The optional human-readable summary shows the saved CI plan to run viewers, but is unsuitable when its contents require tighter access. Authorized maintainers can instead run a **new**, plan-only review in an approved, access-controlled workstation or environment: check out the same configuration revision, select the same backend/workspace and target, use the same Terraform version, variables and plan options, and run `terraform init` and `terraform plan -out=<private-path>` using the consumer's approved least-privilege credentials and state-locking controls. Inspect `terraform show <private-path>` only in that restricted session; do not upload or paste the binary, output or variables into broadly accessible logs, artifacts or tickets. Protect and remove local files per the consumer's policy. A new plan can differ from the CI plan because state, inputs, providers or remote resources may have changed; it is not approval of the exact saved CI plan. `apply: 'true'` immediately applies the same-job plan, so this procedure does not provide an intervening review of that exact plan.

The [saved-plan handoff](../terraform-apply-saved/README.md) selects the plan by ID and verifies its stored checksum, with the metadata trust limitation above. It requires separately provisioned storage and protections. If the human-readable summary cannot be shared or is unavailable, this action does not provide another way for maintainers to inspect the exact binary plan; do not approve based on a different re-plan. Historical `tfplan` artifacts and logs remain subject to their existing retention and must be assessed separately. Persistent/self-hosted runners also need access restrictions and cleanup of plan, tfvars and output files under the consumer's policy.

```yaml
- name: Terraform plan
  uses: aardex/AardexActions/terraform-deploy@main
  with:
    azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
    github-token: ${{ secrets.PRIVATE_MODULES_TOKEN }}
    directory: infra/terraform
    apply: 'false'
    # Only if the consumer accepts the exposure described above:
    # plan-summary-mode: 'human-readable'
```

For apply, a consumer may set `apply: 'true'` **only after** reviewing the target and plan and arranging approval in the consumer workflow/environment. `needs-approval` cannot enforce an approval gate. A reference to `@main` is mutable; use a reviewed ref where possible.

### Local validation

Run the offline test command in [reviewed apply validation](../terraform-apply-saved/README.md#validation-and-outstanding-gates), plus `bash -n terraform-deploy/summarize-plan.sh` and `bash -n terraform-deploy/run-terraform.sh`. The unit tests use a fake Terraform executable and disposable temporary files, with no external service access. The offline command includes a local built-in `terraform_data` plan without a backend, cloud access or apply. A separate existing test also performs a real local apply, and is excluded from that command. The installed Terraform version may differ from the action's pinned version. These tests do not replace a consumer-owned nonproduction workflow smoke test.
