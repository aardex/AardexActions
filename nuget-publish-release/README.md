# Create Release Version Action

This GitHub Action allows you to automatically compute, pack, and publish a **release** (stable) version of your NuGet package.
It is tailored to fit smoothly into your CI/CD pipeline and supports all standard .NET projects.

## 🛠️ Inputs

| Input           | Description                             | Required | Default |
|-----------------|-----------------------------------------|----------|---------|
| `project`       | Directory containing a same-named `.csproj` | Yes | – |
| `dotnet-version`| .NET SDK version to use | No | `8.x` |
| `github-token`  | GitHub token for authentication         | Yes      | –       |

## 🎁 Outputs

| Output    | Description                     |
|-----------|---------------------------------|
| `version` | The generated release version   |

## 📝 Example Usage

```yaml 
jobs: 
    release: 
    runs-on: ubuntu-latest 
    steps: 
        - name: Create Release Version 
          uses: aardex/AardexActions/nuget-publish-release@main
          with: 
              project: 'src/MyProject' 
              dotnet-version: '10.0.x' 
              github-token: ${{ secrets.PAT_TOKEN }}
```

## 🚀 Features

- **Automatic Versioning**: Determines and increments to the next release version based on your project's current versioning strategy.
- **Safety Checks**: Ensures the `RepositoryUrl` and `RepositoryType` are correctly set in your `.csproj` file.
- **Flexible .NET SDK**: Allows full customization of the .NET SDK version and project path.
- **Publishing**: Pushes the package to GitHub Packages using the supplied token; see [configuration](../docs/configuration.md). This action does not commit or push source changes.
- **Full Lifecycle**: Builds, tests, packs, and publishes your NuGet package for reliable, reproducible releases.

---

> Check the generated version and package in the consumer workflow before publishing; this action does not define release approval.