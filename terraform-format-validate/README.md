# Terraform Format and Validate

For a given directory, format the code recursively and validate the Terraform files.

## Inputs

- `azure-credentials` (required): Azure credentials in JSON format.
- `directory` (optional, default: `.`): Directory to format and validate.
- `github-token` (required): GitHub token for authentication.
- `fix` (optional, default: `true`): If `true`, runs `terraform fmt -recursive`. If `false`, runs `terraform fmt -check -recursive`.
- `auto-commit` (optional, default: `auto`):
  - `true`: always commit/push formatting changes (if any)
  - `false`: never commit/push
  - `auto`: commit/push only when `fix=true`
- `auto-commit-message` (optional): Commit message used when `auto-commit` is enabled.

## Usage

```yaml
jobs:
  validate:
    name: Validate and Format Terraform module
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Terraform Format and Validate
        uses: aardex/AardexActions/terraform-format-validate@main
        with:
          azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          directory: "./iac"
          fix: "true"
          auto-commit: "auto"
          auto-commit-message: "chore(terraform): auto-format files [skip ci]"
```

## Strict mode (no auto-fix)

```yaml
with:
  azure-credentials: ${{ secrets.AZURE_CREDENTIALS }}
  github-token: ${{ secrets.GITHUB_TOKEN }}
  directory: "./iac"
  fix: "false"
  auto-commit: "false"
```
