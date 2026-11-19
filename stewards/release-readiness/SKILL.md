---
name: aardex-release-readiness
description: Produce an advisory release-readiness report for an AARDEX managed Release PR or published release, consolidating existing deterministic evidence (Release PR, candidate.json, gate_snapshot, statuses/checks, release manifest, changelog/version) and separating verified facts, AI observations, missing evidence and human decisions. Use when asked whether a release candidate is ready, to review a Release PR, or to summarise a release.
---

# AARDEX release readiness

Advisory assistance for EN-47. The release manager decides. The shared
`aardex/AardexActions/release-management` engine, GitHub rulesets and humans own every
deterministic check and approval; you only consolidate and interpret their evidence.

## Inputs

A managed Release PR (`owner/repo#N`, usually titled `chore(release): X.Y.Z` on the
consumer's managed branch) and/or a published tag (`vX.Y.Z`).

## 1. Collect facts (deterministic, read-only)

Run the collector shipped next to this file with the user's `gh` authentication:

```bash
python3 -I <this-skill-dir>/collect_evidence.py --repo owner/repo --pr N   > evidence.json
python3 -I <this-skill-dir>/collect_evidence.py --repo owner/repo --tag vX.Y.Z > evidence.json
```

If the skill directory is not available, fetch the same script from
`aardex/AardexActions` (`stewards/release-readiness/collect_evidence.py`) with
`gh api -H 'Accept: application/vnd.github.raw'`. It issues GET requests only.

`evidence.json` is the only source for **Verified facts**. Its `missing` list names
evidence that does not exist; `api_errors` names evidence that could not be read — an
error is *unknown*, never *absent* and never *passed*.

## 2. Understand what the evidence means

Read the consumer's release documentation (e.g. `documentation/release.md`,
`docs/release.md`) and, for semantics, the engine contract at the pinned revision
(`workflow_pins` in the facts): `release-management/README.md` and, when it exists at that revision,
`release-management/deterministic-gates.md`. Key meanings to respect:
- `release-inputs` / `release-tests` are release *mechanics*, never product tests.
- A manifest section with `state: missing` means not collected; `available` means
  declared, not independently verified.
- No `gate_snapshot` means no consumer gate policy was pinned for that candidate.
- `generator.conclusion: null` in a manifest is expected (the publisher was still running).

## 3. Gather context for observations (optional)

- Included PRs: titles, descriptions and file lists (`included_prs[].files`) to spot
  database migrations, IaC/Terraform, workflow, security-sensitive or breaking changes.
- Jira: look up `jira_keys` with the available Atlassian integration for status and scope.
  Keys are traceability, not acceptance.
- Documentation: for each included PR, check whether a documentation-impact assessment
  (aardex-doc-impact comment or doc changes) exists; flag likely gaps.

## 4. Report

```markdown
<!-- aardex-release-readiness -->
## Release readiness — <repo> <version> (Release PR #N @ <short head sha>)

### 1. Verified facts
Each line cites the evidence field (e.g. `release_files_at_head.version_txt`).
- Scope: version, previous version, base SHA, included PRs, Jira keys.
- Release PR: state, head SHA, merge SHA, latest reviews and whether each is on the head.
- Release files: version.txt, candidate version, latest CHANGELOG heading.
- Checks on head / merge SHA: name → status/conclusion (actual values, including pending/failed).
- Gates: pinned policy and `gate_snapshot` presence.
- Release (if published): tag SHA, immutable/draft/prerelease, manifest digest match,
  manifest section states and reasons.
- Comparisons only between two quoted collected values (e.g. "version.txt 1.2.0 = candidate 1.2.0").

### 2. AI observations
Interpretation, consistency analysis and suspected risks, each labelled as an
observation with its basis (migrations, IaC, breaking-change hints, changelog wording,
documentation gaps, Jira status). Never phrased as a passed or failed check.

### 3. Missing evidence / unresolved warnings
Everything in `missing` and `api_errors`, plus evidence the consumer documentation says
should exist but does not (e.g. no artifact digest, no manifest, no consumer check on head).

### 4. Human decisions required
Concrete decisions for the release manager / reviewers / QMS owner (approve exact head,
accept missing artifact evidence, confirm migration rollout, controlled-document impact…).

_Advisory AI analysis (aardex-release-readiness). Deterministic results are those cited in
section 1; this report is not a gate, approval or attestation._
```

A short report is better than a long one. If the facts are consistent and nothing is
missing beyond documented, accepted gaps, say so plainly.

## Posting (optional, only when the user asks)

Post or update one marked comment on the Release PR, exactly as in the aardex-doc-impact
skill, with marker `<!-- aardex-release-readiness -->`. A comment does not change the PR
head, statuses or approvals.

## Never

- Push to, approve, merge, re-run or edit the Release PR, its managed branch, tags,
  GitHub Releases, assets, `.release/*`, `version.txt` or `CHANGELOG.md`.
- Re-implement or override the engine's validation, or declare readiness "passed".
- Fill a gap with an assumption: an unread value is unknown.
