# Create Release Candidate Version Action

This GitHub Action automates the increment, packaging, and publishing of a **release candidate** (RC) version of your NuGet package.  
It easily integrates with your CI/CD pipeline for standard .NET projects, providing an efficient way to prepare pre-release packages.

## 🛠️ Inputs

| Input           | Description                             | Required | Default |
|-----------------|-----------------------------------------|----------|---------|
| `project`       | Path to the `.csproj` to publish        | Yes      | –       |
| `dotnet-version`| .NET SDK version to use                 | No       | –       |
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
            uses: aardex/create-release-candidate-version@v1 
            with: 
                project: 'src/MyProject' 
                dotnet-version: '8.0.x'
                github-token: ${{ secrets.PAT_TOKEN }}
```

## 🚀 Features

- **Release Candidate Versioning:** Automatically increments your package to the next release candidate (e.g., `1.0.0-rc.*`).
- **Project Validation:** Ensures your `.csproj` includes the correct `RepositoryUrl` and `RepositoryType` fields.
- **Customizable SDK:** Select the .NET SDK version and project location easily.
- **Secure Publishing:** Publishes securely to GitHub Packages using your provided token.
- **End-to-End Automation:** Handles building, testing, packaging, and publishing for seamless pre-release workflows.