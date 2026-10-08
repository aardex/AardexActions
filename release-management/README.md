# AARDEX release management V1

A small composite action replaces copied application/service release engines. The consumer owns three thin trigger/permission/checkout wrappers; the pinned action owns deterministic release policy and GitHub-only publication.

Normal PR → merge to trunk → deterministic SemVer proposal → one managed Release PR → human approval of its exact final head → human squash merge → immutable version tag → immutable GitHub Release.

Each new source release includes a validated `release-manifest.json` evidence snapshot. A small opt-in consumer policy enforces [deterministic source gates](deterministic-gates.md) before publication. Artifact/package/image publication, Azure/ACR authentication, deployment, environment promotion, prerelease channels and arbitrary shell hooks remain outside this action. EN-45 artifact promotion is not implemented. The manifest is neither deployment authorization nor a compliance/readiness attestation; the [release and documentation standard](https://github.com/aardex/AardexTechnicalDocumentation/blob/main/standards/release-and-documentation-standard.md) owns governance.

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
| Source identities, observed GitHub controls, manifest validation/upload/integrity | Shared publisher |
| Explicit consumer gates and approval-bound source evidence | Consumer owns producers/policy; shared engine verifies pinned identities/results |
| Artifact/migration/dependency/SBOM/provenance declarations | Optional consumer data; no verification of product bytes or external references |
| Azure/ACR, rollout/rollback, SBOM/provenance generation | Separate delivery/governance concerns |

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
| `manifest-data` | Empty | Publish-only JSON containing any of `artifacts`, `migrations`, `dependencies`, `sbom`, `provenance`; at most 64 KiB, strict fields, no duplicate keys |
| `gate-policy-sha` | Empty | Exact reviewed consumer trunk commit containing `.release/gates.json` and producer workflows; identical in all wrappers, required when the policy exists |

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
| Publish (merged PR or recovery dispatch) | `contents: write`, `pull-requests: read`, `statuses: read`, `checks: read`, `actions: read` |
| Optional standalone resolve | `contents: read`, `pull-requests: read` |

With a gate policy, proposal and managed Release PR validation additionally require
`checks: read` and `actions: read`. Publication already has these EN-44 read
permissions. The examples include these reads; no Actions/Workflows write,
administration or credential override is needed.

The action binds `GH_TOKEN` directly to `${{ github.token }}` from the consumer job. Native `GITHUB_TOKEN` is sufficient; the public interface exposes no credential override and consumers do not pass a token. PAT/GitHub App credentials are outside the V1 interface. The token is sent only to GitHub APIs and to Git fetch through a scoped child environment, never in command arguments, logs or persisted Git configuration. API diagnostics omit bodies/headers. No Administration, Actions/Workflows write, cloud, package or identity token permissions are needed. A fresh exact-SHA tag is created first; Release creation uses default trunk only as an unused creation hint. This avoids GitHub's Workflows-write check for recovery of an older source containing different workflows, which native `GITHUB_TOKEN` cannot satisfy. The tag and deterministic body, not a moving branch, prove release source identity. See [GitHub token permissions](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).

Privileged workflows checkout only trusted trunk. The action executes its own pinned `release.py` via isolated Python (`-I`) and imports manifest support only from its pinned action directory, so consumer modules cannot shadow the shared engine/stdlib. PR objects are fetched and inspected with Git as data; no PR checkout, installation, imports or shell execution occurs. Normal PRs cannot change version/history/candidate/baseline. Workflow/engine changes follow ordinary human-reviewed PRs. Pinning reviewed code is part of the trust boundary.

Managed PRs must be in-repository and created by `github-actions[bot]` with bot identity. The proposal appends commits to one stable branch using `force: false`, includes the previous head as a parent, and creates only the exact generated files. Byte comparisons preserve line endings and file modes. Candidate head/trunk are rechecked after validation. Auto-merge is forbidden. Publication requires latest non-comment approval from a human on the final head, a human merge, a one-parent squash commit on trunk's first-parent history, and the same reproducible tree as the approved head.

## Required statuses and rules

[Deterministic release gates](deterministic-gates.md) describes the small opt-in
consumer policy, exact source/run/job/App provenance, approval-bound candidate
snapshot, pilot inventory and adoption limits. Configure `gate-policy-sha` with a
reviewed consumer commit containing `.release/gates.json`; a present policy with
no pin fails closed. Source gates run during candidate construction/reproduction
and publication. Consumers retain their existing build/test ownership.

- `release-inputs`: Conventional PR metadata and protected release files are valid. For the managed PR, bot/branch/repository identity, version/title and exact generated files reproduce.
- `release-tests`: The pinned shared deterministic engine validated release policy/mechanics. Normal PRs pass policy/protected-file checks; managed PRs also pass full candidate reproduction and Git whitespace checks. Shared unit/AST/metadata/link checks run in AardexActions CI. This status never means the product build/test suite passed.

Validation publishes both statuses directly on the exact normal PR head. Proposal publishes pending then success/failure for both contexts on every candidate head. No separate consumer `release-tests.yml`, copied engine tests, path-filter trick or approval-gated same-name check is needed. Product checks keep separate names and permissions; avoid creating check runs with these required context names.

Administrator setup: require PRs, human reviews, both statuses (expected producer GitHub Actions), stale-review dismissal, and up-to-date branches on trunk; enable squash merging, disable managed-PR auto-merge, and block direct/force pushes. Protect version tags against update/deletion while allowing fresh tags. Preserve the managed branch across merges (disable automatic head deletion or exempt it), allow bot append updates but deny force pushes. Require human merge authority. Trunk must remain the configured default branch for `workflow_run` catch-up. Consumer wrappers serialize proposal and publication separately with cancellation disabled. A concurrent trunk advance can fail a stale proposal safely; rerun on current trunk.

Enable **GitHub Release immutability**, then set the repository Actions **variable** `RELEASE_IMMUTABILITY_CONFIRMED=true`. No secret or GitHub Environment is needed. The variable authorizes the preflight only: the engine reads back `immutable=true`, non-draft/non-prerelease, exact tag SHA, release source hint and deterministic body after publication. See [immutable releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#immutable-releases) and [release API](https://docs.github.com/en/rest/releases/releases#create-a-release).

## Release manifest contract

Gated consumers also retain optional `gate_evidence`, the exact source evidence
frozen in the approved candidate plus approval time. The Schema v1 extension
preserves old manifests and the original observed `checks`; validators using the
old closed schema must update with the action. Gate evidence is generated by the
engine and cannot be injected through `manifest-data`.

[JSON Schema v1](release-manifest.schema.json) and [semantic validation](manifest.py) define the small, closed contract. [The complete synthetic example](examples/release-manifest.json) is schema-valid; its SHAs, run and URLs are fixtures, not hosted evidence. Unknown fields and malformed data fail publication. Runtime needs Python stdlib only; CI also checks the schema/example with a standard Draft 2020-12 validator.

The publisher reuses the resolved candidate changes and exact verified merge SHA. It never derives release source from `GITHUB_SHA` or the current checkout. `release_pr` records its approved head, merge SHA and the existing engine's proven tree equality. Each check retains the SHA actually addressed by GitHub, even when both trees match. Included PR titles supply sorted, unique, case-sensitive Jira keys; keys establish traceability only, without Jira lookup or ticket acceptance.

`generator` records the run, attempt, workflow reference/SHA and run head SHA separately. The current attempt is read from GitHub and must still have no final conclusion. The workflow cannot record its own eventual success, and no post-publication rewrite is attempted. The consumer workflow identity is distinct from the source merge and from the pinned shared action code.

Checks snapshot paginated commit-status history and check runs on the approved Release PR head and release merge SHA. API ids/references identify each observation; records are sorted deterministically. `outcome.status` and `outcome.conclusion` preserve actual values, including pending, queued, in-progress, failed, skipped and cancelled. These observations are not a new gate or an aggregate success verdict. `release-inputs` and `release-tests` are classified as release mechanics, never product tests. Other checks retain their GitHub names without inferring test coverage or correctness. Checks on synthetic PR merge refs, included developer PR heads, or other SHAs are not collected or reassigned. Absent mechanics contexts/check runs are explicit `missing` records. GitHub read/API errors block publication rather than silently claim missing/success.

Optional sections use `{"state":"missing","reason":"..."}` when uncollected, `{"state":"not_applicable","reason":"..."}` for a justified consumer declaration, or `{"state":"available","items":[...]}` for supplied data. The default is `missing`; absence never implies non-applicability. Available supplemental items require `verification: declared` and `release_sha` equal to the exact resolved release SHA. `available` means information is present, not independently verified. Artifact digests must be explicit `sha256:<64 lowercase hex>`; a Git SHA is rejected. Migration, SBOM and provenance references are recorded but not fetched, authenticated, verified or generated. Declared dependencies keep `declared_ref` separate from nullable `resolved`; only an exact Git commit, digest or stable version is accepted as a claimed resolution. Branches/constraints remain unresolved, and even a supplied resolution remains declared.

For example, the optional `manifest-data` input may contain:

```json
{"migrations":{"state":"not_applicable","reason":"Reviewed source change has no database migration"},"artifacts":{"state":"missing","reason":"No image digest supplied by an integrated publisher"}}
```

Consumers need no extra input for a source-only manifest. To supply artifact or dependency data, first use `resolve` to obtain the approved merge SHA and pass structured JSON from trusted tooling; `publish` repeats full resolution and rejects a different attachment SHA. Never use a PR checkout, execute PR tooling with the write token, or substitute the workflow/checkout SHA. The action exposes no shell hook, data-file path, credential override or arbitrary URL fetch. References must contain no credentials or signed query strings. No digest, product test result, SBOM, provenance or deployment record is fabricated.

Network references require explicit HTTPS. Scheme-less references containing `@` before their first path separator are rejected as ambiguous credential data. Container digest references therefore include a registry/repository path, for example `registry.example/service@sha256:<digest>`; repository file paths remain accepted. Malformed reference diagnostics omit the supplied value.

Publication validates the snapshot before mutations, creates the exact source tag and draft through the existing flow, refuses existing assets, uploads the UTF-8 deterministic JSON, and verifies the uploaded asset id/state/size plus GitHub's server-computed SHA-256 before clearing `draft`. Final readback repeats source/release identity and asset integrity checks. A missing GitHub digest blocks publication; there is no filename-only fallback. Authenticated requests use fixed GitHub API/upload hosts and reject redirects; input/API `upload_url` values are never used. The manifest's digest identifies only manifest bytes, never product bytes. GitHub's immutable-release attestation is generated after publication and is not invented as product provenance in this snapshot. See [GitHub's draft-first recommendation](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) and [asset digest API](https://docs.github.com/en/rest/releases/assets).

Historical releases without a manifest remain valid source boundaries under the existing checks; they are never modified or recertified. A new manifest does not establish image publication, Terraform apply, runtime state, deployment approval or global release readiness. Adoption and native-token hosted proof in consumers remain necessary after shared merge.

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
| Draft with missing/corrupt/conflicting manifest or failed upload | Block; preserve draft/tag/assets for human reconciliation |
| Publication/readback fails after clearing draft | Report failure; release may already be immutable; do not retry or overwrite assets |
| Both correct immutable identities | Next proposal uses the actual first-parent release merge as boundary |
| Any existing identity during publish | Reject duplicate/partial retry before creating anything |

A successful publication workflow triggers proposal catch-up for intervening trunk merges. GitHub API failures stop execution. Creation is intentionally not transactionally atomic: a failure after tag creation or draft creation leaves evidence that blocks automatic retry. Recovery may retry automatically only while **both identities are absent**, from the already approved merged PR, with full revalidation. Partial publication requires a separately reviewed manual repair; the engine never deletes/moves tags or rewrites an existing Release. For a manually bootstrapped immutable record, the creation hint may be trunk only when the tag independently proves the exact source; new publications also use trunk as the unused creation hint after creating the exact tag, and verify the full source SHA through tag/body readback.

For manifest/upload failure, retain the failed workflow run/attempt, approved PR head/merge, tag SHA, release id/draft state and asset ids/state/size/digest. Compare against the attempted manifest bytes and SHA-256 when available; a filename alone is insufficient. Do not clear `draft` to bypass a failed manifest check. A maintainer must review the cause and authorize any manual repair before resuming; automatic asset deletion, overwrite, tag movement or cleanup is intentionally unavailable. If publication succeeded but final readback failed, first inspect actual immutable release/asset integrity in read-only mode. Immutable assets cannot be repaired in place; an exceptional recovery belongs to the repository's human process, not an automated recertification. The publisher deliberately refuses all existing identities on rerun, including drafts with a valid manifest.

## Consumer workflows

Copy these small wrappers into `.github/workflows/`, replace `REVIEWED_MERGED_SHA`, and pass identical non-default configuration in each action call. For a different trunk/managed branch, update literal trigger/guard/checkout names too. Keep publication workflow name consistent with proposal's `workflow_run.workflows`. The examples are complete, actionlint-checked templates:

- [PR validation](examples/pr-inputs.yml), using `pull_request_target` and trusted trunk checkout.
- [Release proposal](examples/release-pr.yml), using push/dispatch/successful publication catch-up.
- [Publication](examples/release.yml), using merged managed PR or explicit recovery number and explicit status/check/Actions read permissions.

No application code execution belongs in these privileged wrappers. Optional product CI and documentation checks stay in separate read-only workflows.

## Maintainer validation

`python3 -m unittest discover -s release-management/tests -v` uses disposable local Git repositories, in-memory GitHub APIs, fake tokens and network denial. It creates no live PRs, tags or Releases, executes no consumer code and requires no credentials. The fixture Git origin is always its own temporary directory. Fixtures explicitly disable inherited line-ending conversion/hooks; HTTP tests mock transport.

[Application](tests/fixtures/keycloak.json) and [IaC](tests/fixtures/terraform-runner.json) inputs represent the two source-only pilot shapes, including unavailable image evidence and unresolved IaC dependencies. They are synthetic, not recorded pilot executions. Tests cover actual publication ordering, upload/asset conflict and integrity failures, partial publication, evidence outcomes/attachment SHAs, deterministic serialization, and the unchanged historical-release path. Read-only pilot inventory does not replace hosted acceptance of the new action revision. No image build/push, Terraform command, Azure mutation or real release is a validation step.

`python3 -m compileall -q release-management` checks compilation. Install the pinned [CI-only dependencies](requirements-ci.txt) in a disposable virtual environment, then run `python3 release-management/check.py` for AST/action-metadata/Bash-syntax/local-doc-link checks. Actionlint checks the focused CI workflow and example wrappers; `git diff --check` checks whitespace. CI has read-only permissions and no publisher invocation. Live onboarding proof remains a separately authorized consumer exercise.
