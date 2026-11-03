#!/usr/bin/env bash
set -euo pipefail
source "${GITHUB_ACTION_PATH}/git-auth.sh"
git push origin "HEAD:$1"
