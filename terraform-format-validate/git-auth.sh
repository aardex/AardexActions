#!/usr/bin/env bash
# Scope the optional token to this process and its children, never global Git config.
if [[ -n ${GH_MODULE_TOKEN:-} ]]; then
  config_index=${GIT_CONFIG_COUNT:-0}
  export "GIT_CONFIG_KEY_${config_index}=url.https://x-access-token:${GH_MODULE_TOKEN}@github.com/.insteadOf"
  export "GIT_CONFIG_VALUE_${config_index}=https://github.com/"
  export GIT_CONFIG_COUNT=$((config_index + 1))
fi
