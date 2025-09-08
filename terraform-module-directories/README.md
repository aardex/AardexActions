# Terraform Module Directories

Return the list of directories with Terraform modules for the project.
It's usefull to apply Terraform validation or generating Terraform Docs.

## Usage

```yaml
jobs:
  get-sources:
    name: Get Workflow Sources
    runs-on: ubuntu-latest
    
    outputs:
      directories: ${{ steps.module-directories.outputs.directories }}

    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Get module directories
        id: module-directories
        uses: aardex/AardexActions/terraform-module-directories@main
        with:
          exclude_directories: '*/sample/*'
```
