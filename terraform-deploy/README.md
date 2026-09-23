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

Uses Terraform 1.13.3, runs `terraform init -upgrade -input=false`, `terraform validate -no-color`, then saves `tfplan.tfplan`. It runs `terraform show -json` and uploads `tfplan.tfplan`, `tfplan.json` and `result.txt` as the `tfplan` artifact (15-day retention), including on failure where possible. Plans and generated files can contain sensitive data. The Git credential helper masks the supplied token and rewrites GitHub SSH-style module URLs to HTTPS for module fetches; this does not make plan artifacts safe to distribute.

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
