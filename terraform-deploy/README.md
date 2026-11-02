# Terraform deploy to Azure

This composite action logs in with an Azure service principal, initializes and validates Terraform, writes a saved plan and optionally applies it. See [deployment and approval boundaries](../docs/deployment.md) and [configuration/data handling](../docs/configuration.md) before running it.

| Input | Required | Default / behavior |
| --- | --- | --- |
| `azure-credentials` | Yes | Service-principal JSON with `clientId`, `clientSecret`, `tenantId`, `subscriptionId` |
| `github-token` | Yes | Token with read access to referenced private GitHub modules |
| `azure-subscription` | No | Overrides `subscriptionId` from credentials |
| `directory` | No | `terraform` |
| `apply` | No | `'false'`; `'true'` applies the saved plan with `-auto-approve` |
| `needs-approval` | No | Declared as `'true'` but **unused**; does not pause or protect apply |
| `tfvars-content` | No | Writes `terraform.tfvars` in `directory` when nonempty |
| `plan-args` | No | Additional whitespace-split flags for `terraform plan` |

Uses Terraform 1.13.3, runs `terraform init -upgrade -input=false`, `terraform validate -no-color`, then saves `tfplan.tfplan`. The binary plan and captured Terraform output (`init-result.txt`, `validate-result.txt`, `result.txt` and `apply-result.txt`) remain on the runner and are not uploaded by this action. `terraform show -json` is streamed directly into a filter; the job summary contains only fixed action categories and aggregate resource counts. Replacements count once, separately from creates and deletes. Addresses, resource types, indices, values, outputs and variables are omitted. Unsupported action combinations, an invalid or missing plan, or a failed plan produce a generic unavailable message instead. The plan's exit status controls the step; apply runs only after a successful plan and preceding steps. The action no longer explicitly echoes plan arguments. Azure login and other consumer steps can still produce logs that require access controls and review. Do not put secrets or variable values in `plan-args`: GitHub Actions may expose step environment values; use the protected `tfvars-content` input instead.

### Restricted detailed review

This action does not provide a retrievable detailed plan. Authorized maintainers can instead run a **new**, plan-only review in an approved, access-controlled workstation or environment: check out the same configuration revision, select the same backend/workspace and target, use the same Terraform version, variables and plan options, and run `terraform init` and `terraform plan -out=<private-path>` using the consumer's approved least-privilege credentials and state-locking controls. Inspect `terraform show <private-path>` only in that restricted session; do not upload or paste the binary, output or variables into broadly accessible logs, artifacts or tickets. Protect and remove local files per the consumer's policy. A new plan can differ from the CI plan because state, inputs, providers or remote resources may have changed; it is not approval of the exact saved CI plan. `apply: 'true'` immediately applies the same-job plan, so this procedure does not provide an intervening review of that exact plan.

If exact-plan review is required, keep apply disabled until the owner designs and approves a restricted, encrypted plan handoff with narrowly scoped identities, retention and an approval flow. None is provisioned here. Historical `tfplan` artifacts and logs remain subject to their existing retention and must be assessed separately. Persistent/self-hosted runners also need access restrictions and cleanup of plan, tfvars and output files under the consumer's policy.

```yaml
- name: Terraform plan
  uses: aardex/AardexActions/terraform-deploy@main
  with:
    azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
    github-token: ${{ secrets.PRIVATE_MODULES_TOKEN }}
    directory: infra/terraform
    apply: 'false'
```

For apply, a consumer may set `apply: 'true'` **only after** reviewing the target and plan and arranging approval in the consumer workflow/environment. `needs-approval` cannot enforce an approval gate. A reference to `@main` is mutable; use a reviewed ref where possible.

### Local validation

Run `python3 -m unittest discover -s terraform-deploy/tests -v` and `bash -n terraform-deploy/summarize-plan.sh`. The unit tests use a fake Terraform executable and disposable temporary files, with no external service access. If Terraform is installed, an additional test initializes and applies a built-in `terraform_data` resource in a disposable local directory using only local state, no backend, modules or external providers; it does not access a cloud service. The installed Terraform version may differ from the action's pinned version. These tests do not replace a consumer-owned nonproduction workflow smoke test.
