# Copilot PR Review

Posts a `@copilot` comment on a pull request asking for a concise review summary.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `github-token` | **yes** | — | GitHub token with `pull-requests: write` permission. |
| `prompt` | no | `@copilot Summarize…` | The message posted as the PR comment. |
| `avoid-duplicates` | no | `true` | Skip posting if the marker is already present in an existing comment. |
| `marker` | no | `<!-- copilot-pr-review-action -->` | Hidden HTML marker used to detect duplicate posts. |

## Required permissions

```yaml
permissions:
  pull-requests: write
```

## Usage

```yaml
name: Request Copilot PR Review

on:
  pull_request:
    types: [opened]

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

## Limitations

- **Fork PRs**: `GITHUB_TOKEN` is read-only for fork pull requests by default. Writing a comment requires `pull_request_target` — use with caution as it runs in the base repository context.
- **Copilot availability**: The action only posts the comment; it does not verify that Copilot is enabled or will respond.
