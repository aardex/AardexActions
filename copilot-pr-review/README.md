# Copilot PR Review

A reusable GitHub Action that automatically posts a pull request comment
mentioning `@copilot` and asking for a review summary.

## Why a composite action?

A **composite action** was chosen over a reusable workflow because:

- It can be embedded as a single `uses:` step inside any existing workflow,
  giving callers full control over triggers, job structure, and surrounding
  steps.
- It requires no separate `workflow_call` event and avoids the extra layer of
  indirection that reusable workflows add.
- It keeps the implementation minimal — a single `action.yml` plus
  `actions/github-script` to call the GitHub REST API.

## Purpose

When a pull request is opened or updated, this action posts a structured
`@copilot` comment asking for a concise review summary.  GitHub Copilot will
then reply in the PR conversation with a summary of the changes, their purpose,
risks, and what reviewers should focus on — without requiring any paid or
third-party AI service.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `github-token` | **yes** | — | GitHub token with `pull-requests: write` permission. |
| `prompt` | no | See below | The message posted as the PR comment. Must mention `@copilot`. |
| `avoid-duplicates` | no | `true` | When `true`, the action checks existing comments for the marker and skips posting if one is found. |
| `marker` | no | `<!-- copilot-pr-review-action -->` | Hidden HTML marker embedded in the comment body, used to detect duplicate posts. |

### Default prompt

```
@copilot
Summarize the changes introduced by this pull request for reviewers.
Include:
- purpose
- main code changes
- risks
- what reviewers should focus on
Keep it concise.
```

## Required permissions

The workflow calling this action must grant write access to pull requests:

```yaml
permissions:
  pull-requests: write
```

The `GITHUB_TOKEN` is sufficient when this permission is enabled — no PAT is
required.

## Example usage

```yaml
name: Request Copilot PR Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  pull-requests: write

jobs:
  copilot-review:
    runs-on: ubuntu-latest
    steps:
      - name: Request Copilot review summary
        uses: aardex/AardexActions/copilot-pr-review@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Custom prompt

```yaml
      - name: Request Copilot review summary
        uses: aardex/AardexActions/copilot-pr-review@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          prompt: |
            @copilot Please review this PR and highlight any security concerns.
          avoid-duplicates: 'true'
```

### Disable duplicate detection

```yaml
      - name: Request Copilot review summary
        uses: aardex/AardexActions/copilot-pr-review@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          avoid-duplicates: 'false'
```

## Limitations

### Fork pull requests

When a pull request is opened from a **fork**, GitHub restricts the
`GITHUB_TOKEN` to **read-only** permissions by default to prevent malicious
workflows from writing to the upstream repository.  As a result, the comment
cannot be posted automatically for fork PRs unless the repository owner has
explicitly enabled **"Allow GitHub Actions to create and approve pull
requests"** in the repository settings **and** the workflow uses the
`pull_request_target` trigger instead of `pull_request`.

> ⚠️ **Security warning**: Using `pull_request_target` with untrusted code from
> a fork can be dangerous.  Never check out the fork's code and run it in the
> same job that has write permissions.  See the
> [GitHub security guidance](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target)
> for details.

### Copilot availability

This action only **posts the comment**.  It does not verify that GitHub Copilot
is enabled on the repository or that Copilot will reply.  If Copilot is not
available or not configured, the comment will still be posted but no automatic
summary will be generated.

### Comment visibility

The hidden marker (`<!-- copilot-pr-review-action -->`) is embedded in the
comment body as an HTML comment.  It is invisible to human readers in the
rendered GitHub UI but can be seen in the raw Markdown source.
