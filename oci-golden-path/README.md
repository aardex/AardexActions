# OCI release golden path (EN-45 / INFRA-396)

Two reusable workflows turn a container release into: **build once → publish an immutable digest → promote that
same digest through Alpha, Beta and Prod → roll back to a retained digest**. They complement the
[release-management](../release-management/README.md) source release (EN-41/43/44); they add no new policy engine.

| Workflow | Does | Never does |
| --- | --- | --- |
| [`oci-publish.yml`](../.github/workflows/oci-publish.yml) | Builds one exact SHA, pushes `<registry>/<image>:<version>-<sha12>` to the shared registry, labels it with `org.opencontainers.image.revision/source`, locks the digest against delete/overwrite, optionally scans it, returns `image-ref` and EN-44 `manifest-data`. A rerun for the same SHA reuses the existing digest. | Deploy, push `latest`, inject environment configuration, rebuild an existing source |
| [`oci-promote-containerapp.yml`](../.github/workflows/oci-promote-containerapp.yml) | In one GitHub Environment: checks the reference is `shared-registry/repo@sha256:…`, the digest exists and carries a source revision (optionally an expected SHA), optionally proves the run was approved for that environment, updates each Container App, waits for a healthy revision, writes a promotion record (approvers, previous and new revision/image). | Build, accept tags, change registry/identity configuration, skip the environment's protection rules |

## Contracts

- **Immutable artifact**: deploy only `registry/repo@sha256:<digest>`. Tags are informational and never reused.
- **Same bytes everywhere**: environment settings come from Container App environment variables, App
  Configuration and Key Vault — not from the image. `update-config.py`-style config injection is not supported here.
- **Approval stays human**: configure *required reviewers* on the `prod` GitHub Environment and call promote with
  `require-approval: true`. If GitHub has no approval for this run and environment, promotion fails before any
  change (EN-45: missing approval cannot silently deploy). The approver logins go into the promotion record.
- **Traceability**: source SHA (image label) → digest → environment → approvers → run URL → previous/new revision
  in the job summary and the `oci-promotion-<env>-<attempt>` artifact (90 days). GitHub also records each
  environment deployment.
- **Rollback**: rerun promote for the environment with `image-ref` set to the previous image from the promotion
  record. Published digests are locked and the shared registry has no untagged-manifest retention, so they stay
  available.
- **Registry access is Terraform-owned**: each Container App must already list the shared registry with a pull
  identity that has `AcrPull` (`context_environment.shared_container_registry`). Promote checks this for every app
  before changing any of them.

## Consumer setup

1. Workload Terraform: grant the app identity `AcrPull` on `module.context_environment.shared_container_registry.id`
   and set the registry server to its `login_server` (see the MemsMobile.Backend adoption PR).
2. GitHub: `OP_CONNECT_TOKEN` secret (existing); environment variables `OP_ADMIN_VAULT_NAME`, `AZ_APPR`,
   `AZ_SUBSCRIPTION_ID`, `AZ_RG`, `AZ_ENV` (existing); required reviewers on `prod` (**administrator action**).
3. Copy [examples/image-release.yml](examples/image-release.yml), replace `REVIEWED_MERGED_SHA` with the merged
   AardexActions commit, set image/Dockerfile/app names. The caller must grant `actions: read` (approval proof).

### With release-management (EN-44 manifest)

Build at the approved release SHA, then attach the digest to the immutable release record:

```yaml
  resolve:   # release-management command: resolve -> outputs.sha
  image:
    needs: resolve
    uses: aardex/AardexActions/.github/workflows/oci-publish.yml@REVIEWED_MERGED_SHA
    with: { image-name: example-api, source-ref: '${{ needs.resolve.outputs.sha }}', version: '...' }
  publish:   # release-management command: publish
    #   manifest-data: ${{ needs.image.outputs.manifest-data }}
```

Promotion can then pass `expected-source-sha` = the release tag SHA so a digest from another source is rejected.
Repositories not yet on release-management use the same workflows without the manifest step.

## Network and identity

Defaults run on the `aardex` runner group (GitHub-hosted runners with Azure private networking), which resolves the
shared registry through its private endpoint once `TerraformConnectivity` links `privatelink.azurecr.io` to the
runner VNet. Override `runs-on` (JSON) only while public registry access is still enabled. The existing GitHub
automation principal (`AZ_APPR`) is the only identity with `AcrPush`; runtime identities are pull-only.

## Limits

- Single-platform images (default `linux/amd64`); provenance attestations and SBOM generation are not produced by
  this workflow (manifest `sbom`/`provenance` stay `missing` unless a consumer declares them).
- The delete/overwrite lock is best effort; the summary shows whether it applied.
- `vulnerability-gate` defaults to `report` to keep current consumer behaviour; set `block` to enforce.
- Container Apps only. Terraform-owned images (images set by `acr_docker_image` in workload Terraform) must first
  move image ownership to promotion — see the adoption PRs.
