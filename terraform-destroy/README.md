# Terraform destroy for Azure

This composite action generates a saved **destroy plan** and optionally applies it. There is **no built-in manual approval**. See [deployment](../docs/deployment.md) and [configuration](../docs/configuration.md) for approval and plan-data boundaries.

| Input | Required | Default / behavior |
| --- | --- | --- |
| `azure-credentials` | Yes | Azure service-principal JSON (`clientId`, `clientSecret`, `tenantId`, `subscriptionId`) |
| `github-token` | Yes | Token for private GitHub Terraform modules |
| `azure-subscription` | No | Overrides subscription from credentials |
| `directory` | No | `terraform` |
| `apply` | No | `'false'`; `'true'` runs `terraform apply -input=false -auto-approve tfdestroy.tfplan` |
| `tfvars-content` | No | Writes `terraform.tfvars` in `directory` when nonempty |
| `plan-args` | No | Extra whitespace-split Terraform plan arguments |

The action exports `ARM_*` credentials, installs Terraform 1.13.3, configures Git for private modules, then runs `terraform init -upgrade -input=false`, `terraform validate -no-color` and `terraform plan -destroy -out=tfdestroy.tfplan`. It attempts `terraform show -json` and uploads `tfdestroy.tfplan`, `tfdestroy.json` and `result.txt` as `tfdestroy` with 15-day retention even on failure where possible. These artifacts and the generated tfvars file can contain sensitive data; the Git URL configuration includes the token on the runner.

```yaml
- name: Review destroy plan only
  uses: aardex/AardexActions/terraform-destroy@main
  with:
    azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
    github-token: ${{ secrets.PRIVATE_MODULES_TOKEN }}
    directory: infra/terraform
    apply: 'false'
```

Do not set `apply: 'true'` without consumer-owned approval and explicit target/plan verification. `@main` is mutable; use a reviewed ref where possible.
