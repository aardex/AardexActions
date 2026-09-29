# Development and validation

Work on a branch/worktree, inspect the action's `action.yml` and its README, and check all downstream `uses:` references before editing. No root project/solution/package manifest, automated unit-test suite, or general CI validation workflow is present here. `.github/workflows/example-copilot-pr-review.yml` only posts a PR comment on opened PRs. Do not treat a green PR comment job as validation of an action.

## Tooling

Composite actions run in the caller's GitHub Actions job. Shell steps need Bash; Terraform actions use `hashicorp/setup-terraform@v3` (1.13.3 for deploy/destroy/format-validate), Azure actions use Azure CLI and/or Azure deployment actions, Docker publishing uses Buildx, .NET actions use `actions/setup-dotnet` (defaults vary by action), Java deployment uses Java 11 and Gradle 8.10 by default. Python steps use `actions/setup-python@v5` with `3.x`; only actions calling `scripts/azure/update-config.py` or Docker config setup install `scripts/requirements.txt` (`requests==2.32.4`). Consult the relevant manifest for exact runner dependencies, setup order and defaults. Consumer builds and tests belong to the consumer repository; there is nothing to `dotnet build` or `terraform init` at this repo root.

For local, non-deploying checks on a proposed documentation/action change:

```sh
# Optional: PyYAML if installed; parses action definitions without running them
python3 - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path('.').glob('*/action.yml')):
    data = yaml.safe_load(path.read_text())
    assert data['runs']['using'] == 'composite', path
    print(path)
PY
bash -n github-version-update/action.sh terraform-module-directories/action.sh terraform-docs-index/action.sh
python3 - <<'PY'
from pathlib import Path
import ast
for path in Path('scripts').rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
    print(path)
PY
git diff --check
```

YAML parsing is optional and requires a locally installed YAML library (not declared in this repo); `scripts/requirements.txt` is runtime support for config injection, not a test environment. Syntax checks do not prove workflow expressions, permissions, target-side behavior or release safety. For action changes, validate the exact action/ref in an **authorized disposable consumer** workflow with fake/non-production inputs where feasible, and inspect nested `@main` dependencies; do not invoke deploy, publish, push or destroy as a routine test. No such integration harness is provided here. Update the component README and shared guide when contracts change.
