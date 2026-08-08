# テストガイド

## テスト方針

変更箇所に近いテストを短いフィードバック用に使い、業務フローを横断する変更ではフルリグレッションを実行します。ブラウザーE2Eは実データとしてチケットを作成するため、ローカルまたは検証専用環境で実行してください。

## Docker Composeでの前提

1. Docker Compose 一式が起動し、ポータルへ `E2E_BASE_URL`（既定値 `http://localhost:3001`）でアクセスできる。
2. `ENABLE_TEST_USERS=true` で初期化した営業担当者・サポート担当者が存在する。
3. `.env` に次の値が設定されている。
   - `TEST_SALES_USERNAME` / `TEST_SALES_PASSWORD`
   - `TEST_SUPPORT_USERNAME` / `TEST_SUPPORT_PASSWORD`
4. `frontend` で `npm ci` を実行済みで、`make e2e-install` により Chromium をインストール済みである。

CIなどで `.env` を使わない場合は、`E2E_SALES_USERNAME/PASSWORD` と `E2E_SUPPORT_USERNAME/PASSWORD` を設定します。`E2E_*` が `TEST_*` より優先されます。認証情報はレポートへ出力しません。

## Helmfile環境での前提

int/dev/stgでは、環境名から`<env>-sales`と`<env>-support`を生成し、`deploy/env/<env>.env`の対応するパスワードを使用します。ユーザー名と設定場所は次のコマンドで確認できます。

```bash
./scripts/helmfile-deploy.sh int info
```

デプロイ後は専用スクリプトから実行します。

```bash
./scripts/helmfile-e2e.sh int
./scripts/helmfile-e2e.sh stg e2e/ticket-creation.spec.ts
```

Ingressへ接続できない場合はFrontend Serviceへのport-forwardへ自動フォールバックします。共有クラスタなどURLが異なる場合は`E2E_BASE_URL`を明示します。prdではテストユーザーを作らず、このスクリプトも実行できません。

## 観点別E2E

| 変更観点 | 対象 | コマンド |
|---|---|---|
| チケット作成画面・作成API | 営業による新規作成 | `npm run e2e:creation --prefix frontend` |
| 担当引受・コメント・回答 | サポートの一連の対応 | `npm run e2e:support --prefix frontend` |
| 報告書・客先同行・優先度・再対応待ち | 対応要否の反映 | `npm run e2e:requirements --prefix frontend` |
| コメント・ステータス遷移・クローズ | クローズ処理 | `npm run e2e:closure --prefix frontend` |
| 上記の観点別E2Eすべて | フル以外のE2E | `make e2e-focused` |

各テストは固有のチケットを作成し、他のテストの実行順や既存チケットへ依存しません。失敗時のスクリーンショット、動画、トレースは `frontend/test-results/` に保存されます。

## フルリグレッション

`make e2e-full` は次の業務フローを1本のシナリオとして検証します。

1. 営業担当が新規チケットを作成する。
2. サポート担当が担当する。
3. サポート担当がコメントする。
4. サポート担当が回答する。
5. 営業担当が「報告書が必要」を反映する。
6. サポート担当が再度担当し、コメントする。
7. サポート担当が回答する。
8. 営業担当が「客先同行が必要」を反映する。
9. サポート担当が再度担当し、コメントする。
10. サポート担当が回答する。
11. 営業担当がコメントする。
12. 営業担当が「クローズ待ち」へ変更する。
13. サポート担当がコメントし、「クローズ」へ変更する。

次のいずれかに該当する大きな変更では、観点別テストだけでなく、必ず `make regression` を実行します。

- 認証、ロール、権限、セッション管理の変更
- チケット作成、担当、コメント、回答、カスタムフィールド、優先度、ステータス遷移の変更
- Backend API と Frontend の契約変更
- Redmine のステータス、ロール、ワークフロー、初期化処理の変更
- 複数画面・複数機能にまたがる変更、依存関係の大幅更新、リリース前確認

`make regression` は Backendテスト、Frontend単体テスト、Frontendビルド、フルE2Eを順に実行します。小さな表示修正などは関連する単体テストと観点別E2Eを選択できますが、影響範囲を限定できない場合はフルリグレッションとして扱います。

## API結合テスト

Redmine初期化、ページネーション、監査ログなどのAPI結合テストは、Docker Compose 一式を起動後に `runn` で実行します。シナリオは `tests/*.yaml` にあります。
