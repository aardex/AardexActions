# Create Release Version Action

This GitHub Action allows you to automatically increment, publish, and push a **release** (stable) version of your NuGet package.  
It is tailored to fit smoothly into your CI/CD pipeline and supports all standard .NET projects.

## 🛠️ Inputs

| Input           | Description                             | Required | Default |
|-----------------|-----------------------------------------|----------|---------|
| `project`       | Path to the `.csproj` to publish        | Yes      | –       |
| `dotnet-version`| .NET SDK version to use                 | No       | –       |
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
          uses: aardex/create-release-version@v1 
          with: 
              project: 'src/MyProject' 
              dotnet-version: '8.0.x' 
              github-token: ${{ secrets.PAT_TOKEN }}
```

## 🚀 Features

- **Automatic Versioning**: Determines and increments to the next release version based on your project's current versioning strategy.
- **Safety Checks**: Ensures the `RepositoryUrl` and `RepositoryType` are correctly set in your `.csproj` file.
- **Flexible .NET SDK**: Allows full customization of the .NET SDK version and project path.
- **Secure Publishing**: Publishes the package to GitHub Packages using your provided GitHub token.
- **Full Lifecycle**: Builds, tests, packs, and publishes your NuGet package for reliable, reproducible releases.

---

> **Tip:** Use this Action at the end of your release workflow to guarantee version correctness and secure, automated publishing to your NuGet feed.