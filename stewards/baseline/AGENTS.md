# Agent guidance

<!-- Copied from aardex/AardexActions stewards/baseline. Adapt the paths below. -->

## Documentation

- Repository documentation starts at `README.md`; maintainer documentation lives in `docs/`.
- Version-specific documentation for this component changes in the same PR as the code,
  configuration or infrastructure that makes it necessary.
- Cross-project, Confluence and controlled (QMS) documentation is routed, not copied: follow
  the [Documentation Policy](https://github.com/aardex/AardexTechnicalDocumentation/blob/main/documentation/documentation-policy.md).

## Documentation and release assistance

- Documentation impact of a change: use the `aardex-doc-impact` skill.
- Release readiness of a Release PR or release: use the `aardex-release-readiness` skill.
- If the skills are not installed, read and follow
  `https://github.com/aardex/AardexActions/blob/main/stewards/doc-impact/SKILL.md` or
  `https://github.com/aardex/AardexActions/blob/main/stewards/release-readiness/SKILL.md`.
- Both are advisory. Never modify release evidence (`version.txt`, `CHANGELOG.md` release
  sections, `.release/*`), approvals or Release PRs.
