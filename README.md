# Aardex Actions for Github

This project includes github actions that can be used through our CI/CD chains, in particular to validate Terraform modules or generate documentation.

## Available Actions

> ⚠️ **Important Note**  
> Several actions in this repository are interdependent and reference each other using the `main` branch (e.g., `uses: aardex/AardexActions/dotnet-build@main`). When making changes or conducting tests:
> - Be aware that modifying an action might affect other actions that depend on it
> - Consider using a different branch for testing to avoid disrupting existing workflows
> - Update the branch references in dependent actions if you need to test changes
> - Always thoroughly test changes across all dependent actions before merging to `main`

### Azure
- Deploy [Azure Dotnet Function](./azure-dotnet-function-deploy/README.md): Deploy a .NET function to Azure Functions service
- Deploy [Azure Dotnet App Service](./azure-dotnet-app-service-deploy/README.md): Deploy a .NET application to Azure App Service

### Dotnet Nuget
> ⚠️ **Important Note**  
> If you want to use the Nuget workflows, in the project root you must have a **`Directory.Build.props`** file with the following content:
> ```xml
> <Project>
>     <PropertyGroup>
>         <Version>0.6.17-alpha.8.0</Version>
>     </PropertyGroup>
> </Project>
> ```
> **And EVERY .csproj doesn't have a version tag**
- Create [Alpha Version](./nuget-publish-alpha/README.md): Automatically generate and publish an alpha NuGet package version for early testing
- Create [Release Candidate Version](./nuget-publish-release-candidate/README.md): Increment and publish a release candidate NuGet version for pre-release validation
- Create [Release Version](./nuget-publish-release/README.md): Increment and publish a stable NuGet package version for production use

### GitHub
- [Commit New Version](./commit-version-changes/README.md): Automatically commit and push version changes to repository

### Terraform
- Generate [Terraform Docs](./terraform-docs/README.md): Generate comprehensive documentation for a given Terraform module
- Create [Terraform Docs Index](./terraform-docs-index/README.md): Generate an index of documentation for all Terraform modules
- [Terraform Format and Validate](./terraform-format-validate/README.md): Format and validate Terraform code in a specified folder
- Search for [Terraform Modules Directories](./terraform-format-validate/README.md): Locate and list all Terraform module directories in a repository