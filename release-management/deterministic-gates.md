# Deterministic source release gates (EN-43)

This is the shared implementation contract and a read-only pilot inventory dated
2026-10-08. EN-43 remains open until both consumers adopt and validate the merged
revision. [EN-13](https://aardexgroup.atlassian.net/browse/EN-13) owns release
governance; [EN-44](https://aardexgroup.atlassian.net/browse/EN-44) owns the manifest;
[EN-45](https://aardexgroup.atlassian.net/browse/EN-45) owns artifact promotion.
The [Git-hosted standard](https://github.com/aardex/AardexTechnicalDocumentation/blob/main/standards/release-and-documentation-standard.md)
is normative; the [Confluence operating model](https://aardexgroup.atlassian.net/wiki/spaces/RD/pages/2131656733)
explains the intended separation of automation, assistance and human authority.
The standard is currently a team-validation draft and does not replace QMS.

## Decision and responsibility

Retain the existing three wrappers, consumer CI and GitHub protections. GitHub
rulesets already prevent many unsafe merges; use them first. They do not alone
prove the relationship between a check name, its producer, the approved Release
PR and the source actually published. Keycloak currently requires only mechanics
statuses; the Terraform pilot additionally requires its three consumer checks.
Neither ruleset currently pins an expected integration id. The publisher therefore
needs a small evidence verifier and a source mapping, not a workflow orchestrator.

Consumers own builds, tests, scanner setup and deterministic documentation checks.
GitHub attests runs/jobs/checks. The pinned shared engine verifies the explicitly
selected gates, reproduces mechanics and preserves exact-head human approval and
human squash merge. The manifest retains observations and the evidence actually
used. Engineering/QMS/product/regulatory and deployment approvals remain human.
No script, workflow, Jira lookup, arbitrary URL or AI analysis is invoked by gates.

## Pilot inventory

Live default branches at inspection: Keycloak
`c362aec7cac9e4a26e25f1b4c6b38e7bb7a8b07e`; TerraformGithubRunner
`62fb0c8b7c0d1b4d344b540de84549e1b8faa423`. Both still use shared action
`c73d0bf3cf65fc31392412dc2d9913b17d687cda`; manifest adoption PRs
[Keycloak #32](https://github.com/aardex/keycloak/pull/32) and
[TerraformGithubRunner #33](https://github.com/aardex/TerraformGithubRunner/pull/33)
are open. Consumers were read-only in this run.

| Concern | Keycloak | TerraformGithubRunner | EN-43 treatment after adoption |
| --- | --- | --- | --- |
| Release mechanics | `release-inputs`, `release-tests`; required by active ruleset | Same, required by active ruleset | Recalculate trusted engine policy, protected files, generated candidate and tree equality; statuses stay branch gates, not product tests |
| Consumer contracts | Automatic `consumer-checks`: four offline wrapper/authority tests, compilation, whitespace | Automatic `consumer-checks`: eight offline contract tests | Require the exact integrated-source push run and exact named job from its current attempt |
| Application/packaging | Manual/reusable `build-assets.yml` packages theme/policies/dependencies; no automatic build gate demonstrated | Runner image/provisioning is separate | Not certified by `consumer-checks`; no image publisher changes |
| Product tests | No demonstrated automated Keycloak functional/integration tests | No runner runtime acceptance test in PR CI | Missing capability, not a success and not silently made universal |
| Configuration/docs | `consumer-checks` runs local Markdown link/anchor validation; wrapper/authority checks | `terraform-docs` compares generated references for all three Terraform roots; consumer documentation assertions | Reuse these precise obligations; no semantic documentation-impact certification |
| Terraform format | No equivalent automatic source check identified | `terraform-fmt` executes `terraform fmt -check -recursive` only | Require the exact job; explicitly not `terraform validate` |
| Terraform validate | Operational deployment workflows are not source validation gates | Documented isolated `init -backend=false` + `validate` for project and both tenants; requires private module read access; not implemented in PR CI | Not an available automated gate; do not request backend, Azure secrets, plan or apply |
| GitGuardian | App check `GitGuardian Security Checks`, App id `46505`, on PR heads | Same App check on PR heads | Require current successful App results for every included source PR's exact Git head, with suite identity and tree proof |
| Snyk | Historical statuses currently `error`: private-test quota exhausted | No Snyk status observed on inspected recent PRs | External blocker in Keycloak; absent/unverified in IaC; neither is represented as success |
| Jira traceability | Conventional included PR titles | Same | Reuse resolved changes and extract keys in EN-44; keys are not acceptance evidence |
| Human/QMS | One approving review, stale review dismissal, human release approval/merge; ruleset team bypass exists | Same human review rule; separate required-check ruleset has no bypass | Existing exact-head approval and human merge checks remain; no QMS or production approval inferred |

Successful integrated-source examples:
[Keycloak consumer checks](https://github.com/aardex/keycloak/actions/runs/37443053196),
[Terraform format](https://github.com/aardex/TerraformGithubRunner/actions/runs/37483401992),
[Terraform documentation](https://github.com/aardex/TerraformGithubRunner/actions/runs/37483401969),
[Terraform consumer checks](https://github.com/aardex/TerraformGithubRunner/actions/runs/37483401864).
These runs prove the old consumer jobs at those SHAs, not adoption of this patch.
Both pilots use squash-only integration and active rulesets rather than legacy
branch-protection objects. Required-context rules are strict/up-to-date, but have
no explicit producer integration id. No protections were changed.

## Policy and source identity

Install one small `.release/gates.json` in the consumer. The
[Keycloak](examples/gates-keycloak.json) and
[TerraformGithubRunner](examples/gates-terraform-runner.json) examples select
only the automatic capabilities demonstrated above. The file has exactly two
flat lists: `workflows` with an exact repository workflow path and exact job name;
`checks` with an exact App check name and numeric App id. Lists are bounded, names
are unique, and unknown/duplicate fields fail. There are no expressions, optional
successes, hooks, profiles or orchestration.

Pass `gate-policy-sha: <full reviewed consumer trunk commit SHA>` identically in
all three wrappers. That commit contains the policy and trusted producer workflow
bytes. It must be on the candidate source's first-parent trunk history. The policy
and producer files at the source SHA must match that pin byte-for-byte and be
regular non-executable blobs. Removing the input while the policy exists fails.
Changing policy or producers without reviewed repinning fails. Removing the file
while retaining its pin fails. A new pin changes generated candidate metadata,
requiring a new final-head approval. Trusting a moving ref or policy supplied by
an untrusted PR is unsupported. Trusted trunk wrappers and human governance of
their pins are part of the existing release authority, as with the shared action
pin; this action cannot protect against an administrator replacing the publisher.

The relationships are deliberately distinct:

1. Included source PR head to its squash merge: resolve the merged PR through the
   GitHub PR API, fetch its head object, and prove both complete Git trees match.
   App check and suite must address that exact head SHA from the required App.
   GitHub returns empty suite `pull_requests` for the merged pilot PRs, so this
   transient list is not an authority. The immutable Git-object relationship is
   the proof, not a scanner PR-number claim. No synthetic merge check is silently
   reassigned. If tree/source proof is unavailable, stop.
2. Integrated source to consumer validation: use the latest `push` run for the
   exact candidate `base_sha` on trunk, the current `run_attempt`, its exact named
   job, and the job's attested `check_run_url`. Verify repository, event, branch,
   path, SHA, run/attempt, GitHub Actions App id `15368`, suite, timestamps and
   success on both job and check. PR jobs, dispatch runs and other branches do not
   replace this gate. The reviewed producer must actually checkout its event SHA;
   the supplied examples reuse the pilots' existing default checkout behavior.
3. Integrated source to approved Release PR and published merge: the existing
   engine permits only its generated version/changelog/candidate files, reproduces
   their exact bytes, requires final-head human approval and human squash merge,
   and proves approved-head/merge tree equality. Product source therefore comes
   from the proven integrated source; product tests need not be rerun on the merge.

All required source evidence is frozen as `gate_snapshot` in generated candidate
metadata **before human approval**. It contains policy/source SHAs, exact check/run
identities, attempts, references and SHA-256 fingerprints of fetched GitHub
records. Only fingerprints, not check output payloads, are persisted. Reproducing
the candidate requires the current evidence to match that snapshot. A newer run,
new successful attempt, renamed producer, changed result or retrospective check
edit invalidates it, even when `completed_at` is unchanged. Regenerate and reapprove
the candidate. Results must start after their checked commit and complete before
the release's exact-head human approval. No elapsed-time TTL is invented: freshness
means exact source, latest relevant execution and unchanged approved evidence.

Absent, pending, skipped, neutral, failed, cancelled, timed-out and stale results
all block. No filtering for successful runs or fallback to old results occurs.
An arbitrary commit status cannot replace a workflow job or App check. A commit
status's creator/target URL alone does not attest which workflow wrote it; mechanics
are recomputed by the trusted engine instead of accepting self-declared success.

GitGuardian on the Release PR's own generated head remains an EN-44 observation,
not a gate frozen into the content it scans (which would create a cycle). The
required scans address every included source PR's exact head. GitGuardian is a
secret-diff scan, not a dependency audit, full-history recertification or product
security test. Its existing API result has no immutable scan-range/PR identifier
(`external_id` is empty and `details_url` is the generic dashboard); this gate
attests the trusted App verdict on the mapped Git object, not exact scanner range
coverage. Human review retains responsibility for that limitation.

## Publication and manifest

Verify gates during candidate construction/reproduction and again before
manifest collection, immediately before the first tag mutation, and before
clearing the draft after upload. Any initial read/identity/outcome/policy failure
leaves no tag or draft mutation. A later result change during upload preserves the
partial tag/draft for the existing manual reconciliation process. GitHub does not
provide an atomic transaction spanning reviews, check updates, tags and Releases;
the last successful read is the publication evidence boundary, not an assertion
that an external producer can never change a record later.

EN-44's `checks` keeps its original observed head/merge history and semantics.
The optional `gate_evidence` field is an additive Schema v1 extension containing
the approved source snapshot plus approval time. It records the exact source and
PR-head SHAs actually checked, never relabels them as release merge checks, and
does not assert global release readiness. Old ungated manifests/examples remain
valid. Clients validating against the old closed schema must adopt the new schema
alongside the action; do not silently ignore fields or rewrite historical assets.
The shared [manifest implementation](manifest.py) validates gate references,
source mappings and evidence shape; `manifest-data` cannot supply gate evidence.

## Adoption and operation

After the shared PR is reviewed and merged, consumers still require separate
authorized changes. Reconcile with their open EN-44 PRs; do not mutate them here.

1. Add/review the applicable example as `.release/gates.json`, audit the selected
   producer workflow checkout, job and immutable dependencies, and merge this
   non-bumping governance change through the existing human process. Existing
   pre-EN-43 wrappers can validate this installation; no gate adoption is claimed
   until the next steps are complete. Review any candidate proposed in that window.
2. Pin the merged shared action in all three wrappers. Pin the consumer commit
   from step 1 as `gate-policy-sha` in all three calls, update the consumer pin/input
   guards and documentation, and use only trusted trunk checkouts. Proposal and
   Release PR validation now need `checks: read` and `actions: read` in addition to
   existing permissions. Publication also needs EN-44's `statuses: read`,
   `checks: read`, `actions: read`. No administrative, cloud or token override
   permission is added. Scope these permissions to the relevant jobs.
3. Run the existing consumer checks. A push proposal can race source CI and fail
   safely before creating a candidate. When source CI succeeds, use the existing
   proposal dispatch; rerun an incomplete push validation's existing run as needed.
   No automated waiter, check dispatch or new orchestration is required. Do not
   add path filters that omit the latest source revision's required checks.
4. On a natural releasable source change, verify the new candidate snapshot,
   successful gates, exact-head approval/merge and immutable manifest readback in
   each pilot. Also prove a failed/missing gate blocks using a disposable consumer
   fixture, never a production release. No hosted release exercise was run here.

For intentional policy/producer changes, review the new policy and workflow
commit first, then repin through reviewed trusted wrappers. Until repinning,
publication fails closed. For evidence changes before merge, regenerate the
candidate and obtain a new exact-head approval; do not edit candidate JSON
manually. If evidence changes after the approved merge, that merged snapshot
cannot be reapproved in place: the publisher blocks and a maintainer must review
an exceptional recovery/superseding source transition. There is no automatic
rewrite or exemption. An API read failure with unchanged evidence can be retried
while both release identities are absent. Recovery dispatch cannot bypass gates.
Existing tags/drafts still block automatic retry.

## External gaps and human decisions

Snyk on inspected Keycloak PRs and shared PR #65 reports
`error` / `You have used your limit of private tests`. Its status is not an
App-attested workflow-job identity and currently supplies no successful scan.
No inspected required-context rule makes it a mandatory gate today; this patch
neither changes that policy nor treats the error as success. If applicable human
security policy requires Snyk, **release authorization remains blocked** until the
security owner restores quota and a reliable exact-source result is available.
The targeted remediation is a quota/entitlement decision and review of the
integration's attested producer/source mapping, not disabling the status or
allowing errors. A future trusted consumer scan job can use the existing workflow
gate list after review. No organization configuration was changed. IaC Snyk
coverage requires a separate owner decision because no current result was found.

Other missing controls: automatic Keycloak product build/tests; Terraform static
validation with approved private-module access; full dependency/SBOM/provenance
evidence; runtime/device/runner acceptance; migrations where applicable; semantic
documentation impact and Jira functional acceptance. Backend-disabled validation
needs neither shared state nor Azure/plan/apply; safe private dependency access is
the real IaC integration issue. Plan and apply remain deployment evidence, not
universal source release prerequisites. Keycloak's manual packaging and legacy
image publisher are unchanged and are not certified by this action.

The standard's documentation-impact declaration is a target practice, not an
already implemented deterministic PR obligation. Existing link/generated-reference
checks are enforceable; AI cannot certify absence of impact. Cross-project and
controlled-document implications retain review/QMS responsibility.

Administrator decisions, when needed: approve consumer adoption, govern policy
and publisher pins (optional CODEOWNERS review), confirm required-check producer
integration ids and bypass policy, and resolve Snyk quota/security applicability.
Existing immutability confirmation and human controls remain. This patch makes no
secret, rule, organization, identity, Azure, Terraform state or publisher changes.

## Validation boundary

The [isolated suite](README.md#maintainer-validation) uses disposable local Git,
in-memory GitHub run/job/check APIs, fake identities and denied HTTP access. Gate
fixtures represent both pilots; they execute no consumer, Terraform or packaging
code. Initial regressions reproduced publication with missing/failed gates before
the patch. Negative paths assert zero tag/draft mutations, while late changes
assert that a partial draft stays unpublished. Existing mechanics, human approval,
native-token, protected-file, manifest/upload and immutability regressions remain.
Local and shared CI evidence must be reported separately from pilot adoption,
live publication, product security and production approval.
