# Terraform Destroy for Azure

This composite GitHub Action creates a Terraform destroy plan for your Azure infrastructure and, optionally (after manual approval), applies it.

## 🔑 Required Inputs

| Input               | Description                                              |
|---------------------|----------------------------------------------------------|
| `azure-credentials` | Azure service principal JSON used by Terraform AzureRM  |
| `github-token`      | Token to access private GitHub modules (read-only)       |

## 📝 Optional Inputs

| Input                | Description                                                                                   | Default      |
|----------------------|-----------------------------------------------------------------------------------------------|--------------|
| `azure-subscription` | Azure subscription to destroy in (defaults to `subscriptionId` in `azure-credentials`)       | `''`         |
| `directory`          | Path to the Terraform working directory                                                       | `terraform`  |
| `apply`              | Whether to run `terraform apply` on the generated destroy plan (`'true'` or `'false'`)       | `'false'`    |
| `needs-approval`     | Manual approval gate before apply when `apply: 'true'`                                        | `'true'`     |
| `tfvars-content`     | Literal content for `terraform.tfvars` (single string, e.g., from secrets or workflow input) | `''`         |
| `plan-args`          | Additional arguments passed to `terraform plan` (e.g., `-refresh=true -replace=...`)         | `''`         |

## 📦 What it does

- Exports `ARM_` environment variables from `azure-credentials` (clientId, clientSecret, subscriptionId, tenantId).
- If `azure-subscription` is provided, it overrides `subscriptionId` from `azure-credentials`.
- Installs Terraform 1.13.3.
- Configures Git to use `github-token` for private module sources.
- Optionally writes `tfvars-content` to `terraform.tfvars` in the working directory.
- Runs `terraform init -upgrade`, `terraform validate`.
- Creates a destroy plan using `terraform plan -destroy` and uploads artifacts: `tfdestroy.tfplan`, `tfdestroy.json`, and `result.txt`.
- Supports passing additional flags via `plan-args`.
- Apply behavior:
- If `apply: 'false'` (default), no apply is executed (plan only).
- If `apply: 'true'` and `needs-approval: 'true'`, manual approval is required before apply.
- If `apply: 'true'` and `needs-approval: 'false'`, apply runs immediately.

### azure-credentials
```
{
  "clientSecret": "<service principal secret>",
  "subscriptionId": "<azure subscription id>",
  "tenantId": "<azure tenant id>",
  "clientId": "<service principal client id>"
}
```

## 🚀 Usage Examples

### Plan only (no apply)
```
  - name: Terraform destroy plan only
    uses: your-org/terraform-destroy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      apply: 'false'
      plan-args: "-refresh=true"
```

### Apply with manual approval (recommended)
```
  - name: Terraform destroy apply (with approval)
    uses: your-org/terraform-destroy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      apply: 'true'
      needs-approval: 'true'
```

### Apply immediately without approval (use with caution)
```
  - name: Terraform destroy apply (no approval)
    uses: your-org/terraform-destroy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      apply: 'true'
      needs-approval: 'false'
```
