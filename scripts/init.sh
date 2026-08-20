#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

REDMINE_URL="${REDMINE_URL:-http://localhost:3000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin}"
TRACKER_MIGRATION=false

case "${1:-}" in
  "") ;;
  --tracker-migration) TRACKER_MIGRATION=true ;;
  *) echo "usage: $0 [--tracker-migration]" >&2; exit 2 ;;
esac
if [[ "$#" -gt 1 ]]; then
  echo "usage: $0 [--tracker-migration]" >&2
  exit 2
fi

tracker_migration_in_progress=false
leave_tracker_migration_safe() {
  local status=$?
  trap - EXIT
  if [[ "$tracker_migration_in_progress" == true ]]; then
    echo "tracker migration did not restore service; enforcing write-freeze state" >&2
    if ! docker compose stop frontend backend redmine; then
      echo "warning: failed to enforce Compose write-freeze state" >&2
    fi
  fi
  exit "$status"
}

echo "============================================================"
echo "  Redmine Ticket Portal — 初期化スクリプト"
echo "============================================================"
echo ""
echo "  Environment:"
echo "    REDMINE_URL=${REDMINE_URL}"
echo "    ADMIN_USER=${ADMIN_USER}"
echo ""

# ── 1. Redmine を起動 ──────────────────────────────────────────────
if [[ "$TRACKER_MIGRATION" == true ]]; then
  tracker_migration_in_progress=true
  trap leave_tracker_migration_safe EXIT
  echo "[Maintenance] Stopping portal and Redmine writers ..."
  docker compose stop frontend backend redmine
  docker compose up -d --wait postgres
  docker compose run --rm --no-deps \
    -e RETIRE_LEGACY_REQUEST_FIELDS=true redmine \
    bundle exec rails runner /usr/src/redmine/bootstrap_redmine.rb
fi

echo "[Step 1] Starting and bootstrapping Redmine ..."
docker compose up -d --wait postgres redmine
docker compose exec -T -e RETIRE_LEGACY_REQUEST_FIELDS=false redmine \
  bundle exec rails runner /usr/src/redmine/bootstrap_redmine.rb

# ── 2. Python 初期化スクリプトを実行 ───────────────────────────────
echo "[Step 2] Running Redmine setup via init_redmine.py ..."
export REDMINE_URL ADMIN_USER ADMIN_PASS
python3 scripts/init_redmine.py

# ── 3. Backend & Frontend を起動 ──────────────────────────────────
echo "[Step 3] Starting backend and frontend ..."
# init_redmine.py may have replaced the .env values and bootstrapped statuses
# after an already-running backend populated its in-memory cache. Recreate the
# backend so it always starts with the freshly initialized Redmine data.
docker compose up -d --force-recreate backend frontend

if [[ "$TRACKER_MIGRATION" == true ]]; then
  tracker_migration_in_progress=false
  trap - EXIT
fi

echo ""
echo "============================================================"
echo "  ✅ 全ステップ完了！"
echo "============================================================"
echo ""
echo "  Access URLs:"
echo "    Redmine      : http://localhost:3000   (admin/admin)"
echo "    Frontend     : http://localhost:3001"
echo "    Backend API  : http://localhost:8000/docs"
echo ""
echo "  Commands:"
echo "    docker compose ps          # サービスの状態確認"
echo "    docker logs ticket_backend # バックエンドログ"
echo "    runn tests/init_test.yaml  # 動作テスト実行"
