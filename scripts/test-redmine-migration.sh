#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/tests/redmine-migration.compose.yaml"
PROJECT_NAME="${REDMINE_MIGRATION_TEST_PROJECT:-support-ticket-portal-redmine-migration-test-$(date +%s)-$$}"

if [[ ! "$PROJECT_NAME" =~ ^support-ticket-portal-redmine-migration-test-[a-z0-9-]+$ ]]; then
  echo "refusing unsafe disposable Compose project name: $PROJECT_NAME" >&2
  exit 2
fi

cleanup() {
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down --volumes --remove-orphans
}
trap cleanup EXIT

docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --wait postgres redmine
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T redmine \
  bundle exec rails runner /usr/src/redmine/redmine_migration_test.rb
