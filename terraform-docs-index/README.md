# Terraform Documentation Index

Searches all README files recursively from the given directory and add a table of contents in the root README.

## Usage

```yaml
jobs:
  documentation:
    name: Module Documentation
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Terraform Format and Validate
        uses: aardex/AardexActions/terraform-docs-index@main
        with:
          directory: '.'
```