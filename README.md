# 社内問い合わせチケットポータル

Redmine をチケット基盤として利用する、社内問い合わせ向けの Web ポータルです。営業担当者は問い合わせの作成・確認、サポート担当者は受付・回答・ステータス更新を、Redmine の画面を直接操作せずに行えます。

## 主な機能

- Redmine アカウントによるログイン
- チケットの一覧・ステータス絞り込み・ページネーション・手動更新
- 問い合わせ・報告書・客先同行トラッカーを選択したチケット作成、コメント追加、ステータス／優先度変更
- 回答者向けキューと「自分が対応する」操作
- 回答者向けキューでの現在／前回対応者表示
- コメントと項目変更をまとめた監査ログ
- Redmine Wikiを利用したFAQの検索・表示と、サポート担当者／管理者向けCRUD
- Redis を利用した6時間のサーバーサイドセッション
- OpenTelemetry Collector sidecarとGrafana Alloy gatewayによるログ・トレース転送

## 構成

| コンポーネント | 技術 | ローカル URL |
|---|---|---|
| Frontend | React 19 / TypeScript / Vite / nginx | http://localhost:3001 |
| Backend | Python 3.12 / FastAPI | http://localhost:8000 |
| Redmine | Redmine 6.1 | http://localhost:3000 |
| Session store | Redis 7.4 | コンテナ内部のみ |
| Database | PostgreSQL 15 | コンテナ内部のみ |
| Telemetry gateway | Grafana Alloy | http://localhost:12345 |

## クイックスタート

前提として Docker と Docker Compose v2 が必要です。

```bash
cp .env.example .env
# .env の REDMINE_SECRET_KEY_BASE を安全なランダム値へ変更
./scripts/init.sh
```

初期化スクリプトは、問い合わせ・報告書・客先同行の3トラッカーと必要なRedmine管理リソースを準備します。通常初期化は非破壊です。旧要否フィールドの廃止は[明示的なメンテナンス手順](docs/redmine.md#初期化)だけで実行します。起動後は http://localhost:3001 を開き、Redmine アカウントでログインします。

## 開発と検証

```bash
# Python 依存関係
make deps

# バックエンドテスト
make test

# フロントエンドテスト
cd frontend
npm ci
npm test

# フロントエンド型チェックと本番ビルド
npm run build

# 観点別E2E（Docker Compose 一式の起動が必要）
make e2e-focused

# FAQの初期データ・権限・CRUDだけを確認
make e2e-faq

# 大きな変更時のフルリグレッション
make regression
```

ブラウザーE2Eには Playwright、API結合テストには [runn](https://github.com/k1LoW/runn) を利用します。準備、観点別コマンド、フルリグレッションの適用基準は [テストガイド](docs/testing.md) を参照してください。

## Kubernetes / Helmfile

既存の Docker Compose に加えて、Helmfile で `int` / `dev` / `stg` / `prd` を切り替えて Kubernetes へデプロイできます。環境ごとに Namespace、環境変数、イメージタグ、`<namespace>-<env>-<feature>.<domain>` 形式の Traefik Ingress host が切り替わります。既定の Portal URL は `support-ticket-portal-int-portal.localhost` の形式です。int/dev/stg では環境専用テストユーザーによる E2E も実行できます。

PortalとRedmineのIngressは常時作成され、intのRedmineは`support-ticket-portal-int-redmine.localhost`から手動操作できます。

環境別valuesの`traefik.install`により、環境専用Traefikをアプリと一緒に導入・破棄するか、既存Ingress Controllerを利用するか選択できます。

```bash
cp deploy/env/int.env.example deploy/env/int.env
# deploy/env/int.env のシークレットを設定
./scripts/helmfile-deploy.sh int info
./scripts/helmfile-deploy.sh int sync
./scripts/helmfile-e2e.sh int
# custom Namespaceを最初の配置先にする例と、inactive slotの直接E2E
./scripts/helmfile-deploy.sh int sync team-space
./scripts/helmfile-e2e.sh int --namespace team-space --slot green
```

custom Namespaceは同じenvironmentの並行コピーを作るためには使えません。クラスタ前提、イメージ、DNS/TLS、StorageClass、Blue-Green運用、バックアップ、運用上の確認事項は [Helmfile デプロイガイド](docs/helmfile.md) を参照してください。

## 設定

主要な環境変数は次のとおりです。全項目は [.env.example](.env.example) を参照してください。

| 変数 | 用途 |
|---|---|
| `REDMINE_API_KEY` | 起動時のステータス・メンバー情報取得に使う管理用 API キー |
| `REDMINE_PROJECT_ID` | 対象 Redmine プロジェクト |
| `REDMINE_SECRET_KEY_BASE` | Redmine の暗号化用シークレット |
| `SESSION_COOKIE_SECURE` | HTTPS 環境では `true` |
| `ENABLE_TEST_USERS` | ローカル検証ユーザーを作る場合のみ `true` |

各利用者のチケット操作には、ログイン時に Redmine から取得した利用者自身の API キーを使います。API キーは Redis に保存され、ブラウザーには `HttpOnly` Cookie のみが渡されます。

## ドキュメント

- [ドキュメント索引](docs/index.md)
- [Backend API 仕様（INPUT / OUTPUT）](docs/api.md)
- [セットアップガイド](docs/setup.md)
- [アーキテクチャ](docs/architecture.md)
- [Redmine 設定とワークフロー](docs/redmine.md)
- [テストガイド](docs/testing.md)
- [Helmfile デプロイガイド](docs/helmfile.md)
- [MVP スコープ](docs/scope.md)
- [変更履歴](docs/changelog.md)

## ライセンス

[LICENSE](LICENSE) を参照してください。
