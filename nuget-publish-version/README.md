# Create Release Version Action

This GitHub Action allows you to automatically increment, publish, and push a **release** (stable) version of your NuGet package.  
It is tailored to fit smoothly into your CI/CD pipeline and supports all standard .NET projects.

## 🛠️ Inputs

| Input            | Description                                                         | Required | Default |
|------------------|---------------------------------------------------------------------|----------|---------|
| `project`        | Path to the `.csproj` to publish                                    | Yes      | –       |
| `dotnet-version` | .NET SDK version to use                                             | No       | 8.x     |
| `type`           | Type of version to publish <alpha/release-candidate/release/manual> | Yes      | -       |
| `version`        | Version to publish. Used only when type is manual                   | No       | –       |
| `github-token`   | GitHub token for authentication                                     | Yes      | –       |

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
          uses: aardex/AardexActions/nuget-publish-version@main
          with: 
              project: 'src/MyProject' 
              dotnet-version: '8.0.x' 
              type: 'manual'
              version: '1.0.0-amazing-feature.1'
              github-token: ${{ secrets.PAT_TOKEN }}
```
