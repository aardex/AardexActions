# Create Tag and Release Action

This GitHub Action automatically creates a new Git tag and GitHub release for your project.  
It can be used to automate your release process and optionally attach additional files to your release.

## 🔑 Required Inputs

| Input         | Description                            |
|---------------|----------------------------------------|
| `version`     | Version number to use for tag/release  |
| `github-token`| GitHub token for authentication        |

## 📝 Optional Inputs

| Input       | Description                             | Default   |
|-------------|-----------------------------------------|-----------|
| `prerelease`| Whether this is a prerelease            | `false`   |
| `draft`     | Whether this is a draft release         | `false`   |
| `files`     | Files to include in the release         | `''`      |

## 🚀 Usage Example
```yaml 
jobs: 
    tag-and-release: 
        runs-on: ubuntu-latest 
        steps:
          - name: Create Tag and Release 
            uses: aardex/create-tag-and-release@v1 
            with: 
                version: '1.2.3' 
                github-token: ${{ secrets.GITHUB_TOKEN }} 
                prerelease: 'false' 
                draft: 'false' 
                files: 'dist/my-artifact.zip'
```

## ✨ Features

- Checks out your repository
- Creates a Git tag (e.g., `v1.2.3`)
- Publishes a GitHub release with customizable name, body, and release options
- Optionally attaches files to your release