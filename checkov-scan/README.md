# Checkov scan

Composite action for a checked-out repository. Defaults: full repository, all frameworks, no project config, no skipped rules, SARIF artifact `checkov-sarif` (7 days), and **failure on findings**. It never needs Azure/Bridgecrew credentials and does not upload to GitHub Code Scanning. It uses pinned `bridgecrewio/checkov-action` revision `3f0caf0…` (container tag `ghcr.io/bridgecrewio/checkov:3.4.5`); review image provenance before a compliance gate. The metadata-only job summary lists rule IDs/counts. Scanner logs and SARIF may contain code/secret context: use only in private, access-controlled repositories.

```yaml
jobs:
  checkov:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          persist-credentials: false
      - uses: aardex/AardexActions/checkov-scan@<reviewed-commit-sha>
        # No `security/` directory required.
```

To customize a project, add e.g. `security/checkov.yaml` containing `skip-check: []` and pass `config-file: security/checkov.yaml`. A specified missing file **fails**; an omitted file uses the defaults. Inputs `directory`, `framework`, `skip-path`, `soft-fail`, `artifact-name`, `retention-days` are optional. CLI action inputs may override matching YAML settings. Exclude only generated/local files by default (`.terraform,.security-reports`); document any rule exception with owner, reason and review date. The check's `continue-on-error` is internal to retain the SARIF; a final step restores the original result (a red Checkov job on findings).

Checkov still prints CLI findings, potentially including source snippets, into GitHub Actions logs. This is not an Azure runtime audit or an image-layer scan.
