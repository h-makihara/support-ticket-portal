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
  sync|tracker-migration|diff|template|destroy) ;;
  *) echo "unsupported action: $ACTION" >&2; exit 2 ;;
esac

portal_load_secret_env
portal_require_deploy_secrets
unset PORTAL_BLUE_GREEN_PHASE
PORTAL_TRACKER_MIGRATION=false
export PORTAL_TRACKER_MIGRATION

portal_release_conflict_messages() {
  local release inventory namespaces namespace found=1

  for release in "$PORTAL_RELEASE" "$PORTAL_TRAEFIK_RELEASE"; do
    if ! inventory="$(helm list --all-namespaces --filter "^${release}$" --output json 2>&1)"; then
      echo "failed to inspect Helm releases for $release: $inventory" >&2
      return 2
    fi
    if ! namespaces="$(python3 -c '
import json
import sys

items = json.load(sys.stdin)
if not isinstance(items, list):
    raise ValueError("Helm release inventory must be a JSON list")
for item in items:
    if not isinstance(item, dict):
        raise ValueError("Helm release inventory items must be JSON objects")
    namespace = item.get("namespace")
    if isinstance(namespace, str):
        print(namespace)
' <<<"$inventory" 2>&1)"; then
      echo "failed to parse Helm release inventory for $release: $namespaces" >&2
      return 2
    fi
    while IFS= read -r namespace; do
      if [[ -n "$namespace" && "$namespace" != "$PORTAL_NAMESPACE" ]]; then
        printf '%s already exists in namespace %s; this command relocates one environment and does not create parallel copies\n' "$release" "$namespace"
        found=0
      fi
    done <<<"$namespaces"
  done

  return "$found"
}

if [[ "$ACTION" == sync || "$ACTION" == tracker-migration || "$ACTION" == diff ]]; then
  if conflict_messages="$(portal_release_conflict_messages)"; then
    if [[ "$ACTION" == sync || "$ACTION" == tracker-migration ]]; then
      echo "$conflict_messages" >&2
      exit 1
    fi
    echo "warning: $conflict_messages" >&2
  else
    preflight_status=$?
    if [[ "$preflight_status" -ne 1 ]]; then
      exit "$preflight_status"
    fi
  fi
fi

cd "$ROOT_DIR"

portal_scale_writers_to_zero() {
  local instance_selector pod_selector deployments deployment deployment_name pods pod
  local backend_found=false frontend_found=false redmine_found=false
  local -a writer_deployments=()

  instance_selector="app.kubernetes.io/instance=$PORTAL_RELEASE"
  pod_selector="$instance_selector,app.kubernetes.io/name in (backend,frontend,redmine)"
  deployments="$(kubectl -n "$PORTAL_NAMESPACE" get deployment --selector="$instance_selector" -o name)" || return
  while IFS= read -r deployment; do
    deployment_name="${deployment##*/}"
    case "$deployment_name" in
      backend|backend-blue|backend-green)
        backend_found=true
        writer_deployments+=("$deployment")
        ;;
      frontend|frontend-blue|frontend-green)
        frontend_found=true
        writer_deployments+=("$deployment")
        ;;
      redmine)
        redmine_found=true
        writer_deployments+=("$deployment")
        ;;
    esac
  done <<<"$deployments"
  if [[ "$backend_found" != true || "$frontend_found" != true || "$redmine_found" != true ]]; then
    echo "failed to find backend, frontend, and Redmine Deployments for $PORTAL_RELEASE" >&2
    return 1
  fi

  kubectl -n "$PORTAL_NAMESPACE" scale "${writer_deployments[@]}" --replicas=0 || return
  pods="$(kubectl -n "$PORTAL_NAMESPACE" get pod --selector="$pod_selector" -o name)" || return
  while IFS= read -r pod; do
    [[ -z "$pod" ]] || kubectl -n "$PORTAL_NAMESPACE" wait --for=delete "$pod" --timeout=120s || return
  done <<<"$pods"
}

if [[ "$ACTION" == tracker-migration ]]; then
  tracker_migration_in_progress=true
  leave_tracker_migration_safe() {
    local status=$?
    trap - EXIT
    if [[ "$tracker_migration_in_progress" == true ]]; then
      echo "tracker migration did not restore service; enforcing zero-replica maintenance state" >&2
      portal_scale_writers_to_zero || echo "warning: failed to verify zero-replica maintenance state" >&2
    fi
    exit "$status"
  }
  trap leave_tracker_migration_safe EXIT

  portal_scale_writers_to_zero
  PORTAL_BLUE_GREEN_PHASE=active
  PORTAL_TRACKER_MIGRATION=true
  export PORTAL_BLUE_GREEN_PHASE PORTAL_TRACKER_MIGRATION
  helmfile --environment "$PORTAL_ENVIRONMENT" sync

  PORTAL_TRACKER_MIGRATION=false
  export PORTAL_TRACKER_MIGRATION
  helmfile --environment "$PORTAL_ENVIRONMENT" sync

  tracker_migration_in_progress=false
  trap - EXIT
  echo "Tracker migration completed and normal service was restored"
  exit 0
fi

if [[ "$ACTION" == sync ]]; then
  if legacy_deployments="$(kubectl -n "$PORTAL_NAMESPACE" get deployment backend frontend -o name --ignore-not-found 2>&1)"; then
    kubectl_status=0
  else
    kubectl_status=$?
  fi
  if [[ "$kubectl_status" -ne 0 ]]; then
    echo "failed to inspect legacy Deployments in namespace $PORTAL_NAMESPACE: $legacy_deployments" >&2
    exit 1
  fi

  legacy_backend=false
  legacy_frontend=false
  while IFS= read -r deployment; do
    case "$deployment" in
      deployment/backend|deployment.apps/backend) legacy_backend=true ;;
      deployment/frontend|deployment.apps/frontend) legacy_frontend=true ;;
      '') ;;
      *)
        echo "unexpected legacy Deployment response in namespace $PORTAL_NAMESPACE: $deployment" >&2
        exit 1
        ;;
    esac
  done <<<"$legacy_deployments"

  if [[ "$legacy_backend" == true || "$legacy_frontend" == true ]]; then
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
