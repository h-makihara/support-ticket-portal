#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENVIRONMENT="${1:-}"

# shellcheck source=scripts/lib/helmfile-env.sh
source "$ROOT_DIR/scripts/lib/helmfile-env.sh"
portal_select_environment "$ENVIRONMENT" false
shift

portal_load_secret_env

PORT_FORWARD_PID=""
PORT_FORWARD_LOG=""

cleanup() {
  if [[ -n "$PORT_FORWARD_PID" ]]; then
    kill "$PORT_FORWARD_PID" 2>/dev/null || true
    wait "$PORT_FORWARD_PID" 2>/dev/null || true
  fi
  if [[ -n "$PORT_FORWARD_LOG" ]]; then
    rm -f "$PORT_FORWARD_LOG"
  fi
}
trap cleanup EXIT INT TERM

if [[ -z "${E2E_BASE_URL:-}" ]]; then
  ingress_url="$PORTAL_URL"
  if curl --noproxy '*' --fail --silent --show-error --max-time 2 "$ingress_url/" >/dev/null 2>&1; then
    export E2E_BASE_URL="$ingress_url"
  else
    local_port="${E2E_PORT_FORWARD_PORT:-18080}"
    PORT_FORWARD_LOG="$(mktemp -t support-ticket-portal-e2e.XXXXXX)"
    kubectl -n "$PORTAL_NAMESPACE" port-forward service/frontend "$local_port:80" \
      >"$PORT_FORWARD_LOG" 2>&1 &
    PORT_FORWARD_PID=$!
    export E2E_BASE_URL="http://127.0.0.1:$local_port"

    ready=false
    for _ in {1..30}; do
      if ! kill -0 "$PORT_FORWARD_PID" 2>/dev/null; then
        echo "frontend port-forward exited unexpectedly:" >&2
        cat "$PORT_FORWARD_LOG" >&2
        exit 1
      fi
      if curl --noproxy '*' --fail --silent --show-error --max-time 2 "$E2E_BASE_URL/" >/dev/null 2>&1; then
        ready=true
        break
      fi
      sleep 1
    done
    if [[ "$ready" != true ]]; then
      echo "frontend port-forward did not become ready at $E2E_BASE_URL:" >&2
      cat "$PORT_FORWARD_LOG" >&2
      exit 1
    fi
    echo "Ingress is unavailable; running E2E through $E2E_BASE_URL (frontend port-forward)"
  fi
fi

export E2E_SALES_USERNAME="$PORTAL_TEST_SALES_USERNAME"
export E2E_SALES_PASSWORD="${TEST_SALES_PASSWORD:?TEST_SALES_PASSWORD is required}"
export E2E_SUPPORT_USERNAME="$PORTAL_TEST_SUPPORT_USERNAME"
export E2E_SUPPORT_PASSWORD="${TEST_SUPPORT_PASSWORD:?TEST_SUPPORT_PASSWORD is required}"

cd "$ROOT_DIR/frontend"
npx playwright test "$@"
