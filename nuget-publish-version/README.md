# Publish a versioned NuGet package

This action computes an alpha, release-candidate or release version (or accepts a manual version), updates the consumer's `Directory.Build.props`, builds, tests, packs and pushes to GitHub Packages. It does **not** commit or push the source changes. See [deployment](../docs/deployment.md) and [configuration](../docs/configuration.md).

## 🛠️ Inputs

| Input            | Description                                                         | Required | Default |
|------------------|---------------------------------------------------------------------|----------|---------|
| `project`        | Directory containing a same-named `.csproj`                                    | Yes      | –       |
| `dotnet-version` | .NET SDK version to use                                             | No       | 8.x     |
| `type`           | Type of version to publish <alpha/release-candidate/release/manual> | Yes      | -       |
| `version`        | Version to publish. Used only when type is manual                   | No       | –       |
| `github-token`   | GitHub token for authentication                                     | Yes      | –       |

## 🎁 Outputs

| Output    | Description                     |
|-----------|---------------------------------|
| `version` | The determined package version   |

## 📝 Example Usage

```yaml 
jobs: 
    release:
      runs-on: ubuntu-latest
      steps:
        - name: Publish version
          uses: aardex/AardexActions/nuget-publish-version@main
          with: 
              project: 'src/MyProject' 
              dotnet-version: '10.0.x' 
              type: 'manual'
              version: '1.0.0-amazing-feature.1'
              github-token: ${{ secrets.PAT_TOKEN }}
```
