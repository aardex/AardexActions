# Release a .NET component version

This action updates the consumer's `Directory.Build.props`, invokes `github-commit-push@main`, then invokes `github-create-tag-release@main` to create a `v<version>` tag and GitHub Release in the consumer repository. It does **not** pack or publish a NuGet package. See [deployment](../docs/deployment.md).

## 🛠️ Inputs

| Input          | Description                                       | Required | Default |
| -------------- | ------------------------------------------------- | -------- | ------- |
| `version`      | Explicit version; otherwise generated from `Directory.Build.props` | No | – |
| `github-token` | GitHub token for authentication                   | Yes      | –       |
| `directory-build-props-path` | Path to `Directory.Build.props` file | No | `Directory.Build.props` |

## 📝 Example Usage

```yaml 
jobs: 
    release:
      runs-on: ubuntu-latest
      steps:
        - name: Create Release Version 
          uses: aardex/AardexActions/dotnet-component-release@main
          with: 
              version: '1.0.0-amazing-feature.1'
              github-token: ${{ secrets.PAT_TOKEN }}
              directory-build-props-path: src/AcquisitionConnectorShl/Directory.Build.props
```
