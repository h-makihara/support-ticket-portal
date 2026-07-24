# 社内問い合わせチケットポータル

Redmine をチケット基盤として利用する、社内問い合わせ向けの Web ポータルです。営業担当者は問い合わせの作成・確認、サポート担当者は受付・回答・ステータス更新を、Redmine の画面を直接操作せずに行えます。

## 主な機能

- Redmine アカウントによるログイン
- チケットの一覧・ステータス絞り込み・ページネーション
- チケット作成、コメント追加、ステータス変更
- 回答者向けキューと「自分が対応する」操作
- コメントと項目変更をまとめた監査ログ
- Redis を利用した6時間のサーバーサイドセッション
- OpenTelemetry によるバックエンドと Redmine API 呼び出しのトレース

## 構成

| コンポーネント | 技術 | ローカル URL |
|---|---|---|
| Frontend | React 18 / TypeScript / Vite / nginx | http://localhost:3001 |
| Backend | Python 3.12 / FastAPI | http://localhost:8000 |
| Redmine | Redmine 6.1 | http://localhost:3000 |
| Session store | Redis 7.4 | コンテナ内部のみ |
| Database | PostgreSQL 15 | コンテナ内部のみ |
| Tracing | Grafana Tempo | http://localhost:3200 |

## クイックスタート

前提として Docker と Docker Compose v2 が必要です。

```bash
cp .env.example .env
# .env の REDMINE_SECRET_KEY_BASE を安全なランダム値へ変更
docker compose up -d postgres redmine
python3 scripts/init_redmine.py
docker compose up --build -d
```

初期化スクリプトが `.env` に Redmine API キー、プロジェクト ID、トラッカー IDを書き込みます。起動後は http://localhost:3001 を開き、Redmine アカウントでログインします。

一括セットアップを行う場合は、次のスクリプトも利用できます。

```bash
./scripts/init.sh
```

## 開発と検証

```bash
# Python 依存関係
make deps

# バックエンドテスト
make test

# フロントエンド型チェックと本番ビルド
cd frontend
npm ci
npm run build
```

結合テストには [runn](https://github.com/k1LoW/runn) を利用します。Docker Compose 一式が起動した状態で `runn` を実行してください。

## 設定

主要な環境変数は次のとおりです。全項目は [.env.example](.env.example) を参照してください。

| 変数 | 用途 |
|---|---|
| `REDMINE_API_KEY` | 起動時のステータス・メンバー情報取得に使う管理用 API キー |
| `REDMINE_PROJECT_ID` | 対象 Redmine プロジェクト |
| `REDMINE_TRACKER_ID` | 問い合わせトラッカー |
| `REDMINE_SECRET_KEY_BASE` | Redmine の暗号化用シークレット |
| `SESSION_COOKIE_SECURE` | HTTPS 環境では `true` |
| `ENABLE_TEST_USERS` | ローカル検証ユーザーを作る場合のみ `true` |

各利用者のチケット操作には、ログイン時に Redmine から取得した利用者自身の API キーを使います。API キーは Redis に保存され、ブラウザーには `HttpOnly` Cookie のみが渡されます。

## ドキュメント

- [セットアップガイド](docs/setup.md)
- [アーキテクチャ](docs/architecture.md)
- [Redmine 設定とワークフロー](docs/redmine.md)
- [MVP スコープ](docs/scope.md)
- [変更履歴](docs/changelog.md)

## ライセンス

[LICENSE](LICENSE) を参照してください。
