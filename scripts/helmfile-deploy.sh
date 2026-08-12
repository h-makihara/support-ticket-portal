#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENVIRONMENT="${1:-}"
ACTION="${2:-sync}"
NAMESPACE="${3:-}"

# shellcheck source=scripts/lib/helmfile-env.sh
source "$ROOT_DIR/scripts/lib/helmfile-env.sh"

if [[ "$#" -gt 3 ]]; then
  portal_usage_deploy >&2
  exit 2
fi

portal_select_environment "$ENVIRONMENT" true "$NAMESPACE"
export PORTAL_NAMESPACE

case "$ACTION" in
  info)
    portal_print_info
    exit 0
    ;;
  sync|diff|template|destroy) ;;
  *) echo "unsupported action: $ACTION" >&2; exit 2 ;;
esac

portal_load_secret_env
portal_require_deploy_secrets

portal_release_conflict_messages() {
  local release inventory namespaces namespace found=1

  for release in "$PORTAL_RELEASE" "$PORTAL_TRAEFIK_RELEASE"; do
    inventory="$(helm list --all-namespaces --all --filter "^${release}$" --output json)"
    namespaces="$(python3 -c '
import json
import sys

for item in json.load(sys.stdin):
    namespace = item.get("namespace")
    if isinstance(namespace, str):
        print(namespace)
' <<<"$inventory")"
    while IFS= read -r namespace; do
      if [[ -n "$namespace" && "$namespace" != "$PORTAL_NAMESPACE" ]]; then
        printf '%s already exists in namespace %s; this command relocates one environment and does not create parallel copies\n' "$release" "$namespace"
        found=0
      fi
    done <<<"$namespaces"
  done

  return "$found"
}

if [[ "$ACTION" == sync || "$ACTION" == diff ]]; then
  if conflict_messages="$(portal_release_conflict_messages)"; then
    if [[ "$ACTION" == sync ]]; then
      echo "$conflict_messages" >&2
      exit 1
    fi
    echo "warning: $conflict_messages" >&2
  fi
fi

cd "$ROOT_DIR"
if [[ "$ACTION" == sync ]]; then
  if kubectl -n "$PORTAL_NAMESPACE" get deployment backend frontend -o name >/dev/null 2>&1; then
    for PORTAL_BLUE_GREEN_PHASE in migration coexist active; do
      export PORTAL_BLUE_GREEN_PHASE
      helmfile --environment "$PORTAL_ENVIRONMENT" sync
    done
  else
    PORTAL_BLUE_GREEN_PHASE=active
    export PORTAL_BLUE_GREEN_PHASE
    helmfile --environment "$PORTAL_ENVIRONMENT" sync
  fi
else
  helmfile --environment "$PORTAL_ENVIRONMENT" "$ACTION"
fi
