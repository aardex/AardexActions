# Create Alpha Version Action

This GitHub Action helps you automatically generate, pack and publish an **alpha** version of a NuGet package.
It's designed to integrate smoothly with your CI/CD pipeline and supports standard .NET projects.

## 🛠️ Inputs

| Input           | Description                               | Required | Default      |
|-----------------|-------------------------------------------|----------|--------------|
| `project`       | Directory containing a same-named `.csproj` to publish | Yes | – |
| `dotnet-version`| .NET SDK version to use | No | `8.x` |
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
            uses: aardex/AardexActions/nuget-publish-alpha@main
            with: 
              project: 'src/MyProject' 
              dotnet-version: '10.0.x' 
              github-token: ${{ secrets.PAT_TOKEN }}
```

## 🚀 Features

- **Versioning:** Increments to the next pre-release (alpha) version according to your solution’s current version
- **Safety:** Automatically adds or updates your project’s `RepositoryUrl` field if missing
- **Flexible:** Supports customizable .NET SDK versions and repository paths
- **Publishing:** Uses the supplied GitHub token for GitHub Packages; the action packs and pushes but does not run a separate test or commit/push step. Provide credentials through consumer secrets. See [configuration](../docs/configuration.md).

