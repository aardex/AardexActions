# Azure Publish Docker

This GitHub Action automates the build and deployment of a .NET Azure Function to your specified Azure environment,
supporting both standard and flex consumption plans.

## 🔑 Required Inputs

| Input               | Description                                              |
|---------------------|----------------------------------------------------------|
| `environment`       | Target environment for deployment                        |
| `azure-environment` | Azure environment to use                                 |
| `image-name`        | Name of the Docker Image                                 |
| `github-token`      | GitHub token for authentication                          |
| `azure-credentials` | Json with Azure Managed Identity information             |
| `acr-login-server`  | Server name of Azure registry (Settings > Access keys)   |
| `acr-username`      | Username of Azure registry (Settings > Access keys)      |
| `acr-passworrd`     | Password name of Azure registry (Settings > Access keys) |

## 📝 Optional Inputs

| Input              | Description                                                                                                   | Default         |
|--------------------|---------------------------------------------------------------------------------------------------------------|-----------------|
| `config-file-path` | Path to configuration file                                                                                    | `''`            |
| `docker-directory` | Docker directory path                                                                                         | `'docker'`      |
| `platforms`        | Platform available for the image (separated by coma)                                                          | `'linux/amd64'` |
| `skip-check`       | Skip vulnerability check                                                                                      | `'false'`       |
| `version`          | The version the image to publish and deploy. If not specified, it will used the Directory.Build.props version | `''`            |

## 📤 Outputs

| Output    | Description           |
|-----------|-----------------------|
| `version` | The published version |

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
        uses: aardex/AardexActions/azure-publish-docker@main
        with:
          environment: ${{ inputs.environment }}
          azure-environment: ${{ vars.AZ_ENV }}
          image-name: 'mobile-backend'
          config-file-path: 'src/MemsMobile.Backend.Functions/appsettings.json'
          github-token: ${{ secrets.PAT_TOKEN }}
          azure-credentials: ${{ secrets.AZ_CREDENTIALS }}
          acr-login-server: acradxsandbox.azurecr.io
          acr-username: ${{ secrets.ACR_USERNAME }}
          acr-password: ${{ secrets.ACR_PASSWORD }}
          dockerfile-path: 'docker'
          docker-directory: 'docker'
          platforms: 'linux/amd64,linux/arm64'
```