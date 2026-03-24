# Copilot PR Review

Generates a pull request summary with GitHub Copilot CLI, then posts the result as a normal PR comment.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `github-token` | **yes** | — | GitHub token with `pull-requests: write` permission. |
| `copilot-token` | **yes** | — | Fine-grained PAT for a Copilot-licensed user with `Copilot Requests` permission. |
| `prompt` | no | `Summarize this pull request…` | Instructions passed to Copilot before PR metadata and file patches. |
| `avoid-duplicates` | no | `true` | Skip posting if the marker is already present in an existing comment. |
| `marker` | no | `<!-- copilot-pr-review-action -->` | Hidden HTML marker used to detect duplicate posts. |
| `max-files` | no | `20` | Maximum number of changed files included in the Copilot prompt. |
| `max-patch-chars` | no | `4000` | Maximum number of patch characters included per file. |
| `node-version` | no | `22` | Node.js version used to install Copilot CLI. |

## Required permissions

```yaml
permissions:
  contents: read
  pull-requests: write
```

## Required secret

Create a repository secret that stores a fine-grained personal access token for a GitHub user who:

- has an active Copilot license
- has access to the repository
- has the `Copilot Requests` permission on the token

Use that secret as the `copilot-token` input.

## Usage

```yaml
name: Request Copilot PR Review

on:
  pull_request:
    types: [opened]

permissions:
  contents: read
  pull-requests: write

jobs:
  copilot-review:
    runs-on: ubuntu-latest
    steps:
      - name: Generate and post Copilot PR summary
        uses: aardex/AardexActions/copilot-pr-review@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          copilot-token: ${{ secrets.COPILOT_PAT }}
```

Because the workflow only listens to `pull_request` with `types: [opened]`, it runs once when the pull request is created and does not rerun on later commits pushed to the same pull request.

## Limitations

- **Fork PRs**: `GITHUB_TOKEN` is read-only for fork pull requests by default. Posting the summary comment will fail unless you use a different event strategy such as `pull_request_target`, which has its own security tradeoffs.
- **Prompt size**: Large pull requests may have omitted files or truncated patches based on `max-files` and `max-patch-chars`.
- **Copilot access**: The token supplied via `copilot-token` must belong to a user who can use Copilot CLI.

## References

- https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-with-actions
- https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli
