# Github Version Update

Retrieve and update the version number based on the input type of release.

## Usage

```yaml
jobs:
  get-sources:
    name: Update Project Version
    runs-on: ubuntu-latest
    
    outputs:
      version: ${{ steps.version-update.outputs.version }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Update Version
        id: version-update
        uses: aardex/AardexActions/terraform-version-update@main
        with:
          type: 'alpha'
```

## Inputs

- `type`: The type of new version: `major`, `minor`, `patch`, `release`, release-candidate`, `alpha`.
- `version_file`: (Optional) The path to the file with version number. Ex: `version.txt`
- `version`: (Optional) To force the current version. Ex: `1.2.3-alpha.456.7`

## Outputs

- `version`: the new generated version.
