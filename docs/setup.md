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

## uv パッケージ管理

本プロジェクトは [uv](https://github.com/astral-sh/uv) を使用してパッケージを管理しています。

### 初期設定

```bash
# 依存パッケージをインストール
make deps
# または
uv sync
```

### テスト実行

```bash
# ユニットテスト実行（カバレッジ付き）
make test
# または
uv run pytest tests/ --tb=short
```

### バックエンド開発サーバー

```bash
make run
# または
uv run uvicorn src.backend.app:app --reload --host 0.0.0.0 --port 8000
```

### テスト依存パッケージの追加

pyproject.toml の `[dependency-groups]` セクションに追記：

```toml
[dependency-groups]
test = [
    "pytest>=8.0",
    "your-package>=1.0",
]
```

その後 `uv sync --frozen` で反映。

### Docker ビルド

Dockerfile が uv を使用するように更新済みです：
- 依存パッケージの解凍が pip より高速
- lock file による再現性確保（将来 uv.lock を追跡可能）
# 認証・セッション設定

Frontend は Backend の認証 API を経由して Redmine にログインします。Redmine の
REST API が有効で、ユーザーごとの API キーが利用可能である必要があります。
Backend は Redmine から得た API キーを Redis に6時間保存し、ブラウザーには
`HttpOnly` のセッション Cookie だけを返します。

ローカル起動時は次の手順を使用します。

1. `.env.example` を `.env` にコピーし、必要な値を設定します。
2. `docker compose up --build` を実行します。
3. `http://localhost:3001` を開き、Redmine アカウントでログインします。

本番では `SESSION_COOKIE_SECURE=true` を必須とし、Redmine への接続 URL には
HTTPS を使用してください。Frontend と Backend を別 Origin で公開する場合は、
Backend の `CORS_ORIGINS` に許可する Origin をカンマ区切りで設定します。

## ローカル検証アカウント

検証専用の管理者・サポート・営業ユーザーは、`.env` で
`ENABLE_TEST_USERS=true` を明示した場合だけ初期化処理で作成されます。各
`TEST_*_USERNAME`、`TEST_*_PASSWORD`、`TEST_*_EMAIL` はすべて設定してください。
認証情報はソースやログには出力されません。作成されたユーザーには初回ログイン時の
パスワード変更が要求されます。本番環境では `ENABLE_TEST_USERS=false` のままにします。

## 追加環境変数

| 変数 | 既定値 | 用途 |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | セッション Redis |
| `SESSION_COOKIE_NAME` | `session_id` | Cookie 名 |
| `SESSION_COOKIE_SECURE` | `true` | HTTPS 限定 Cookie |
| `CORS_ORIGINS` | `http://localhost:3001` | Cookie を許可する Origin |
| `ENABLE_TEST_USERS` | `false` | 検証ユーザー作成の明示スイッチ |
