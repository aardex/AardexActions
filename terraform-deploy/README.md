# Terraform Deploy

This GitHub action will deploy Azure resources using Terraform.

## 🛠️ Inputs

| Input               | Description                                  | Required | Default     |
|---------------------|----------------------------------------------|----------|-------------|
| `azure-credentials` | Json with Azure Managed Identity information | true     | N/A         |
| `directory`         | Terraform directory location from root       | false    | `terraform` |
| `apply`             | Allow to apply the terraform plan            | false    | `false`     |

## 📝 Exemple of variables
### azure-credentials
```json
{
    "clientSecret": "<managed identity secret>",
    "subscriptionId": "<managed identity subscription id>",
    "tenantId": "<managed identity tenant id>",
    "clientId": "<managed identity client id>"
}
```

## 📝 Example Usage

```yaml 
jobs:
  terraform:
    name: Terraform Plan & Apply
    runs-on:
      group: Terraform

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Deploy with Terraform
        uses: aardex/AardexActions/terraform-deploy@main
        with:
          azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
          apply: true
```
