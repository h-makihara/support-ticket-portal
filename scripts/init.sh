#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

REDMINE_URL="${REDMINE_URL:-http://localhost:3000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin}"

echo "============================================================"
echo "  Redmine Ticket Portal — 初期化スクリプト"
echo "============================================================"
echo ""
echo "  Environment:"
echo "    REDMINE_URL=${REDMINE_URL}"
echo "    ADMIN_USER=${ADMIN_USER}"
echo ""

# ── 1. Redmine を起動 ──────────────────────────────────────────────
echo "[Step 1] Starting and bootstrapping Redmine ..."
docker compose up -d --wait postgres redmine
docker compose exec -T redmine \
  bundle exec rails runner /usr/src/redmine/bootstrap_redmine.rb

# ── 2. Python 初期化スクリプトを実行 ───────────────────────────────
echo "[Step 2] Running Redmine setup via init_redmine.py ..."
export REDMINE_URL ADMIN_USER ADMIN_PASS
python3 scripts/init_redmine.py

# ── 3. Backend & Frontend を起動 ──────────────────────────────────
echo "[Step 3] Starting backend, frontend, tempo ..."
docker compose up -d backend frontend tempo

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
