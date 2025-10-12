# Terraform Deploy to Azure

This GitHub Action initializes, validates, plans, and optionally applies Terraform configurations against Azure using a service principal. It also supports injecting tfvars content securely and accessing private Terraform modules via a GitHub token.

## 🔑 Required Inputs

| Input               | Description                                              |
|---------------------|----------------------------------------------------------|
| `azure-credentials` | Azure service principal JSON used by Terraform AzureRM  |
| `github-token`      | Token to access private GitHub modules (read-only)       |

## 📝 Optional Inputs

| Input             | Description                                                                                   | Default      |
|-------------------|-----------------------------------------------------------------------------------------------|--------------|
| `directory`       | Path to the Terraform working directory                                                       | `terraform`  |
| `apply`           | Whether to run `terraform apply` on the generated plan (`'true'` or `'false'`)                | `'false'`    |
| `tfvars-content`  | Literal content for `terraform.tfvars` (single string, e.g., from secrets or workflow input)  | `''`         |

## 📦 What it does

- Exports ARM_ environment variables from `azure-credentials` (clientId, clientSecret, subscriptionId, tenantId).
- Installs Terraform 1.13.3.
- Configures Git to use `github-token` for private module sources.
- Optionally writes `tfvars-content` to `terraform.tfvars` in the working directory.
- Runs `terraform init -upgrade`, `terraform validate`, and `terraform plan`.
- Uploads the generated `tfplan` as a workflow artifact.
- Optionally runs `terraform apply` on `tfplan` when `apply: 'true'`.

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
### Plan only (no apply):
```yaml
  - name: Terraform plan (no apply)
    uses: your-org/terraform-deploy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
```