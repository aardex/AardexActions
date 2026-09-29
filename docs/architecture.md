# Architecture and component boundaries

This repository is a library of **composite GitHub Actions**. Each action directory contains `action.yml` (`runs.using: composite`) and a consumer README. GitHub Actions executes steps in the **consumer's job**, not a hosted service operated by this repository. The consumer supplies its workspace, runner, permissions, credentials and target resources. There is no solution, container image, Terraform infrastructure definition or running service in this repository.

| Boundary | Evidence and responsibility |
| --- | --- |
| Action entry points | Root action directories' `action.yml` files declare inputs, outputs, third-party `uses` and shell steps. The action README describes usage; `action.yml` is authoritative for behavior at this revision. |
| Shared scripts | `scripts/nuget/*.py` read/update consumer `Directory.Build.props` and compute versions; `scripts/azure/update-config.py` reads GitHub environment variables into a consumer JSON config; `scripts/requirements.txt` pins `requests`. `github-version-update/action.sh`, `terraform-module-directories/action.sh` and `terraform-docs-index/action.sh` are action-local scripts. |
| Composition | `azure-container-app-deploy` calls `azure-publish-dotnet-docker`, which calls `azure-publish-docker`. `dotnet-component-release` calls `github-commit-push` and `github-create-tag-release`. Other actions call external GitHub, Azure, Docker, Terraform, Codecov, Trivy or NuGet tooling in the consumer job. Internal `uses: aardex/AardexActions/...@main` references resolve independently of the caller's ref. |
| Consumer integration | Consumers own `.csproj`, `Directory.Build.props`, `Dockerfile`, Terraform modules/state, GitHub environment variables/secrets, Azure resources and workflow permissions. The sole workflow here, `.github/workflows/example-copilot-pr-review.yml`, requests a Copilot PR review comment on opened PRs; it is not a repository-wide build or release pipeline. |

Key side effects differ by action: the Terraform actions may format, plan, apply or destroy infrastructure; Azure actions build/push images and deploy applications; NuGet actions may edit project metadata and publish packages; GitHub actions may commit/push or create tags/releases. Consult [deployment](deployment.md) before execution, and [configuration](configuration.md) for credential/data boundaries. The repository does not define application runtime architecture or production environments.

## Decisions

No component ADR files or ADR index exist at this revision. Do not infer that absence means no decisions were made. For a change that needs a component-specific architectural decision, look for the governing issue/PR or external decision authority with the organization maintainer; link a decision from the affected component README if one is adopted. A repository ADR index should be added when actual ADRs exist, not as an empty placeholder. Ownership and location of any external decision archive need confirmation.
