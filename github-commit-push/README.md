# Git Commit and Push

The GitHub Actions for pushing local changes to GitHub using an authorized GitHub token, if provided.

## Usage

```yaml
jobs:
  versioning:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Make some changes
        uses: ...

      - name: Commit and Push
        uses: aardex/AardexActions/github-commit-push@main
        with:
          message: "Updated by Github Action"
          github-token: ${{ secrets.PAT_TOKEN }}
```