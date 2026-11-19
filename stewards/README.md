# Documentation and release assistance (stewards)

Portable AI-agent instructions for two advisory capabilities, run by developers and
release managers in their existing **Codex** or **Claude Code** environment:

| Skill | Purpose | Jira |
| --- | --- | --- |
| [`aardex-doc-impact`](doc-impact/SKILL.md) | Analyse a PR or local diff, route each documentation impact to its authority and prepare reviewable documentation patches | EN-46, EN-48, EN-49 |
| [`aardex-release-readiness`](release-readiness/SKILL.md) | Consolidate existing release evidence for a managed Release PR or published release into a four-part readiness report | EN-47 |

Both are **advisory**: no required check, gate, approval, publication or release-evidence
write. Routing rules stay in the
[Documentation Policy and Map](https://github.com/aardex/AardexTechnicalDocumentation/tree/main/documentation)
(draft governance) and the
[Release & Documentation Standard](https://github.com/aardex/AardexTechnicalDocumentation/blob/main/standards/release-and-documentation-standard.md);
release semantics stay in [release-management](../release-management/README.md). The
skills read those sources instead of restating them.

## Install (once per workstation)

Each skill is a directory with a `SKILL.md`, a format both Codex and Claude Code load.
Link the directories from a local clone of this repository so `git pull` keeps them current:

```bash
git clone https://github.com/aardex/AardexActions.git ~/src/AardexActions   # or reuse an existing clone
mkdir -p ~/.claude/skills ~/.codex/skills
for s in doc-impact release-readiness; do
  ln -sfn ~/src/AardexActions/stewards/$s ~/.claude/skills/aardex-$s   # Claude Code
  ln -sfn ~/src/AardexActions/stewards/$s ~/.codex/skills/aardex-$s    # Codex
done
```

Prerequisites: `gh` authenticated with read access to the repositories involved, Python
3.11+ for the release collector, and optionally the Atlassian integration you already use
for Jira/Confluence look-ups. No API key, service or new secret is needed.

Without installation, an agent can still follow the instructions by reading the
`SKILL.md` from GitHub; repositories that adopted the [baseline](#new-repository-baseline-en-51)
point their agents there.

## Use

In Claude Code or Codex, from the repository (or anywhere for a remote PR):

- `Use aardex-doc-impact on this branch` — analyses `main...HEAD` plus uncommitted changes
  and edits the affected repository documentation in place for your review.
- `Use aardex-doc-impact on aardex/keycloak#35` — analyses a remote PR; patches are prepared
  in a local checkout of its branch when you ask.
- `Use aardex-release-readiness on aardex/TerraformGithubRunner#35` (managed Release PR) or
  `… on aardex/keycloak tag v1.1.0`.
- Add `and post it as a PR comment` to create or update one identifiable comment
  (`<!-- aardex-doc-impact -->` / `<!-- aardex-release-readiness -->`) with your own `gh`
  credentials.

Codex non-interactive equivalent: `codex exec "Use the aardex-release-readiness skill on aardex/keycloak#29"`.
Claude Code: `claude -p "Use the aardex-release-readiness skill on aardex/keycloak#29"`.

## GitHub integration: on-demand comment, no hosted AI execution

The capability runs in the local agent and reaches GitHub through the user's `gh` session:
it reads PRs/checks/releases and, on request, upserts one marked PR comment. There is
deliberately **no** workflow that runs the analysis on GitHub-hosted runners, because every
option available today needs a credential or billing setup the organisation does not have:

| Option | Why not in V1 |
| --- | --- |
| Claude Code / Codex GitHub actions | Require a new provider API key or a personal subscription token stored as a repository secret |
| GitHub Copilot CLI in Actions | Copilot Business is available to assigned users, but CLI use in Actions needs a fine-grained PAT with Copilot permission stored as a secret; the native `GITHUB_TOKEN` cannot use Copilot |
| `@copilot` PR mention ([copilot-pr-review](../copilot-pr-review/README.md) pattern) | Only answered when the Copilot coding agent is enabled, and that agent responds by changing the PR with commits; it cannot be restricted to an advisory report |

A placeholder workflow that only posts a prompt would not perform useful analysis. If a
hosted run is wanted later, the smallest step is a `workflow_dispatch` job that runs one of
these skills with an approved credential and upserts the same marked comment; the
instructions here need no change.

## New-repository baseline (EN-51)

Shared conventions come from native mechanisms, not copies:

- **PR template** (*Documentation impact* declaration): an organisation default in
  `aardex/.github` (`.github/pull_request_template.md`). GitHub applies it to every repository
  without its own template, which only repository-specific exceptions should add.
- **Agent rules**: these skills. A repository's `AGENTS.md` keeps only its own documentation
  locations, commands and constraints, plus a one-line reference to this directory; copy
  [`baseline/AGENTS.md`](baseline/AGENTS.md) and adapt it. `CLAUDE.md` contains only
  `@AGENTS.md` (Claude Code imports it; Codex reads `AGENTS.md` natively).

Agents find the skills either through the per-user installation above or, when they are
not installed, by following the `AGENTS.md` reference and reading the `SKILL.md` from GitHub.
Do not add empty documentation files to satisfy a checklist.

## Limitations

- Quality depends on the agent model and the repository's existing documentation;
  impacts are classified *confirmed* or *uncertain* and humans decide.
- Cross-repository patches require the user's own clone and push rights; Confluence and
  QMS changes are suggestions only.
- The collector reports GitHub facts; it does not verify artifact bytes, deployments,
  SBOM or provenance (EN-45 and consumer publishers own those).
- Governance documents are drafts; their routing may change without changes here.

## Maintainer checks

```bash
python3 -m unittest discover -s stewards/tests -v
```

The tests use an in-memory GitHub API; they make no network calls.
