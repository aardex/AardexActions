"""Run nested composite actions offline with synthetic secrets and stubbed external services."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import uuid

root = pathlib.Path(__file__).resolve().parents[1]
secret = "synthetic_" + uuid.uuid4().hex
runner_image = os.environ.get('INFRA406_ACT_IMAGE', 'postgres:17')
if subprocess.run(['docker', 'image', 'inspect', runner_image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
 print('Required local act runner image is unavailable; set INFRA406_ACT_IMAGE to a cached image with bash and coreutils.')
 raise SystemExit(1)
with tempfile.TemporaryDirectory(prefix='infra406-act-') as directory:
 p=pathlib.Path(directory); (p/'actions').mkdir(); (p/'.github/workflows').mkdir(parents=True)
 for n in ['azure-container-app-deploy','azure-publish-dotnet-docker','azure-publish-docker']:
  shutil.copytree(root/n,p/'actions'/n)
 f=p/'actions/azure-container-app-deploy/action.yml';s=f.read_text().replace('aardex/AardexActions/azure-publish-dotnet-docker@main','./actions/azure-publish-dotnet-docker').replace('aquasecurity/trivy-action@0.35.0','./actions/fake-scan');f.write_text(s)
 f=p/'actions/azure-publish-dotnet-docker/action.yml';s=f.read_text().replace('aardex/AardexActions/azure-publish-docker@main','./actions/azure-publish-docker').replace('actions/setup-python@v5','./actions/fake-setup').replace('run: pip install -r "${{ github.action_path }}/../scripts/requirements.txt"','run: echo fixture-dependencies');f.write_text(s)
 f=p/'actions/azure-publish-docker/action.yml';s=f.read_text();start=s.index('    - name: Login to Azure\n');end=s.index('    - name: Set up QEMU\n',start);s=s[:start]+s[end:];s=s.replace('docker/setup-qemu-action@v3','./actions/fake-setup').replace('docker/setup-buildx-action@v3','./actions/fake-setup').replace('docker/build-push-action@v5','./actions/fake-build');f.write_text(s)
 for n in ('fake-setup','fake-build','fake-scan'):(p/'actions'/n).mkdir()
 (p/'actions/fake-setup/action.yml').write_text('''name: Fixture setup
outputs:
  name:
    description: Fake builder
    value: fixture-builder
runs:
  using: composite
  steps:
    - shell: bash
      run: echo fixture-setup
''')
 (p/'actions/fake-build/action.yml').write_text('''name: Fixture Buildx
inputs:
  secret-envs:
    required: false
  build-args:
    required: false
  tags:
    required: false
outputs:
  digest:
    description: Fixture digest
    value: ${{ steps.fixture.outputs.digest }}
runs:
  using: composite
  steps:
    - shell: bash
      id: fixture
      env:
        SECRET_ENVS: ${{ inputs.secret-envs }}
        BUILD_ARGS: ${{ inputs.build-args }}
        TAGS: ${{ inputs.tags }}
      run: |
        test "$SECRET_ENVS" = 'nuget_pat=NUGET_PAT_SECRET'
        test "$NUGET_PAT_SECRET" = "$FIXTURE_PAT"
        [[ "$BUILD_ARGS" == *APP_VERSION=fixture-version* ]]
        [[ "$BUILD_ARGS" != *NUGET_PAT* ]]
        [[ "$BUILD_ARGS" != *"$FIXTURE_PAT"* ]]
        [[ "$TAGS" == *fixture.azurecr.io/cdc:1.2.3* ]]
        [[ "$TAGS" == *fixture.azurecr.io/cdc:latest* ]]
        echo 'digest=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' >> "$GITHUB_OUTPUT"
''')
 (p/'actions/fake-scan/action.yml').write_text('''name: Fixture scanner
inputs:
  image-ref:
    required: true
runs:
  using: composite
  steps:
    - shell: bash
      env:
        IMAGE_REF: ${{ inputs.image-ref }}
      run: |
        printf '%s' "$IMAGE_REF" > "$GITHUB_WORKSPACE/scan.ref"
''')
 (p/'.github/workflows/test.yml').write_text('''name: nested-contract
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      FIXTURE_PAT: ${{ secrets.FIXTURE_PAT }}
    steps:
      - name: Install fake az
        shell: bash
        run: |
          mkdir -p "$GITHUB_WORKSPACE/bin"
          printf '#!/bin/bash\\nprintf "%%s\\\\n" "$@" >> "$GITHUB_WORKSPACE/az.calls"\\n' > "$GITHUB_WORKSPACE/bin/az"
          chmod +x "$GITHUB_WORKSPACE/bin/az"
          echo "$GITHUB_WORKSPACE/bin" >> "$GITHUB_PATH"
      - name: Execute nested composites
        uses: ./actions/azure-container-app-deploy
        with:
          environment: alpha
          azure-environment: alpha
          ca-name: ca-test
          image-name: cdc
          version: 1.2.3
          github-token: ${{ secrets.FIXTURE_PAT }}
          azure-credentials: fixture
          subscription-id: fixture
          acr-login-server: fixture.azurecr.io
          ca-resource-group: fixture
          build-args: APP_VERSION=fixture-version
          nuget-secret-mode: 'true'
          deploy-by-digest: 'true'
      - name: Verify digest reached scan and deployment
        shell: bash
        run: |
          ref="fixture.azurecr.io/cdc@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
          test "$(cat "$GITHUB_WORKSPACE/scan.ref")" = "$ref"
          grep -Fxq "$ref" "$GITHUB_WORKSPACE/az.calls"
          echo nested-contract-pass
''')
 subprocess.run(['git','init','-q'],cwd=p,check=True)
 subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','fixture'],cwd=p,check=True)
 env=os.environ.copy();env['FIXTURE_PAT']=secret
 cmd=['act','push','-W',str(p/'.github/workflows/test.yml'),'-j','test','-P','ubuntu-latest='+runner_image,'--network','none','--container-daemon-socket','-','--pull=false','--no-cache-server','--bind','--secret','FIXTURE_PAT']
 r=subprocess.run(cmd,cwd=p,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
 output=r.stdout.decode(errors='replace').replace(secret,'[synthetic]')
 print('Nested composite action harness exit:',r.returncode)
 if r.returncode or 'nested-contract-pass' not in output:print(output[-6500:]);raise SystemExit(1)
 print('PASS: secret-mode and ordinary argument reached Buildx stub; digest reached scan and fake az deployment')
 print('PASS: version and latest tags preserved; synthetic credential absent from captured act logs' if secret.encode() not in r.stdout else 'FAIL: synthetic credential appeared in act logs')
 if secret.encode() in r.stdout:raise SystemExit(1)
