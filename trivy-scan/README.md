# Trivy filesystem scan

[Adoption guide for both scans, optional configuration and report interpretation](../docs/security-scans/README.md).

Composite action for a checked-out repository. Defaults: `fs .`, `vuln,secret,misconfig`, `HIGH,CRITICAL`, Trivy `v0.70.0`, SARIF artifact `trivy-sarif` (7 days), `exit-code: '0'` on findings. Operational errors and missing SARIF still fail. Without optional inputs, the action generates an explicit empty Trivy config (`{}`) and an empty YAML ignore list: existing `trivy.yaml` or `.trivyignore` files cannot silently change or suppress the scan. No `security/` directory, cloud credentials or GitHub Code Scanning is required. The job summary lists rule IDs/counts, not source snippets; SARIF can contain sensitive findings and must remain private. The action uses pinned `aquasecurity/trivy-action` revision `a9c7b0f…`.

```yaml
jobs:
  trivy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          persist-credentials: false
      - uses: aardex/AardexActions/trivy-scan@<reviewed-commit-sha>
        # No `security/` directory required.
```

Optional project overrides:

```yaml
with:
  config-file: security/trivy.yaml
  ignore-file: security/trivyignore.yaml
```

Both files are optional; a **specified but missing** file fails. Existing implicit Trivy config/ignore files are not opt-in overrides: pass their path explicitly to use them. `scan-ref`, `scanners`, `severity`, `skip-dirs`, `exit-code`, `artifact-name`, `retention-days` are optional inputs. CLI inputs override matching config values. No ignore file means **no suppressed findings**; never add a secret finding to an ignore file instead of handling the incident. Severity filtering may hide some secrets; review scanner behavior before treating this as exhaustive. `fs` does not inspect image layers; the existing `azure-container-app-deploy` action separately scans a published image.
