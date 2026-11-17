# OCI release: build once, promote by digest (EN-45 / INFRA-396)

Two reusable workflows turn a container release into: **build once → publish an immutable digest → promote that
same digest through Alpha, Beta and Prod → roll back to a retained digest**. They complement the
[release-management](../release-management/README.md) source release (EN-41/43/44); they add no new policy engine.

| Workflow | Does | Never does |
| --- | --- | --- |
| [`oci-publish.yml`](../.github/workflows/oci-publish.yml) | Builds one exact SHA, pushes `<registry>/<image>:<version>-<sha12>` to the shared registry, labels it with `org.opencontainers.image.revision/source`, locks the digest against delete/overwrite, optionally scans it, returns `image-ref` and EN-44 `manifest-data`. A rerun for the same SHA reuses the existing digest. | Deploy, push `latest`, inject environment configuration, rebuild an existing source |
| [`oci-promote-containerapp.yml`](../.github/workflows/oci-promote-containerapp.yml) | In one GitHub Environment: checks the reference is `shared-registry/repo@sha256:…`, the digest exists, was built from **the calling repository** (`org.opencontainers.image.source`) and carries a source revision (optionally an expected SHA), optionally proves the run was approved for that environment, updates each Container App, waits for a healthy revision, writes a promotion record (approvers, previous and new revision/image). | Build, accept tags, change registry/identity configuration, skip the environment's protection rules |

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
- **Rollback**: rerun promote with `image-ref` set to the previous shared-registry digest from the promotion record.
  Published digests are locked and the shared registry has no untagged-manifest retention, so they stay available.
  A caller that chains Alpha → Beta → Prod also re-promotes the lower environments when rolling Prod back; that is
  intended (Prod never runs a digest the lower environments do not). **First cutover only:** the previous image is
  an environment-registry tag without OCI labels, which promote rejects. Break-glass rollback is
  `az containerapp update -n <app> -g <rg> --image <previous_image from the record>`; it works because workload
  Terraform keeps the environment registry configured next to the shared one until phase 2.
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

- Single-platform images (default `linux/amd64`): the source checks read the single image config.
- **Accepted limitation — SBOM and provenance.** The release standard lists SBOM and artifact provenance as
  "where applicable", progressively added to the Release Manifest; EN-44 records them explicitly as `missing`
  by default. This workflow produces neither: BuildKit provenance/SBOM attestations would turn the digest into an
  image index and break the single-config source check, and nothing consumes them yet. Provenance today is the
  OCI `revision`/`source` labels checked at promotion plus the immutable digest in the manifest `artifacts`
  section. Adding attestations is a separate, reviewed change when a consumer (e.g. signature/attestation
  verification at deploy) exists.
- `credential-environment`: `AZ_APPR` is environment-scoped in current consumers, so callers pass an environment
  (e.g. `alpha`); the publish job then appears as an `alpha` deployment. An empty value (no environment) has not
  been exercised yet.
- The delete/overwrite lock is best effort; the summary shows whether it applied.
- `vulnerability-gate` defaults to `report` to keep current consumer behaviour; set `block` to enforce.
- Container Apps only. Terraform-owned images (images set by `acr_docker_image` in workload Terraform) must first
  move image ownership to promotion — see the adoption PRs.
