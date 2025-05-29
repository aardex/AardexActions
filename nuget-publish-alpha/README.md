# Create Alpha Version Action

This GitHub Action helps you automatically generate, publish, and push an **alpha** version of a NuGet package.  
It's designed to integrate smoothly with your CI/CD pipeline and supports standard .NET projects.

## 🛠️ Inputs

| Input           | Description                               | Required | Default      |
|-----------------|-------------------------------------------|----------|--------------|
| `project`       | Path to the `.csproj` to publish          | Yes      | –            |
| `dotnet-version`| .NET SDK version to use                   | No       | –            |
| `github-token`  | GitHub token for authentication           | Yes      | –            |

## 🎁 Output

| Output    | Description                |
|-----------|----------------------------|
| `version` | The generated alpha version|

## 📝 Example Usage
```yaml
jobs: 
    alpha-release: 
        runs-on: ubuntu-latest 
        steps: 
          - name: Create Alpha Version 
            uses: aardex/create-alpha-version@v1 
            with: 
              project: 'src/MyProject' 
              dotnet-version: '8.0.x' 
              github-token: ${{ secrets.PAT_TOKEN }}
```

## 🚀 Features

- **Versioning:** Increments to the next pre-release (alpha) version according to your solution’s current version
- **Safety:** Automatically adds or updates your project’s `RepositoryUrl` field if missing
- **Flexible:** Supports customizable .NET SDK versions and repository paths
- **Secure:** Uses your GitHub token for authentication and package publishing

