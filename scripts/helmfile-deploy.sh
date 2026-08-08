#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENVIRONMENT="${1:-}"
ACTION="${2:-sync}"

# shellcheck source=scripts/lib/helmfile-env.sh
source "$ROOT_DIR/scripts/lib/helmfile-env.sh"

portal_select_environment "$ENVIRONMENT"

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

cd "$ROOT_DIR"
helmfile --environment "$PORTAL_ENVIRONMENT" "$ACTION"
