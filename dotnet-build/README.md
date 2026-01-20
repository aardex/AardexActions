# Dotnet Build Action

This GitHub Action builds and tests a .NET project with code coverage reporting.

## 🔑 Required Inputs

| Input | Description |
|-------|-------------|
| `github-token` | GitHub token for authentication |
| `codecov-token` | Codecov token for coverage report upload |

## 📝 Optional Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `build-target` | Build configuration to use | `Debug` |
| `working-directory` | Working directory for dotnet commands | `.` |
| `dotnet-version` | .NET SDK version to use | `10.0.x` |
| `output-path` | Custom output path for build artifacts | - |

## 🚀 Usage Example
```yaml
jobs: 
  build:
    runs-on: ubuntu-latest
    steps:
    - name: Build and Test
      uses: aardex/dotnet-build@v1
      with:
        github-token: ${{ secrets.PAT_TOKEN }}
        codecov-token: ${{ secrets.CODECOV_TOKEN }}
        build-target: Release
        dotnet-version: '10.0.x'
        working-directory: 'src/JulProject'
        output-path: 'bin'
```

## ✨ Features

The action performs the following operations:
- Sets up .NET environment
- Configures GitHub NuGet sources
- Restores dependencies 
- Builds the project
- Runs tests with coverage reporting
- Uploads coverage reports to Codecov