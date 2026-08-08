#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENVIRONMENT="${1:-}"

case "$ENVIRONMENT" in
  int|dev|stg) ;;
  *) echo "usage: $0 <int|dev|stg> [playwright arguments...]" >&2; exit 2 ;;
esac
shift

ENV_FILE="$ROOT_DIR/deploy/env/$ENVIRONMENT.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

export E2E_BASE_URL="${E2E_BASE_URL:-http://support-ticket-portal-$ENVIRONMENT-portal.localhost}"
export E2E_SALES_USERNAME="$ENVIRONMENT-sales"
export E2E_SALES_PASSWORD="${TEST_SALES_PASSWORD:?TEST_SALES_PASSWORD is required}"
export E2E_SUPPORT_USERNAME="$ENVIRONMENT-support"
export E2E_SUPPORT_PASSWORD="${TEST_SUPPORT_PASSWORD:?TEST_SUPPORT_PASSWORD is required}"

cd "$ROOT_DIR/frontend"
npx playwright test "$@"
