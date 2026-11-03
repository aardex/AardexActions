# Terraform Format and Validate

Formats and validates a Terraform directory. Existing defaults remain `fix: 'true'`, `auto-commit: 'auto'`, and `init-backend: 'true'`; these can modify files, push changes, and initialize a configured remote backend. Callers must choose an appropriate trust boundary.

## Inputs

- `directory` (required): Terraform directory.
- `azure-credentials` (optional): Azure service-principal JSON, needed only where the caller's backend or providers require it. Invalid or incomplete nonempty JSON fails the job.
- `github-token` (optional): GitHub credential for private modules and, when auto-commit is enabled, pushing. It is scoped to the init/push process and is not written to global Git configuration. A repository's `GITHUB_TOKEN` does not normally grant access to another private repository.
- `init-backend` (optional, default `true`): Set `false` to use `terraform init -backend=false` for backend-independent validation. Dependencies and providers are still downloaded.
- `fix` (optional, default `true`): Set `false` for `terraform fmt -check -recursive`.
- `auto-commit` (optional, default `auto`): `true` pushes changes, `false` never pushes, `auto` pushes when `fix` is `true`.
- `auto-commit-message` (optional): Commit message when auto-commit is enabled.

## Read-only validation

```yaml
permissions:
  contents: read
steps:
  - uses: actions/checkout@v4
    with:
      persist-credentials: false
  - uses: aardex/AardexActions/terraform-format-validate@<full-commit-sha>
    with:
      directory: ./iac
      fix: 'false'
      auto-commit: 'false'
      init-backend: 'false'
      # Only if private modules are required: use a dedicated read-only credential.
      github-token: ${{ secrets.TERRAFORM_MODULES_READ_TOKEN }}
```

PR code can access credentials passed to its job; scope any module credential to read-only access to the minimum repositories and treat disclosure as possible. A run with private modules fails if access is unavailable; no module-validation fallback is performed.

For trusted auto-commit callers, retain appropriate branch authorization and write credentials. If using `github-token` for pushes, avoid checkout's persisted authorization header (`persist-credentials: false`) so it does not override that credential. Branch protection can still reject a push. Test with a disposable remote before adoption.

## Safe local contract tests

`python3 -m unittest discover -s terraform-format-validate/tests -v` uses temporary local Git repositories, a synthetic credential, a provider-less Terraform fixture and a local-only provider installation configuration. It performs no deployment, backend access, or remote Git push. Terraform must be installed locally. Hosted action resolution, private module access, and protected-branch authorization need separate consumer verification.
