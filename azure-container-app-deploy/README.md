# Deploy Docker to Container App

This GitHub Action automates the build and deployment of a .NET Azure Function to your specified Azure environment,
supporting both standard and flex consumption plans.

## 🔑 Required Inputs

| Input               | Description                                              |
|---------------------|----------------------------------------------------------|
| `environment`       | Target environment for deployment                        |
| `azure-environment` | Azure environment to use                                 |
| `ca-name`           | Name of the Container App                                |
| `image-name`        | Name of the Docker Image                                 |
| `github-token`      | GitHub token for authentication                          |
| `azure-credentials` | Json with Azure Managed Identity information             |
| `subscription-id`  | Azure Subscription ID                                    |
| `acr-login-server`  | Server name of Azure registry (Settings > Access keys)   |
| `ca-resource-group` | Registry Resource Group                                  |

## 📝 Optional Inputs

| Input              | Description                                                                                                   | Default         |
|--------------------|---------------------------------------------------------------------------------------------------------------|-----------------|
| `config-file-path` | Path to configuration file                                                                                    | `''`            |
| `docker-directory` | Docker directory path                                                                                         | `'docker'`      |
| `platforms`        | Platform available for the image (separated by coma)                                                          | `'linux/amd64'` |
| `skip-check`       | Skip vulnerability check                                                                                      | `'false'`       |
| `version`          | The version the image to publish and deploy. If not specified, it will used the Directory.Build.props version | `''`            |


## Exemple of variables
### azure-credentials
```json
{
    "clientSecret": "<managed identity secret>",
    "subscriptionId": "<managed identity subscription id>",
    "tenantId": "<managed identity tenant id>",
    "clientId": "<managed identity client id>"
}
```

## 🚀 Usage Example

```yaml 
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy Docker to Azure Container Apps to ${{ inputs.environment }}
        uses: aardex/AardexActions/azure-container-app-deploy@main
        with:
          environment: ${{ inputs.environment }}
          azure-environment: ${{ vars.AZ_ENV }}
          ca-name: 'ca-mobile-backend'
          image-name: 'mobile-backend'
          config-file-path: 'src/MemsMobile.Backend.Functions/appsettings.json'
          github-token: ${{ secrets.PAT_TOKEN }}
          azure-credentials: ${{ secrets.AZ_CREDENTIALS }}
          subscription-id: ${{ vars.AZ_SUBSCRIPTION_ID }}
          acr-login-server: acradxsandbox.azurecr.io
          ca-resource-group: "rg-mobile-backend"
          dockerfile-path: 'docker'
          docker-directory: 'docker'
          platforms: 'linux/amd64,linux/arm64'
```