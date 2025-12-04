# Terraform Destroy for Azure

This composite GitHub Action creates a Terraform destroy plan for your Azure infrastructure and, optionally (after manual approval), applies it.

## 🔑 Required Inputs

| Input               | Description                                              |
|---------------------|----------------------------------------------------------|
| `azure-credentials` | Azure service principal JSON used by Terraform AzureRM  |
| `github-token`      | Token to access private GitHub modules (read-only)       |

## 📝 Optional Inputs

| Input              | Description                                                                                   | Default     |
|--------------------|-----------------------------------------------------------------------------------------------|-------------|
| `directory`        | Path to the Terraform working directory                                                       | `terraform` |
| `needs-approval`   | Whether to require manual approval before applying the destroy plan (recommended)             | `'true'`    |
| `tfvars-content`   | Literal content for `terraform.tfvars` (single string, e.g., from secrets or workflow input)  | `''`        |

## 📦 What it does

- Exports `ARM_` environment variables from `azure-credentials` (clientId, clientSecret, subscriptionId, tenantId).
- Installs Terraform 1.13.3.
- Configures Git to use `github-token` for private module sources.
- Optionally writes `tfvars-content` to `terraform.tfvars` in the working directory.
- Runs `terraform init -upgrade`, `terraform validate`.
- Creates a destroy plan using `terraform plan -destroy` and uploads artifacts: `tfdestroy.tfplan`, `tfdestroy.json`, and `result.txt`.
- If `needs-approval: 'true'`, pauses for manual approval and then applies the destroy plan with `terraform apply tfdestroy.tfplan`.

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

### Plan destroy with approval before applying
```
  - name: Terraform destroy (with approval)
    uses: your-org/terraform-destroy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      needs-approval: 'true'
```

### Plan destroy only (no apply)
```
  - name: Terraform destroy plan only
    uses: your-org/terraform-destroy@v1
    with:
      azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
      github-token: ${{ secrets.PAT_TOKEN }}
      directory: 'infra/terraform'
      needs-approval: 'false'
```

> Note: When `needs-approval` is set to `'false'`, the action will not apply the plan; it only produces and uploads the destroy artifacts for review.
