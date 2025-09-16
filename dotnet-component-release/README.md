# Create Release Version Action

This GitHub Action allows you to automatically increment, publish, and push a **release** (stable) version of your NuGet package.  
It is tailored to fit smoothly into your CI/CD pipeline and supports all standard .NET projects.

## 🛠️ Inputs

| Input          | Description                                       | Required | Default |
| -------------- | ------------------------------------------------- | -------- | ------- |
| `version`      | Version to publish. Used only when type is manual | No       | –       |
| `github-token` | GitHub token for authentication                   | Yes      | –       |

## 📝 Example Usage

```yaml 
jobs: 
    release: 
    runs-on: ubuntu-latest 
    steps: 
        - name: Create Release Version 
          uses: aardex/AardexActions/dotnet-component-release@main
          with: 
              type: 'manual'
              version: '1.0.0-amazing-feature.1'
              github-token: ${{ secrets.PAT_TOKEN }}
```
