# Terraform Format and Validate

For a given directory, format the code recursively and validate the Terraform files.

## Usage

```yaml
jobs:
  validate:
    name: Validate and Format Terraform module
    runs-on: ubuntu-latest

  steps:
    - name: Checkout
      uses: actions/checkout@v5

    - name: Terraform Format and Validate
      uses: aardex/AardexActions/terraform-format-validate@main
      with:
        directory: './iac'
```