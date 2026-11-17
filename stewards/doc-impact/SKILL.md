---
name: aardex-doc-impact
description: Analyse the documentation impact of an AARDEX pull request or local diff, route each impact to its authoritative source (component repository, AardexTechnicalDocumentation, Confluence or QMS) and prepare reviewable documentation patches. Use when asked for documentation impact, doc review, "which docs must change" or a documentation patch for a change.
---

# AARDEX documentation impact

Advisory assistance for EN-46/EN-48/EN-49. You help a developer keep documentation
correct; you never approve, gate or publish. Humans review every patch.

## Inputs

One of:
- a PR (`owner/repo#N` or URL): `gh pr view N -R owner/repo` and `gh pr diff N -R owner/repo`;
- the local working branch: `git diff <base>...HEAD` plus uncommitted changes (`git diff HEAD`).

If the PR is not checked out locally, read the repository files you need with
`gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha> -H 'Accept: application/vnd.github.raw'`.

## Governance context (advisory, read; do not restate)

The routing rules live in `aardex/AardexTechnicalDocumentation`. They are a draft
for team validation: use them as context, not as enforcement. Read them from a
local clone if one exists, otherwise with `gh api ... -H 'Accept: application/vnd.github.raw'`:

- `documentation/documentation-policy.md` — authority, representation and routing rules;
- `documentation/documentation-map.yaml` — `decision_order`, `domains`, `maintenance_modes`;
- `documentation/recovery/inventory.yaml` — known state and accepted gaps per repository
  (do not re-report a gap the inventory already records; say it is known);
- `standards/release-and-documentation-standard.md` — the PR "Documentation impact" declaration.

When a rule there conflicts with this file, the governance document wins.

## Procedure

1. **Understand the change.** Read the whole diff, then the touched code paths enough to
   know what behaviour, contract, configuration, infrastructure, deployment, security,
   operations or troubleshooting actually changed. Ignore pure refactors, tests and
   formatting unless they change a documented behaviour.
2. **Inventory the documentation.** Find the repository's documentation entry points
   (README, `docs/`, `documentation/`, ADRs, CHANGELOG, generated references such as
   terraform-docs) and grep them for the identifiers, settings, endpoints, resources and
   commands the diff touches. Stale text that the diff makes wrong is a confirmed impact.
3. **Route each impact** with the map's `decision_order` (controlled → component
   version-specific → component ADR → cross-project normative → human narrative →
   unresolved). Record the domain id and its maintenance mode.
4. **Classify confidence.**
   - *Confirmed*: you can point to a file and line that the diff makes wrong, an
     enumeration (list, table, inventory) that now omits what the diff adds, or a documented
     obligation (generated reference, link check) that fails. Text that never covered the
     changed detail is not made incomplete by the change; at most it is *uncertain*.
   - *Uncertain*: plausible impact that needs a human to confirm (intent, audience,
     ownership, controlled scope). Say what would confirm or dismiss it.
   Do not inflate: "no meaningful documentation impact" is a valid, common result.
5. **Act by authority.**
   - *Component repository, this repo:* edit the existing document in the working branch.
     Prefer updating existing text over new files; keep the repository's style; regenerate
     generated references with the repository's own tool when available. Do not commit or
     push unless the user asks.
   - *Another repository you can access* (e.g. `AardexTechnicalDocumentation` for a
     cross-project ADR, C4 model or standard): prepare the patch on a new branch in a local
     clone of that repository and show the diff. Open a draft PR only when the user asks.
   - *Confluence:* do not edit. Give the page (id/title from the inventory when known), the
     section, and the proposed wording for the responsible owner to review.
   - *Controlled/QMS documentation:* do not draft or edit content. Report the potential
     impact, why, and that the applicable controlled process/owner decides.
   - *Unresolved route:* mark it for human review; never invent an authoritative location
     or create a second copy because it is easier to edit.
6. **Verify your patch.** Run the repository's existing documentation checks when they
   exist (link checkers, terraform-docs, markdown tests, consumer checks) and
   `git diff --check`. Report what you ran and the result.

## Report

Use this structure (Markdown). Keep it short; omit empty sections.

```markdown
<!-- aardex-doc-impact -->
## Documentation impact — <repo>#<pr or branch> @ <short sha>

**Declaration (standard):** none | repository documentation | cross-project / Confluence documentation | controlled documentation

### Confirmed impacts
| Impact | Authority (map domain) | Location | Action taken / proposed |

### Uncertain — needs human confirmation
| Possible impact | Why uncertain | Who can confirm |

### Cross-project routing
- <authority>: <what> — patch branch / draft PR / Confluence suggestion / QMS owner notification

### Checks run
- <command> — <result>

_Advisory AI analysis (aardex-doc-impact). Not a deterministic check, approval or release gate._
```

## Posting to the PR (optional, only when the user asks)

Save the report to a file whose first line is the marker, then create or update the single
marked comment with the user's own `gh` credentials:

```bash
REPO=owner/repo PR=123 FILE=doc-impact.md MARKER='<!-- aardex-doc-impact -->'
ID=$(gh api "repos/$REPO/issues/$PR/comments" --paginate --jq ".[] | select(.body | contains(\"$MARKER\")) | .id" | tail -n1)
if [ -n "$ID" ]; then gh api -X PATCH "repos/$REPO/issues/comments/$ID" -F body=@"$FILE"
else gh api "repos/$REPO/issues/$PR/comments" -F body=@"$FILE"; fi
```

## Never

- Change code, tests, CI, release files (`version.txt`, `CHANGELOG.md` release sections,
  `.release/*`), approvals or another person's branch.
- Publish to Confluence or any controlled/QMS system.
- Present an inferred route or AI judgement as a deterministic result.
- Add mandatory checks, labels or gates.
