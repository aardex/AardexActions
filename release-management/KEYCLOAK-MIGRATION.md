# Keycloak migration after shared PR merge

No Keycloak file is changed by this extraction. Plan based on current pilot `main` at `951e17b5389d71fdd3e32a2d2dae946746b27cf7`; refresh that branch before preparing migration.

## Pin and review boundary

After the AardexActions PR is human-reviewed and merged, read its **actual merge commit SHA** from GitHub, verify it is reachable on `aardex/AardexActions/main`, and replace every `REVIEWED_MERGED_SHA` with that full SHA. If squash-merged, use the squash commit, never this implementation branch head. That immutable SHA cannot be named before merge and is intentionally not guessed. Create a separate Keycloak migration PR; review local/hosted parity before adoption. Do not merge this extraction automatically.

## Exact file changes

Remove:

- `scripts/release/release.py` — shared deterministic engine.
- `tests/release/test_release.py` — shared policy/lifecycle/publication fixtures; Keycloak-specific workflow assertions may be retained as repository tests under a product CI status if useful.
- `.github/workflows/release-tests.yml` — both required contexts now come from trusted shared validation/proposal; do not retain a competing check named `release-tests`.

Replace with thin wrappers from [examples](examples/pr-inputs.yml):

- `.github/workflows/pr-inputs.yml` — `pull_request_target` + trusted `main` checkout + `validate-pr`; retain optional manual PR validation by adding a dispatch input and trunk-only guard if wanted.
- `.github/workflows/release-pr.yml` — push/dispatch/successful publication catch-up + `propose`; use one serial proposal group.
- `.github/workflows/release.yml` — managed merged PR/manual recovery + `publish`; no copied publisher or second checkout. Use one serial publication group.

Update repository-owned documentation:

- `documentation/release.md` — point to the shared contract/pinned revision, explain the new status meaning and wrapper/recovery path; preserve Keycloak/bootstrap facts.
- `documentation/release-extraction.md` — replace the earlier reusable-workflow/hook proposal with this implemented composite interface and migration pin.
- `documentation/development.md` — replace removed engine-suite commands with shared CI references; retain product/docs check commands.
- Any remaining mentions of removed engine files found during the fresh migration audit.

Remain repository-owned and byte-unchanged in the extraction:

- `version.txt`, `CHANGELOG.md`, `.release/baseline.json`, `.release/candidate.json` — release authority/history/evidence; migration does not reset them or fabricate history.
- `scripts/release/check-doc-links.py` — Keycloak documentation check; retain under separate read-only product/docs CI, not a privileged hook. Its document set is consumer-specific.
- `scripts/release/build-assets.py`, `.github/workflows/build.yml` — Keycloak packaging.
- `.github/workflows/publish-image.yml`, `.github/workflows/deploy.yml`, `.github/workflows/initial-environment.yml` — separate operational delivery/infrastructure workflows.
- Dockerfiles, theme/policy/package files, Terraform/version/changelog, deployment docs and all other consumer content.

## Inputs in all three wrappers

| Input | Keycloak value |
| --- | --- |
| `trunk-branch` | `main` (default) |
| `version-file` | `version.txt` (default) |
| `changelog-file` | `CHANGELOG.md` (default) |
| `candidate-file` | `.release/candidate.json` (default) |
| `baseline-file` | `.release/baseline.json` (default) |
| `managed-branch` | `release/keycloak` (explicit in all calls and publication guard) |
| `release-name` | `Keycloak` (explicit in all calls) |
| `tag-prefix` | `v` (default) |
| `github-token` | Native `${{ github.token }}` (default) |
| `command` | `validate-pr`, `propose`, or `publish` |
| `pr` | Event PR number; publication manual dispatch may pass `inputs.release_pr` |
| `immutability-confirmed` | Publication only: `${{ vars.RELEASE_IMMUTABILITY_CONFIRMED }}` |

Use default path/trunk/tag inputs by omission; only `managed-branch` and `release-name` add two lines per call. The publication guard must use `release/keycloak`; the proposal catch-up name must match the chosen publication workflow name. Keep the stable branch after merging candidates, fresh review dismissal, required `release-inputs`/`release-tests`, human squash merging and protected immutable tags/releases. No new cloud or package permission is introduced.

## Acceptance after migration preparation

Run shared local tests/metadata/actionlint and verify wrapper permissions/trusted checkout/pinned merge SHA. Confirm no duplicate same-name status checks survive. Verify current `v1.1.0` tag/immutable Release and preserved version/candidate/changelog before enabling the consumer change. A non-bumping migration alone should produce no candidate; the next natural `fix`/`feat` proves the hosted native-token proposal/status/approval/publish mapping. Migration changes production release delivery and requires the explicitly authorized Keycloak adoption step; this extraction does not execute it.
