# Deploy Azure Dotnet Function Action

This GitHub Action automates the build and deployment of a .NET Azure Function to your specified Azure environment, supporting both standard and flex consumption plans.

## 🔑 Required Inputs

| Input             | Description                              |
|-------------------|------------------------------------------|
| `environment`     | Target environment for deployment        |
| `azure-environment` | Azure environment to use               |
| `project`         | Project path to deploy                   |
| `func-name`       | Name of the Azure Function               |
| `github-token`    | GitHub token for authentication          |
| `azure-profile`   | Azure publish profile                    |

## 📝 Optional Inputs

| Input             | Description                                              | Default   |
|-------------------|----------------------------------------------------------|-----------|
| `config-file-path`| Path to configuration file                               | `''`      |
| `flex-consumption`| Whether to deploy as a flex consumption plan             | `false`   |
| `dotnet-version`  | .NET SDK version to use                                  | `8.0.x`   |
| `codecov-token`   | Codecov token (for coverage reports)                     | -         |

## 🚀 Usage Example
```yaml 
jobs: 
    deploy: 
        runs-on: ubuntu-latest 
        steps: 
          - name: Deploy .NET Azure Function 
            uses: aardex/deploy-dotnet-function@v1 
            with: 
              environment: 'production' 
              azure-environment: 'prod' 
              project: 'src/MyFunctionApp' 
              func-name: 'my-awesome-func' 
              github-token: {{ secrets.PAT_TOKEN }} 
              azure-profile: {{ secrets.AZURE_PUBLISH_PROFILE }} 
              dotnet-version: '8.0.x' 
              config-file-path: 'src/MyFunctionApp/appsettings.json'
              codecov-token: ${{ secrets.CODECOV_TOKEN }}
```
## ✨ Features

- Checks out your code and a shared actions repository
- Optionally updates configuration via Python script
- Builds and packages the .NET Azure Function using the specified .NET version
- Optionally uploads code coverage reports using Codecov
- Deploys to Azure Functions using your chosen plan (standard or flex consumption)

---

Deployment is performed through the [Azure Functions Action](https://github.com/marketplace/actions/azure-functions-action).  
See the [official documentation](https://learn.microsoft.com/en-us/azure/azure-functions/) and the [Azure Functions Action Marketplace page](https://github.com/marketplace/actions/azure-functions-action) for further details.
