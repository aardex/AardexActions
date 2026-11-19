# Checkov and Trivy scans: adoption guide

[`checkov-scan`](../../checkov-scan/README.md) and [`trivy-scan`](../../trivy-scan/README.md) are reusable composite actions that scan a **checked-out consumer repository**. They do not install a workflow automatically: each consumer owns its triggers, branch protection and finding triage. No local Python scripts, `security/` directory, cloud credentials or GitHub Code Scanning are required. The actions' `action.yml` files define the authoritative inputs and defaults.

## What the scans do

| Action | Default scope | Job result |
| --- | --- | --- |
| Checkov | Static checks on the repository (`directory: .`, `framework: all`), including applicable IaC, Dockerfiles and GitHub workflows. Excludes `.terraform` and `.security-reports`. No rule is skipped by the action's default config. | Fails on findings (`soft-fail: 'false'`), scanner errors or missing SARIF. |
| Trivy | Filesystem scan (`fs .`) for `vuln,secret,misconfig` at `HIGH,CRITICAL` severity. Excludes `.git`, `.terraform` and `.security-reports`. | Findings are informational (`exit-code: '0'`); scanner errors or missing SARIF fail. |

A red Checkov job with an uploaded report can therefore be an **expected finding outcome**, not a broken integration. A green Trivy job does **not** mean zero findings. Severity filtering and filesystem dependency detection are not an exhaustive secret, .NET dependency or image inventory. Neither action inspects built image layers or validates the deployed Azure environment.

## Add a workflow to a consumer repository

Create `.github/workflows/security-scans.yml` (or adapt the [AcquisitionComponent example](https://github.com/aardex/AcquisitionComponent/blob/develop/.github/workflows/manual-security-scans.yml)):

```yaml
name: Checkov and Trivy scans
on:
  workflow_dispatch:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
jobs:
  checkov:
    name: Checkov (source/IaC)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
      - uses: aardex/AardexActions/checkov-scan@52f32c3871f22c07466e82e15463a0a5c24a6f8a
  trivy:
    name: Trivy (filesystem)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
      - uses: aardex/AardexActions/trivy-scan@52f32c3871f22c07466e82e15463a0a5c24a6f8a
```

The example pins the revision used by AcquisitionComponent. Review and pin the intended revision in each consumer; update both references when upgrading. To run only on demand, remove `pull_request`. For forked PRs, check whether the organization's policy grants access to the shared private actions. Before making Checkov a *required* check, triage existing findings and agree on how to handle the backlog: a PR can remain red even if it changes no affected files. Do not disable rules merely to make CI green.

## Optional project configuration files

These names are **examples**, not required files. Pass each path explicitly in `with:`; a supplied but missing file fails the job. Only create a file when the project has a documented reason to override the defaults.

| Example file | Action input | Initial content |
| --- | --- | --- |
| `security/checkov.yaml` | Checkov `config-file` | Checkov YAML, e.g. `skip-check: []` to retain all checks. |
| `security/trivy.yaml` | Trivy `config-file` | Trivy YAML, e.g. `scan: {skip-files: []}`. This is **not** the ignore list. |
| `security/trivyignore.yaml` | Trivy `ignore-file` | YAML ignore lists: `vulnerabilities`, `misconfigurations` and `secrets`, all empty initially. |

Set only the inputs corresponding to files that actually exist:

```yaml
- uses: aardex/AardexActions/checkov-scan@52f32c3871f22c07466e82e15463a0a5c24a6f8a
  with:
    config-file: security/checkov.yaml
- uses: aardex/AardexActions/trivy-scan@52f32c3871f22c07466e82e15463a0a5c24a6f8a
  with:
    config-file: security/trivy.yaml
    ignore-file: security/trivyignore.yaml
```

Copy each of these **separate** examples only into its matching file:

```yaml
# security/checkov.yaml
skip-check: []
```

```yaml
# security/trivy.yaml
scan:
  skip-files: []
```

```yaml
# security/trivyignore.yaml
vulnerabilities: []
misconfigurations: []
secrets: []
```

After review of a **confirmed** false positive, Trivy YAML ignores can target one rule and file. This example is illustrative only; replace the ID, path, reason and date with the reviewed case:

```yaml
misconfigurations:
  - id: DS-0002
    paths:
      - "docker/example/Dockerfile"
    statement: "Reviewed false positive; reference the team's decision"
    expired_at: 2027-01-31
```

Trivy YAML ignores are experimental in the pinned version: rerun the scan to confirm that only the intended occurrence is suppressed. Never ignore an actual secret instead of removing and revoking it. Checkov's `skip-check: [CKV_…]` suppresses a rule **throughout the scan**, not just one occurrence; prefer fixing the underlying issue and review any exception. Do not assume an IaC inline suppression also applies to Checkov's secret scanner.

When no input is supplied, the actions generate explicit **no-exception** configs in `.security-reports`. Trivy receives an empty config and an empty ignore list; a repository's `trivy.yaml` or `.trivyignore` is not an implicit override. Checkov merges discovered `.checkov.yaml/.yml` even when `--config-file` is specified, so the action **fails closed** if it finds an unselected implicit config in the scanned directory, current directory or home. Pass the discovered file as `config-file` if you intend to use it, and resolve any second conflicting implicit config. Other action inputs (`framework`, `skip-path`, `scanners`, `severity`, `skip-dirs`, etc.) become CLI arguments and may override equivalent YAML keys; consult the `action.yml` files before adding options.

Syntax references: [Checkov CLI](https://www.checkov.io/2.Basics/CLI%20Command%20Reference.html), [Trivy config](https://trivy.dev/latest/docs/references/configuration/config-file/), [Trivy YAML ignore format](https://trivy.dev/latest/docs/configuration/filtering/#trivyignoreyaml). Check compatibility with the **pinned scanner version** before introducing additional options.

## Interpret the reports

1. Open the run's **GitHub Actions → Summary**. Each job shows a SARIF result count and counts by **rule ID**; it does not copy locations, code snippets or detected values into the summary. A result is a scanner finding, not a confirmed vulnerability or proof about deployed resources.
2. Download the `checkov-sarif` (`results.sarif`) or `trivy-sarif` (`trivy-results.sarif`) artifact from **that run** to inspect rule, location, severity when available and context. Default retention is **7 days**. Access follows the repository's GitHub permissions; Checkov logs and SARIF may contain code or sensitive values. Do not share raw reports in public channels, PR comments or tickets.
3. Classify each finding: fix, investigate, duplicate, or documented false positive. A high-entropy secret detection (e.g. `CKV_SECRET_6`) is not proof of a real secret; examine it privately. If real, remove and revoke it. If false, prefer changing the test fixture or a narrowly reviewed exception over disabling the rule globally.
4. Fix and triage findings in a separate branch and rerun the workflow. Compare rule IDs **and individual occurrences**, not just a green/red job or total count; Trivy's vulnerability database can change between runs. Changing either action's blocking behavior requires an explicit team decision.

For the complete input contract, see [Checkov](../../checkov-scan/README.md) and [Trivy](../../trivy-scan/README.md).
