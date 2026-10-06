# Aardex Actions

Reusable composite GitHub Actions for CI/CD in consumer repositories: Terraform validation, documentation and Azure plans; Azure application and image delivery; .NET/NuGet versioning and publication; and GitHub repository automation. This repository contains action definitions and supporting scripts, **not** an application, Terraform stack or .NET solution. A consumer invokes an action at `aardex/AardexActions/<directory>@<ref>` from its own workflow. Check that directory's `action.yml` for the executable input/output contract and its README for usage.

The GitHub organization in the action references is `aardex`; this repository does not identify a named maintainer, escalation owner or approval authority. Confirm ownership and access with the organization maintainers rather than assuming a contact from a commit or token name.

## Actions

| Area | Action directories |
| --- | --- |
| Azure applications and images | [Container App deploy](azure-container-app-deploy/README.md), [.NET App Service deploy](azure-dotnet-app-service-deploy/README.md), [.NET Function deploy](azure-dotnet-function-deploy/README.md), [Java App Service deploy](azure-java-app-service-deploy/README.md), [Docker image publish](azure-publish-docker/README.md), [.NET Docker image publish](azure-publish-dotnet-docker/README.md) |
| .NET / NuGet | [.NET build](dotnet-build/README.md), [component release](dotnet-component-release/README.md), [alpha](nuget-publish-alpha/README.md), [release candidate](nuget-publish-release-candidate/README.md), [release](nuget-publish-release/README.md), [versioned publish](nuget-publish-version/README.md) |
| GitHub release management | [Human-approved release golden path](release-management/README.md) — deterministic Release PRs and immutable GitHub source identities; no artifact publication or deployment |
| GitHub / versioning | [commit and push](github-commit-push/README.md), [commit version](commit-version-changes/README.md), [create tag and release](github-create-tag-release/README.md), [update version](github-version-update/README.md), [Copilot PR review request](copilot-pr-review/README.md) |
| Terraform | [deploy](terraform-deploy/README.md), [destroy](terraform-destroy/README.md), [docs](terraform-docs/README.md), [docs index](terraform-docs-index/README.md), [format and validate](terraform-format-validate/README.md), [module directories](terraform-module-directories/README.md), [version update](terraform-version-update/README.md) |

## Maintainer guide

- [Architecture and boundaries](docs/architecture.md) — composition, script ownership and decision records
- [Development and checks](docs/development.md) — local setup, safe validation and consumer testing
- [Configuration and secrets](docs/configuration.md) — input and credential boundaries
- [Deployment and release](docs/deployment.md) — publication and potentially destructive actions
- [Operations](docs/operations.md) and [troubleshooting](docs/troubleshooting.md) — available signals and diagnostics
- [Change history](CHANGELOG.md) — recorded repository changes and history limitations

**Version coupling:** a reference to `@main` follows the current branch, not a frozen version. Several actions call other actions in this repository using `@main`, even when the caller is pinned to another ref. Inspect transitive references in `action.yml` before changing or testing an action; test in a disposable consumer workflow with a pinned commit/ref where possible. A component README is guidance for this revision, not a guarantee for other refs. No repository-wide release workflow or compatibility policy is defined here.
