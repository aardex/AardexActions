# Commit Version Changes Action

This GitHub Action automates updating a NuGet package version and committing the changes to your repository.

## 📌 Description

The action performs the following tasks:

- Checks out the target repository.
- Checks out a custom action repository (`aardex/AardexActions`) containing a Python script.
- Updates the NuGet package version using the provided script.
- Commits and pushes the changes using the provided version number as the commit message.

## 🔑 Required Inputs

| Input Name     | Description |
|----------------|-------------|
| `version`      | The new version number to apply and include in the commit message (e.g., `1.2.3`). |
| `github-token` | GitHub token with permissions to push to the repository. Usually `${{ secrets.GITHUB_TOKEN }}` or a personal access token. |

## 🚀 Usage Example

```yaml
jobs:
  versioning:
    runs-on: ubuntu-latest
    steps:
      - name: Commit Version Update
        uses: your-org/commit-version-action@v1
        with:
          version: '1.2.3'
          github-token: ${{ secrets.PAT_TOKEN }}
```