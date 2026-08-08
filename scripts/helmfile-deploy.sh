#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENVIRONMENT="${1:-}"
ACTION="${2:-sync}"

case "$ENVIRONMENT" in
  int|dev|stg|prd) ;;
  *) echo "usage: $0 <int|dev|stg|prd> [sync|diff|template|destroy]" >&2; exit 2 ;;
esac

case "$ACTION" in
  sync|diff|template|destroy) ;;
  *) echo "unsupported action: $ACTION" >&2; exit 2 ;;
esac

ENV_FILE="$ROOT_DIR/deploy/env/$ENVIRONMENT.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE (copy deploy/env/$ENVIRONMENT.env.example first)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(REDMINE_API_KEY REDMINE_SECRET_KEY_BASE POSTGRES_PASSWORD)
if [[ "$ENVIRONMENT" != "prd" ]]; then
  required+=(TEST_ADMIN_PASSWORD TEST_SUPPORT_PASSWORD TEST_SALES_PASSWORD)
fi
for name in "${required[@]}"; do
  value="${!name:-}"
  if [[ -z "$value" || "$value" == replace-with-* ]]; then
    echo "$name must be set to a non-placeholder value in $ENV_FILE" >&2
    exit 1
  fi
done

cd "$ROOT_DIR"
helmfile --environment "$ENVIRONMENT" "$ACTION"
