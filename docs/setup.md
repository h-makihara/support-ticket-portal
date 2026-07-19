# セットアップガイド

## 前提条件

| ツール | バージョン | 確認方法 |
|-------|-----------|---------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| Python | 3.12+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm / yarn | latest | `npm -v` |

## クイックスタート

```bash
# 1. リポジトリ取得
git clone <repo-url> support-ticket-portal
cd support-ticket-portal

# 2. 全自動セットアップ（Redmine起動 → 初期化 → Backend/Frontend起動）
./scripts/init.sh

# 3. テスト実行（初期化の正しさを確認）
runn tests/init_test.yaml
```

### セットアップの流れ

1. **Docker Compose サービス起動** — postgres, redmine をバックグランドで起動
2. **Redmine 待機** — Redmine がレスポンスを返すまで最大 180秒待機
3. **API Key 取得** — admin アカウントでログインし、REST API キーを取得
4. **プロジェクト作成** — 「社内問い合わせ」(internal-inquiry) を作成（既存ならスキップ）
5. **トラッカー作成** — 「問い合わせ」トラッカーを作成（既存ならスキップ）
6. **ステータス確認** — デフォルト 4 ステータス (New/In Progress/Reopened/Closed) の存在を確認
7. **ロール作成** — 「営業担当者」「サポート担当者」の2ロールを作成（既存ならスキップ）
8. **.env 生成** — API Key / プロジェクト ID を `.env` に書き出し

## 個別手順

### Redmine のみ初期化する場合

```bash
# Docker が既に動いている場合
docker compose up -d postgres redmine

# Python スクリプトのみ実行
python3 scripts/init_redmine.py
```

環境変数で設定可能：

```bash
REDMINE_URL=http://localhost:3000 \
ADMIN_USER=admin \
ADMIN_PASS=admin \
python3 scripts/init_redmine.py
```

### Backend / Frontend のみ起動する場合

```bash
docker compose up -d backend frontend tempo
```

## 動作確認

```bash
# Redmine Web UI
open http://localhost:3000
# → admin/admin でログイン

# フロントエンド（React）
open http://localhost:3001

# Backend API (Swagger UI)
open http://localhost:8000/docs
```

## トラブルシューティング

### Redmine が起動しない場合

```bash
# コンテナの状態確認
docker compose ps

# Redmine コンテナのログ確認
docker logs redmine

# PostgreSQL が動いているか確認
docker logs redmine_pg
```

### Backend API エラーの場合

```bash
# Backend ログ確認
docker logs ticket_backend

# .env に正しい設定が書かれているか確認
cat .env
```

### 初期化スクリプトのエラー

```bash
# httpx がインストールされているか確認
python3 -c "import httpx; print(httpx.__version__)"

# なければインストール
pip3 install httpx
```
