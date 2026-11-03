#!/usr/bin/env bash
set -euo pipefail
source "${GITHUB_ACTION_PATH}/git-auth.sh"
case "${INIT_BACKEND:-true}" in
  true) terraform init -upgrade -input=false ;;
  false) terraform init -upgrade -input=false -backend=false ;;
  *) echo "init-backend must be true or false" >&2; exit 1 ;;
esac
