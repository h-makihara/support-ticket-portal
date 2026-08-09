# セットアップガイド

## 前提条件

- Docker と Docker Compose v2
- 初期化スクリプトを個別実行する場合は Python 3.12+
- ローカル開発・テストを行う場合は uv 0.11.17+、Node.js 20.19+、npm 11.10+
- 結合テストを行う場合は runn

## Docker Compose で起動

```bash
cp .env.example .env
```

`.env` の `REDMINE_SECRET_KEY_BASE` を十分に長いランダム値へ変更します。初回は Redmine を起動して初期化し、その後すべてのサービスを起動します。

```bash
docker compose up -d postgres redmine
python3 scripts/init_redmine.py
docker compose up --build -d
```

`scripts/init_redmine.py` は Redmine の REST API を有効化したうえで、問い合わせプロジェクト・トラッカー・ロールを確認し、実行時に必要な ID と API キーを `.env` へ保存します。

`HTTP_PROXY` / `HTTPS_PROXY` が設定された環境にも対応しています。リモート Redmine へは環境のプロキシを利用し、`localhost` およびループバック IP への初期化通信は認証情報をプロキシへ送らず直接接続します。

一括実行する場合:

```bash
./scripts/init.sh
```

## アクセス先

| サービス | URL |
|---|---|
| ポータル | http://localhost:3001 |
| Backend API / Swagger UI | http://localhost:8000/docs |
| Backend health | http://localhost:8000/health |
| Redmine | http://localhost:3000 |
| Grafana Alloy status | http://localhost:12345 |

ポータルには Redmine アカウントでログインします。Redmine の初期管理者は初回ログイン後にパスワード変更が必要です。

Alloyの外部OTLP/HTTP転送先は `.env` の `EXTERNAL_OTLP_ENDPOINT` で指定します。既定の `.invalid` URLは設定漏れを明示するためのプレースホルダーなので、実際の可観測性基盤のベースURLへ変更してください。

## ローカル開発

```bash
uv sync
uv run uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Vite の開発サーバーは `/api` を `http://localhost:8000` へプロキシします。

## テスト

```bash
# バックエンド単体・APIテスト（カバレッジ付き）
uv run --group test pytest

# Frontend の型チェックと本番ビルド
cd frontend
npm run build
```

ブラウザーE2Eを初めて実行する場合は、ブラウザーをインストールします。

```bash
make e2e-install
```

E2Eでは `.env` の `TEST_SALES_USERNAME/PASSWORD`、`TEST_SUPPORT_USERNAME/PASSWORD`、`TEST_ADMIN_USERNAME/PASSWORD` を読み込みます。対応する `E2E_<ROLE>_USERNAME/PASSWORD` を実行環境へ設定すると、その値を優先します。検証ユーザーを作成するには `ENABLE_TEST_USERS=true` で Redmine 初期化を実行してください。

```bash
# 機能観点ごとのE2E（フルシナリオを除く）
make e2e-focused

# 業務フロー全体のE2E
make e2e-full

# Backend、Frontend、ビルド、フルE2Eを一括実行
make regression
```

詳細なテスト選択基準は [テストガイド](testing.md) を参照してください。

Docker Compose 一式が起動済みの場合:

```bash
runn
```

## セッションと Cookie

Backend はログインした利用者の Redmine API キーを Redis に6時間保存します。ブラウザーには API キーを返さず、`HttpOnly` セッション Cookie のみを設定します。

- ローカル HTTP: `SESSION_COOKIE_SECURE=false`
- 本番 HTTPS: `SESSION_COOKIE_SECURE=true`
- 別 Origin の Frontend を許可する場合: Backend の `CORS_ORIGINS` をカンマ区切りで設定

Kubernetes/Helmfile環境の構築、環境別テストユーザー、Traefik、バックアップと破棄は[Helmfileデプロイガイド](helmfile.md)を参照してください。

## 検証ユーザー

初期化時に検証ユーザーを作成する場合だけ、`.env` で `ENABLE_TEST_USERS=true` とし、すべての `TEST_*_USERNAME`、`TEST_*_PASSWORD`、`TEST_*_EMAIL` を設定します。本番環境では必ず無効のままにしてください。

## トラブルシューティング

```bash
docker compose ps
docker compose logs backend
docker compose logs redmine
docker compose logs redis
```

- Backend が起動しない: `.env` の `REDMINE_API_KEY` と `REDMINE_PROJECT_ID` を確認する。
- ログインできない: Redmine の REST API が有効で、対象ユーザーが API キーを利用できるか確認する。
- ローカルで Cookie が保存されない: `SESSION_COOKIE_SECURE=false` を確認する。
- 回答者一覧に表示されない: プロジェクトメンバーのロール名が `サポート担当者` か確認する。
