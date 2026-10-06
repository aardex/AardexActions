# AARDEX release management V1

A small composite action replaces copied application/service release engines. The consumer owns three thin trigger/permission/checkout wrappers; the pinned action owns deterministic release policy and GitHub-only publication.

Normal PR → merge to trunk → deterministic SemVer proposal → one managed Release PR → human approval of its exact final head → human squash merge → immutable version tag → immutable GitHub Release.

No artifact/package/image publication, Azure/ACR authentication, deployment, environment promotion, Terraform/IaC semantics, prerelease channels, arbitrary shell hooks, SBOM/provenance or EN-13 evidence is included. These remain separate delivery/governance concerns; EN-42 may inform a later version.

## Responsibility boundaries

| Capability | Ownership / V1 handling |
| --- | --- |
| Conventional titles, stable SemVer/highest bump, first-parent merged-PR identity | Shared action; fixed release policy |
| Deterministic notes/candidate, exactly three files, stable branch without force-push | Shared release engine |
| Trusted validation, native bot identity, fresh exact-head statuses/approval | Shared release engine |
| Human squash merge, exact SHA, fresh identities, immutable readback | Shared release engine |
| Approved pending-publication deferral; partial/duplicate/conflict blockers | Shared release engine |
| Trunk, four paths, managed branch, display name, tag prefix | Consumer configuration; small validated input surface |
| Event triggers, concurrency, native-token permissions, checkout, branch/tag rules | Consumer workflows and administrator settings |
| Engine tests and compilation | AardexActions CI |
| Product build tests and documentation checks | Consumer tooling; separate from shared required statuses |
| Current version, bootstrap boundary and existing history | Consumer-owned release authority and evidence |
| Artifact packaging and publication | Consumer delivery tooling; outside this action |
| Azure/ACR, rollout/rollback, SBOM/provenance | Separate delivery/governance concerns |

The composite action keeps event triggers local and shared code pinned outside the consumer checkout. Validation never executes consumer code or arbitrary hooks. Publication reads the resolved merge as Git objects, so no copied publisher or second checkout is needed. Shared unit tests run in AardexActions CI; consumer statuses describe runtime policy/mechanics validation, not a repeated library suite or product build.

## Consumer prerequisites

GitHub.com application/service repository; Linux GitHub-hosted runner with Git and Python 3.11+; reviewed trunk as the default branch; full trusted trunk checkout with `persist-credentials: false`; native `GITHUB_TOKEN`; Actions allowed to create PRs. No package install or external runtime service is required by the action. Origin must be the consumer's canonical HTTPS GitHub repository URL.

Pin **every** wrapper to the full reviewed **merged AardexActions commit SHA**. `REVIEWED_MERGED_SHA` in the [examples](examples/pr-inputs.yml) is a deliberate placeholder: replace it after this implementation PR merges. Do not adopt a feature-branch SHA that squash merge may leave unreachable.

## Inputs

[Action metadata](action.yml) is the executable interface. Configuration is identical across validation, proposal, resolution and publication.

| Input | Default | Meaning |
| --- | --- | --- |
| `command` | Required | `validate-pr`, `propose`, `resolve`, `publish` |
| `pr` | Empty | Positive PR number; required except for `propose` |
| `trunk-branch` | `main` | Reviewed default/trunk branch |
| `version-file` | `version.txt` | Sole stable SemVer authority |
| `changelog-file` | `CHANGELOG.md` | Preserved history plus generated notes |
| `candidate-file` | `.release/candidate.json` | Generated candidate metadata |
| `baseline-file` | `.release/baseline.json` | Approved initial history boundary |
| `managed-branch` | `release/managed` | One stable in-repository branch |
| `release-name` | `Release` | GitHub Release name is `<name> X.Y.Z` |
| `tag-prefix` | `v` | Tag is `<prefix>X.Y.Z`; empty is allowed |
| `immutability-confirmed` | `false` | For publish, pass `${{ vars.RELEASE_IMMUTABILITY_CONFIRMED }}`; must equal `true` |

Paths must be distinct repository-relative regular files using letters, digits, `_`, `.`, `/`, `-`; no absolute/traversal/empty segments, `.git*` segments (including workflow paths), option-like segments, overlapping paths, symlinks or executable blobs. Branch inputs are restricted valid Git branch names; managed branch differs from trunk. Tag prefixes use only letters, digits, `_`, `-`. No custom title types/bump mappings, candidate files, hooks or publication bypasses exist.

## Outputs

Unset outputs are empty. Failure produces no success result.

| Output | Commands / meaning |
| --- | --- |
| `result` | `validate-pr`: `validated`; `propose`: `candidate`, `no-change`, `publication-pending`; `resolve`: `resolved`; `publish`: `published` |
| `pr` | Validated, proposed, resolved or published PR number |
| `head-sha` | Validated/proposed exact PR head |
| `version` | Proposed/published stable SemVer |
| `sha` | Resolved/published exact Release PR merge SHA |
| `tag` | Published tag |
| `release-url` | Published GitHub Release URL |
| `immutable` | `true` only after successful publication readback |

`resolve` checks merged PR identity, human merge and exact-head approval and returns its merge SHA; it performs no publication and is not a substitute for publication preflight. `publish` independently repeats those checks, fetches the exact approved objects and validates candidate/merge reproduction against trunk history before any mutation. No second consumer checkout or approval gate is needed.

## Permissions and trusted-code boundary

| Wrapper / command | Minimum permissions |
| --- | --- |
| Validate (`pull_request_target`) | `contents: read`, `pull-requests: read`, `statuses: write` |
| Propose (`push`, dispatch, successful publication catch-up) | `contents: write`, `pull-requests: write`, `statuses: write` |
| Publish (merged PR or recovery dispatch) | `contents: write`, `pull-requests: read` |
| Optional standalone resolve | `contents: read`, `pull-requests: read` |

The action binds `GH_TOKEN` directly to `${{ github.token }}` from the consumer job. Native `GITHUB_TOKEN` is sufficient; the public interface exposes no credential override and consumers do not pass a token. PAT/GitHub App credentials are outside the V1 interface. The token is sent only to GitHub APIs and to Git fetch through a scoped child environment, never in command arguments, logs or persisted Git configuration. API diagnostics omit bodies/headers. No Administration, Actions/Workflows write, cloud, package or identity token permissions are needed. A fresh exact-SHA tag is created first; Release creation uses default trunk only as an unused creation hint. This avoids GitHub's Workflows-write check for recovery of an older source containing different workflows, which native `GITHUB_TOKEN` cannot satisfy. The tag and deterministic body, not a moving branch, prove release source identity. See [GitHub token permissions](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).

Privileged workflows checkout only trusted trunk. The action executes its own pinned `release.py` via isolated Python (`-I`), so consumer modules cannot shadow the shared engine/stdlib. PR objects are fetched and inspected with Git as data; no PR checkout, installation, imports or shell execution occurs. Normal PRs cannot change version/history/candidate/baseline. Workflow/engine changes follow ordinary human-reviewed PRs. Pinning reviewed code is part of the trust boundary.

Managed PRs must be in-repository and created by `github-actions[bot]` with bot identity. The proposal appends commits to one stable branch using `force: false`, includes the previous head as a parent, and creates only the exact generated files. Byte comparisons preserve line endings and file modes. Candidate head/trunk are rechecked after validation. Auto-merge is forbidden. Publication requires latest non-comment approval from a human on the final head, a human merge, a one-parent squash commit on trunk's first-parent history, and the same reproducible tree as the approved head.

## Required statuses and rules

- `release-inputs`: Conventional PR metadata and protected release files are valid. For the managed PR, bot/branch/repository identity, version/title and exact generated files reproduce.
- `release-tests`: The pinned shared deterministic engine validated release policy/mechanics. Normal PRs pass policy/protected-file checks; managed PRs also pass full candidate reproduction and Git whitespace checks. Shared unit/AST/metadata/link checks run in AardexActions CI. This status never means the product build/test suite passed.

Validation publishes both statuses directly on the exact normal PR head. Proposal publishes pending then success/failure for both contexts on every candidate head. No separate consumer `release-tests.yml`, copied engine tests, path-filter trick or approval-gated same-name check is needed. Product checks keep separate names and permissions; avoid creating check runs with these required context names.

Administrator setup: require PRs, human reviews, both statuses (expected producer GitHub Actions), stale-review dismissal, and up-to-date branches on trunk; enable squash merging, disable managed-PR auto-merge, and block direct/force pushes. Protect version tags against update/deletion while allowing fresh tags. Preserve the managed branch across merges (disable automatic head deletion or exempt it), allow bot append updates but deny force pushes. Require human merge authority. Trunk must remain the configured default branch for `workflow_run` catch-up. Consumer wrappers serialize proposal and publication separately with cancellation disabled. A concurrent trunk advance can fail a stale proposal safely; rerun on current trunk.

Enable **GitHub Release immutability**, then set the repository Actions **variable** `RELEASE_IMMUTABILITY_CONFIRMED=true`. No secret or GitHub Environment is needed. The variable authorizes the preflight only: the engine reads back `immutable=true`, non-draft/non-prerelease, exact tag SHA, release source hint and deterministic body after publication. See [immutable releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#immutable-releases) and [release API](https://docs.github.com/en/rest/releases/releases#create-a-release).

## Version, history and bootstrap

Titles use `type(optional-scope)!: description`. Allowed types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `build`, `ci`, `style`, `revert`. `feat` bumps minor; `fix` bumps patch; explicit `!` bumps major; other types do not bump. Highest bump wins, with lower components reset. Scope `release` is reserved. Stable `X.Y.Z` only, without leading zeros, prerelease or build metadata. Developer intermediate commit messages need no grammar; source trunk commits must identify exactly one merged PR.

Metadata contains `base_sha`, `previous_version`, `version`, `date`, and ordered `changes` with `number`, `title`, `sha`. Git first-parent history supplies source order, exact merged SHAs and date; no runner-clock dates or invented history. Notes group Breaking changes, Features, Fixes and Other changes and retain PR links/exact source SHAs. Historical changelog text remains byte-for-byte. Editing historical PR titles changes trusted inputs and requires regeneration/reapproval.

Minimal onboarding for an existing repository:

1. Establish reviewed `main` as default/trunk and a squash-merge policy.
2. Identify the current stable version; verify or add `version.txt` with that version and newline.
3. Establish `CHANGELOG.md` with preserved existing history and a `## [X.Y.Z]` heading for the current version. If history is absent, record only a truthful bootstrap boundary, not reconstructed historical changes.
4. Add `.release/baseline.json` with `{"version":"X.Y.Z","sha":"<full reviewed trunk SHA>"}`. The SHA must be on first-parent trunk history. Choose a boundary that excludes unsupported pre-bootstrap direct commits. The reviewed onboarding PR is normally non-bumping `chore(ci)` and starts automatic history; do not add candidate metadata manually. Older tags/releases are not recertified.
5. Add the three [thin wrappers](#consumer-workflows), pinning the reviewed merged shared SHA. Keep existing application CI separate.
6. Configure the PR/branch/tag rules, required statuses and Actions PR-creation permission above.
7. Enable GitHub Release immutability and verify the setting.
8. Set repository variable `RELEASE_IMMUTABILITY_CONFIRMED=true`.
9. Prove one natural `fix`/`feat` PR → candidate → exact-head human approval → human squash merge → correct immutable tag/Release. Verify hosted native-token permissions and source mapping; local fixtures alone cannot prove repository settings.

No historical release reconstruction, Azure setup or artifact publisher is a prerequisite. Bootstrap authority files require an administrator-reviewed initial installation/transition because ordinary validation intentionally rejects their mutation.

## Recovery

| State after approved merge | Behavior |
| --- | --- |
| Neither tag nor Release | Proposal validates the approved/reproducible prior merge and returns `publication-pending`; correct the cause and dispatch publish naming that exact merged PR |
| Tag only / Release only | Block; human reconciliation required |
| Wrong tag SHA / conflicting version | Block; never move/delete evidence automatically |
| Draft, prerelease, mutable or conflicting Release | Block; human reconciliation required |
| Both correct immutable identities | Next proposal uses the actual first-parent release merge as boundary |
| Any existing identity during publish | Reject duplicate/partial retry before creating anything |

A successful publication workflow triggers proposal catch-up for intervening trunk merges. GitHub API failures stop execution. Creation is intentionally not transactionally atomic: a failure after tag creation or draft creation leaves evidence that blocks automatic retry. Recovery may retry automatically only while **both identities are absent**, from the already approved merged PR, with full revalidation. Partial publication requires a separately reviewed manual repair; the engine never deletes/moves tags or rewrites an existing Release. For a manually bootstrapped immutable record, the creation hint may be trunk only when the tag independently proves the exact source; new publications also use trunk as the unused creation hint after creating the exact tag, and verify the full source SHA through tag/body readback.

## Consumer workflows

Copy these small wrappers into `.github/workflows/`, replace `REVIEWED_MERGED_SHA`, and pass identical non-default configuration in each action call. For a different trunk/managed branch, update literal trigger/guard/checkout names too. Keep publication workflow name consistent with proposal's `workflow_run.workflows`. The examples are complete, actionlint-checked templates:

- [PR validation: 24 lines](examples/pr-inputs.yml), using `pull_request_target` and trusted trunk checkout.
- [Release proposal: 31 lines](examples/release-pr.yml), using push/dispatch/successful publication catch-up.
- [Publication: 37 lines](examples/release.yml), using merged managed PR or explicit recovery number.

No application code execution belongs in these privileged wrappers. Optional product CI and documentation checks stay in separate read-only workflows.

## Maintainer validation

`python3 -m unittest discover -s release-management/tests -v` uses disposable local Git repositories, in-memory GitHub APIs, fake tokens and network denial. It creates no live PRs, tags or Releases, executes no consumer code and requires no credentials. The fixture Git origin is always its own temporary directory. Fixtures explicitly disable inherited line-ending conversion/hooks; HTTP tests mock transport.

`python3 -m compileall -q release-management` checks compilation. Install the pinned [CI-only dependencies](requirements-ci.txt) in a disposable virtual environment, then run `python3 release-management/check.py` for AST/action-metadata/Bash-syntax/local-doc-link checks. Actionlint checks the focused CI workflow and example wrappers; `git diff --check` checks whitespace. CI has read-only permissions and no publisher invocation. Live onboarding proof remains a separately authorized consumer exercise.
