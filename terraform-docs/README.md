# Terraform Docs Generation

Generate the documentation in `README.md` for the given module (directory).

> **Warning** the documentation files are not push in the repository.

## Usage

```yaml
jobs:
  documentation:
    name: Module Documentation
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Terraform Format and Validate
        uses: aardex/AardexActions/terraform-docs@main
        with:
          directory: './iac'
```