# Create Release Candidate Version Action

This GitHub Action automates the increment, packaging, and publishing of a **release candidate** (RC) version of your NuGet package.  
It easily integrates with your CI/CD pipeline for standard .NET projects, providing an efficient way to prepare pre-release packages.

## 🛠️ Inputs

| Input           | Description                             | Required | Default |
|-----------------|-----------------------------------------|----------|---------|
| `project`       | Directory containing a same-named `.csproj` | Yes | – |
| `dotnet-version`| .NET SDK version to use | No | `8.x` |
| `github-token`  | GitHub token for authentication         | Yes      | –       |

## 🎁 Outputs

| Output    | Description                                |
|-----------|--------------------------------------------|
| `version` | The generated release candidate version    |

## 📝 Example Usage

```yaml 
jobs: 
    release-candidate: 
        runs-on: ubuntu-latest 
        steps: 
          - name: Create Release Candidate Version 
            uses: aardex/AardexActions/nuget-publish-release-candidate@main
            with: 
                project: 'src/MyProject' 
                dotnet-version: '10.0.x'
                github-token: ${{ secrets.PAT_TOKEN }}
```

## 🚀 Features

- **Release Candidate Versioning:** Automatically increments your package to the next release candidate (e.g., `1.0.0-rc.*`).
- **Project Validation:** Ensures your `.csproj` includes the correct `RepositoryUrl` and `RepositoryType` fields.
- **Customizable SDK:** Select the .NET SDK version and project location easily.
- **Publishing:** Pushes to GitHub Packages using the supplied token; see [configuration](../docs/configuration.md). It does not commit or push source changes.
- **End-to-End Automation:** Handles building, testing, packaging, and publishing for seamless pre-release workflows.