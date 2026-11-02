# Opt-in NuGet BuildKit secret

The Docker publishing actions keep their existing `NUGET_PAT` build-argument behavior by default. Set `nuget-secret-mode: 'true'` only after the consuming Dockerfile uses a BuildKit secret with ID `nuget_pat`. In that mode, the action passes `github-token` via the runner environment and Buildx `secret-envs`, omits its legacy `NUGET_PAT` argument, and rejects a `NUGET_PAT` entry in additional build arguments. Do not pass the credential under another build argument or write it to a Docker layer.

`azure-publish-docker` and `azure-publish-dotnet-docker` expose the `digest` output. `azure-container-app-deploy` accepts `deploy-by-digest: 'true'`: it validates that digest, scans the digest reference and deploys the same reference. Existing version and `latest` tags remain published. Both options default to `false`, preserving existing callers. Consumers should change both their Dockerfile and the action input together.

The current registry cache is exported with `mode=max`. A Dockerfile must not copy the mounted secret into any filesystem snapshot or diagnostic output. Previously exported cache, historical image layers and logs are not remediated by this change. The opt-in mode requires consumer-specific build and cache inspection; the Python contract tests do not run BuildKit or contact a registry.

Run `python3 -m unittest discover -s tests -v` for local synthetic contract tests. They execute only local Bash and do not access external services.
