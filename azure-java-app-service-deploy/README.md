# Deploy Java App Service Action

This GitHub Action builds and deploys a Java application to Azure App Service, making it easy to automate your cloud application delivery using GitHub Actions.

## 🔑 Required Inputs

| Input               | Description                              |
|---------------------|------------------------------------------|
| `environment`       | Target environment for deployment        |
| `azure-environment` | Azure environment to use                 |
| `project`           | Project path to deploy                   |
| `app-name`          | Name of the Azure Web App                |
| `github-token`      | GitHub token for authentication          |
| `azure-profile`     | Azure publish profile                    |
 
## 📝 Optional Inputs

| Input               | Description                                              | Default   |
|---------------------|----------------------------------------------------------|-----------|
| `java-version`      | Java version                               | `11`      |
| `gradle-version`    | Gradle version to use                              	     | `8.10`    |
| `pre-build`         | A pre build step command                              	 | -         |
| `codecov-token`     | Codecov token (for coverage reports)                     | -         |

## 🚀 Usage Example
```yaml
jobs:
    deploy: 
        runs-on: ubuntu-latest 
        steps: 
          - name: Deploy Java App Service 
            uses: aardex/AardexActions/azure-java-app-service-deploy@main
            with: 
              environment: 'production'
              azure-environment: 'prod' 
              project: 'src/MyApp' 
              app-name: 'my-awesome-app' 
              github-token: ${{ secrets.PAT_TOKEN }}
              azure-profile: ${{ secrets.AZURE_PUBLISH_PROFILE }}
              java-version: '11' 
              gradle-version: '8.10' 
              pre-build: |
                echo "My pre build step"
              codecov-token: ${{ secrets.CODECOV_TOKEN }}
```

## ✨ Features

- Checks out the consumer repository; see [configuration](../docs/configuration.md) for credentials
- Optionally perform pre build task 
- Builds and packages java application in a WAR file
- Optionally integrates code coverage reporting with Codecov
- Deploys your application to Azure App Service using the [Azure Web Apps Deploy Action](https://github.com/marketplace/actions/azure-webapps-deploy)

Deployment to Azure Web App leverages the [Azure Web Apps Deploy GitHub Action](https://github.com/marketplace/actions/azure-webapps-deploy).
For more information, see the [Azure App Service documentation](https://learn.microsoft.com/en-us/azure/app-service/).