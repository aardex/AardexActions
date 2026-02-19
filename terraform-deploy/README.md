# Terraform Deploy to Azure

This GitHub Action initializes, validates, plans, and optionally applies Terraform configurations against Azure using a service principal. It also supports injecting tfvars content securely and accessing private Terraform modules via a GitHub token.

## 🔑 Required Inputs

| Input               | Description                                            |
|---------------------|--------------------------------------------------------|
| `azure-credentials` | Azure service principal JSON used by Terraform AzureRM |
| `github-token`      | Token to access private GitHub modules (read-only)     |

## 📝 Optional Inputs

| Input                | Description                                                                                   | Default      |
|----------------------|-----------------------------------------------------------------------------------------------|--------------|
| `azure-subscription` | Azure subscription to deploy to (defaults to first subscription in credentials)               | `''`         |
| `directory`          | Path to the Terraform working directory                                                       | `terraform`  |
| `apply`              | Whether to run `terraform apply` on the generated plan (`'true'` or `'false'`)                | `'false'`    |
| `needs-approval`     | When `'true'`, pauses for manual approval before applying; when `'false'`, no approval gate   | `'true'`     |
| `tfvars-content`     | Literal content for `terraform.tfvars` (single string, e.g., from secrets or workflow input)  | `''`         |

## 📦 What it does

- Exports ARM_ environment variables from `azure-credentials` (clientId, clientSecret, subscriptionId, tenantId).
- If `azure-subscription` is provided, it overrides the `subscriptionId` from `azure-credentials`.
- Installs Terraform 1.13.3.
- Configures Git to use `github-token` for private module sources.
- Optionally writes `tfvars-content` to `terraform.tfvars` in the working directory.
- Runs `terraform init -upgrade`, `terraform validate`, and `terraform plan`.
- Uploads the generated `tfplan` as a workflow artifact.
- Apply behavior:
  - If `needs-approval: 'true'` (default) and `apply: 'true'`, the job will require manual approval before running `terraform apply`.
  - If `needs-approval: 'false'` and `apply: 'true'`, `terraform apply` will run immediately without approval.
  - If `apply: 'false'`, no apply is performed (plan only).

### azure-credentials
```json
{
    "clientSecret": "<managed identity secret>",
    "subscriptionId": "<managed identity subscription id>",
    "tenantId": "<managed identity tenant id>",
    "clientId": "<managed identity client id>"
}
```

## 🚀 Usage Examples

### Plan only (no apply)
```yaml
  - name: Terraform plan (no apply)
    uses: your-org/terraform-deploy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      apply: 'false'  # default
```

### Apply with manual approval (recommended)
```yaml
  - name: Terraform apply (with approval)
    uses: your-org/terraform-deploy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      apply: 'true'
      needs-approval: 'true'  # default
```

### Apply immediately without approval (use with caution)
```yaml
  - name: Terraform apply (no approval)
    uses: your-org/terraform-deploy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      apply: 'true'
      needs-approval: 'false'
```