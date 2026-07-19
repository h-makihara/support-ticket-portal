以下、いただいた内容を反映した **ローカルLLM開発依頼用のMarkdown仕様書ドラフト** です。
Redmineは公式にREST APIを持ち、Issueの作成・更新・コメント追加・ステータス変更・担当者変更などはAPI経由で扱えます。API認証はBasic認証またはAPIキーに対応し、`X-Redmine-API-Key` ヘッダーも利用できます。([Redmine][1])
Redmine 6.1.x が現時点のLatest stable系で、公式リリース一覧では 6.1.2 が最新リリースとして掲載されています。([Redmine][2])

---

````markdown
# 社内問い合わせチケット管理システム 仕様書

## 1. 概要

本システムは、社内問い合わせを Redmine のチケットとして管理するための問い合わせ対応システムである。

営業担当者が問い合わせチケットを作成し、サポート担当者または技術担当者が回答する。  
問い合わせ内容、回答コメント、追加質問、クローズまでの流れを Redmine 上のチケット・コメント・ステータスとして管理する。

Redmine の画面操作は、初期設定やワークフロー定義などの管理用途に限定する。  
通常利用者は独自フロントエンドを利用し、バックエンド API 経由で Redmine API を操作する。

本システムに AI / LLM 機能は含めない。  
ローカル LLM は、本システムの実装を支援する開発エージェントとして利用するだけであり、実行時システムには組み込まない。

---

## 2. 目的

### 2.1 解決したい課題

- 社内問い合わせを Redmine チケットとして一元管理したい
- 営業担当者が問い合わせ状況を一覧で確認できるようにしたい
- サポート・技術担当者が対応すべき問い合わせを一覧で確認できるようにしたい
- 問い合わせ、回答、追加質問、クローズまでの履歴を残したい
- Redmine のワークフローを活用しつつ、通常利用者には専用 UI を提供したい
- グループ、ロール、可視化範囲を設定し、問い合わせの参照範囲を制御したい

### 2.2 想定利用者

| 利用者 | 役割 |
|---|---|
| 営業担当者 | 問い合わせチケットを作成する。回答を確認する。追加質問を行う。納得したらクローズする。 |
| サポート担当者 | 問い合わせを確認し、回答コメントを追加する。必要に応じて担当者を変更する。 |
| 技術担当者 | サポート担当者からアサインされた技術的な問い合わせに回答する。 |
| 管理者 | Redmine のプロジェクト、トラッカー、ステータス、ワークフロー、ロール、グループを設定する。 |

---

## 3. スコープ

## 3.1 MVPで実装する範囲

MVPでは、以下の正常系を実現する。

1. 営業担当者が問い合わせチケットを作成する
2. 回答者が未回答・回答待ちのチケット一覧を確認する
3. 回答者がチケットに回答コメントを追加する
4. 回答者がステータスを変更し、営業担当者に確認を戻す
5. 営業担当者が回答を確認する
6. 営業担当者が追加質問コメントを追加する
7. 回答者が追加質問に回答する
8. 営業担当者が納得したらチケットをクローズする
9. チケット作成からクローズまでの履歴を監査ログとして確認できる

### 3.2 MVPで実装しない範囲

以下はMVPでは対象外とする。

- LLM による問い合わせ分類
- LLM による回答生成
- LLM による要約
- 添付ファイルアップロード
- メール通知
- Teams / Slack 連携
- Redmine プラグイン開発
- 複数 Redmine インスタンス対応
- 複数プロジェクトの動的切り替え
- HTTPS 終端
- 本格的な OIDC / LDAP / AD 認証連携

---

## 4. 全体アーキテクチャ

## 4.1 構成

```text
[Browser]
   |
   | HTTP
   v
[Frontend]
   |
   | REST API
   v
[Backend API: FastAPI]
   |
   | Redmine REST API
   v
[Redmine]
   |
   v
[PostgreSQL]
````

### 4.2 コンポーネント

| コンポーネント     | 技術                        | 役割                                     |
| ----------- | ------------------------- | -------------------------------------- |
| Frontend    | React / TypeScript / Vite | 営業・回答者向け画面を提供する                        |
| Backend API | Python + FastAPI          | Frontend からの要求を受け、Redmine API を操作する    |
| Redmine     | Redmine 6.1.x 系           | チケット、コメント、ステータス、ロール、ワークフローを管理する        |
| Database    | PostgreSQL                | Redmine のデータ保存先。必要に応じてバックエンド監査ログにも利用する |
| Helm Chart  | Helm                      | Kubernetes へのデプロイを管理する                 |

---

## 5. Redmine 前提

## 5.1 Redmine バージョン

* Redmine は無料で利用可能な OSS 版を使用する
* 可能な限り最新の stable 系を利用する
* 現時点の候補は Redmine 6.1.x 系とする
* 実装時は使用する Docker image tag を明示すること

例:

```yaml
redmine:
  image:
    repository: redmine
    tag: "6.1"
```

または Bitnami Helm Chart を利用する場合は、Chart 側の対応バージョンを確認して固定する。

## 5.2 Redmine プロジェクト

MVPでは Redmine のプロジェクトは固定とする。

例:

| 項目                 | 値                  |
| ------------------ | ------------------ |
| project_id         | 環境変数で指定            |
| project_identifier | `internal-inquiry` |
| project_name       | `社内問い合わせ`          |

## 5.3 Tracker

MVPでは問い合わせ用 Tracker を1つ定義する。

| Tracker | 用途                    |
| ------- | --------------------- |
| 問い合わせ   | 営業からサポート・技術担当者への問い合わせ |

## 5.4 ステータス

MVPで利用するステータスは以下とする。

| ステータス  | 説明                     |
| ------ | ---------------------- |
| 新規     | 営業が問い合わせを作成した直後        |
| 回答待ち   | サポート・技術担当者が回答する必要がある   |
| 営業確認中  | 回答者が回答済みで、営業側の確認待ち     |
| 追加質問あり | 営業が追加質問した状態            |
| 技術確認中  | 技術担当者に確認中              |
| クローズ   | 営業が回答に納得し、問い合わせを終了した状態 |

## 5.5 ワークフロー

MVPの基本ワークフローは以下とする。

```text
新規
  ↓
回答待ち
  ↓
営業確認中
  ├─→ クローズ
  └─→ 追加質問あり
          ↓
       回答待ち
          ↓
       営業確認中
```

技術担当者へのエスカレーションが必要な場合:

```text
回答待ち
  ↓
技術確認中
  ↓
営業確認中
```

## 5.6 優先度

Redmine の Issue Priority を利用する。

MVPでは以下を想定する。

| 優先度[118;1:3u | 説明          |
| --- | ----------- |
| 低   | 急ぎではない問い合わせ |
| 通常  | 通常の問い合わせ    |
| 高   | 優先対応が必要     |
| 緊急  | 業務影響が大きい    |

## 5.7 担当者

Redmine の `assigned_to_id` を利用する。

* 営業が作成した直後はサポート窓口グループまたは代表担当者にアサインする
* サポート担当者は必要に応じて技術担当者へアサインを変更できる
* 回答後は営業確認中ステータスに変更する
* 営業が追加質問した場合は回答者側に戻す

## 5.8 グループ・ロール・可視化範囲

Redmine のグループ・ロール・メンバー設定を利用する。

MVPで想定するグループ:

| グループ      | 説明      |
| --------- | ------- |
| sales     | 営業担当者   |
| support   | サポート担当者 |
| engineers | 技術担当者   |
| admins    | 管理者     |

MVPで想定するロール:

| ロール | 権限                                   |
| --- | ------------------------------------ |
| 営業  | チケット作成、自分または参照可能なチケットの閲覧、コメント追加、クローズ |
| 回答者 | チケット閲覧、コメント追加、ステータス変更、担当者変更          |
| 管理者 | 全操作、Redmine 管理                       |

可視化範囲の制御は、MVPでは Redmine 側のプロジェクトメンバー・ロール・チケット公開範囲に依存する。
将来的には、バックエンド API 側でもユーザーの所属グループに応じたフィルタリングを追加する。

---

## 6. 認証・認可

## 6.1 MVPの認証方式

MVPでは Basic 認証またはアプリケーション用 API キー認証を採用する。

推奨MVP構成:

* Frontend は Backend API のみを呼び出す
* Frontend から Redmine API を直接呼び出さない
* Backend API が Redmine API Key を Secret から読み込む
* Redmine API Key は Kubernetes Secret に保存する
* Backend API はリクエストユーザーを簡易認証する

## 6.2 将来対応

将来的には以下のいずれかに対応する。

* LDAP 認証
* Windows AD 認証
* OIDC / Keycloak
* Ingress 側での認証
* Redmine ユーザーとの紐付け
* ユーザーごとの Redmine 権限反映

---

## 7. Backend API 仕様

## 7.1 技術スタック

* Python 3.12 以上
* FastAPI
* Pydantic
* httpx
* SQLAlchemy
* PostgreSQL driver
* pytest
* ruff
* mypy

## 7.2 Backend の責務

Backend API は以下を担当する。

* Frontend 向け REST API の提供
* Redmine API のラップ
* Redmine API Key の秘匿
* チケット作成
* チケット一覧取得
* チケット詳細取得
* コメント追加
* ステータス変更
* 担当者変更
* 優先度変更
* 監査ログ記録
* Redmine API エラーの変換
* バリデーション
* 構造化ログ出力

## 7.3 環境変数

| 環境変数                          | 必須  | 説明                         |
| ----------------------------- | --- | -------------------------- |
| `REDMINE_BASE_URL`            | yes | Redmine のベースURL            |
| `REDMINE_API_KEY`             | yes | Redmine API Key            |
| `REDMINE_PROJECT_ID`          | yes | 固定で利用する Redmine Project ID |
| `REDMINE_TRACKER_ID`          | yes | 問い合わせ Tracker ID           |
| `REDMINE_DEFAULT_PRIORITY_ID` | yes | デフォルト優先度 ID                |
| `REDMINE_DEFAULT_ASSIGNEE_ID` | no  | デフォルト担当者 ID                |
| `DATABASE_URL`                | yes | 監査ログ保存用DB接続文字列             |
| `APP_AUTH_MODE`               | yes | `basic` or `none`          |
| `APP_BASIC_USER`              | no  | Basic認証ユーザー                |
| `APP_BASIC_PASSWORD`          | no  | Basic認証パスワード               |
| `LOG_LEVEL`                   | no  | ログレベル                      |
| `HTTP_TIMEOUT_SECONDS`        | no  | Redmine API timeout        |

## 7.4 API一覧

### 7.4.1 ヘルスチェック

```http
GET /healthz
```

レスポンス:

```json
{
  "status": "ok"
}
```

### 7.4.2 readiness

```http
GET /readyz
```

確認内容:

* Backend 起動済み
* DB 接続可能
* Redmine への接続確認可能

レスポンス:

```json
{
  "status": "ready",
  "database": "ok",
  "redmine": "ok"
}
```

### 7.4.3 チケット作成

```http
POST /api/inquiries
```

リクエスト:

```json
{
  "subject": "VPN接続ができない",
  "description": "顧客環境でVPN接続に失敗しています。エラーメッセージは...",
  "priority_id": 4
}
```

Backend は Redmine API の `POST /issues.json` を呼び出す。

Redmine へ送信する例:

```json
{
  "issue": {
    "project_id": 1,
    "tracker_id": 1,
    "subject": "VPN接続ができない",
    "description": "顧客環境でVPN接続に失敗しています。エラーメッセージは...",
    "priority_id": 4,
    "status_id": 1,
    "assigned_to_id": 10
  }
}
```

レスポンス:

```json
{
  "id": 123,
  "subject": "VPN接続ができない",
  "status": {
    "id": 1,
    "name": "新規"
  },
  "priority": {
    "id": 4,
    "name": "通常"
  },
  "assigned_to": {
    "id": 10,
    "name": "Support Team"
  },
  "url": "http://redmine.example.com/issues/123"
}
```

### 7.4.4 チケット一覧取得

```http
GET /api/inquiries
```

クエリパラメータ:

| パラメータ         | 説明                                   |
| ------------- | ------------------------------------ |
| `status`      | `open`, `closed`, `*`, または status_id |
| `assigned_to` | `me` または user_id                     |
| `role_view`   | `sales` / `responder`                |
| `limit`       | 取得件数                                 |
| `offset`      | オフセット                                |

営業向け一覧:

```http
GET /api/inquiries?role_view=sales&status=*
```

回答者向け一覧:

```http
GET /api/inquiries?role_view=responder&status=open
```

レスポンス:

```json
{
  "items": [
    {
      "id": 123,
      "subject": "VPN接続ができない",
      "status": {
        "id": 2,
        "name": "回答待ち"
      },
      "priority": {
        "id": 4,
        "name": "通常"
      },
      "assigned_to": {
        "id": 10,
        "name": "Support User"
      },
      "updated_on": "2026-05-21T10:00:00Z"
    }
  ],
  "total_count": 1,
  "limit": 25,
  "offset": 0
}
```

### 7.4.5 チケット詳細取得

```http
GET /api/inquiries/{issue_id}
```

Backend は Redmine API の `GET /issues/{id}.json?include=journals` を呼び出す。

レスポンス:

```json
{
  "id": 123,
  "subject": "VPN接続ができない",
  "description": "顧客環境でVPN接続に失敗しています。",
  "status": {
    "id": 2,
    "name": "回答待ち"
  },
  "priority": {
    "id": 4,
    "name": "通常"
  },
  "assigned_to": {
    "id": 10,
    "name": "Support User"
  },
  "journals": [
    {
      "id": 1001,
      "user": {
        "id": 5,
        "name": "営業 太郎"
      },
      "notes": "追加でログを確認しました。",
      "created_on": "2026-05-21T10:10:00Z"
    }
  ]
}
```

### 7.4.6 コメント追加

```http
POST /api/inquiries/{issue_id}/comments
```

リクエスト:

```json
{
  "notes": "ログを確認したところ、認証サーバへの到達に失敗しています。"
}
```

Backend は Redmine API の `PUT /issues/{id}.json` を呼び出し、`notes` を追加する。

Redmine へ送信する例:

```json
{
  "issue": {
    "notes": "ログを確認したところ、認証サーバへの到達に失敗しています。"
  }
}
```

### 7.4.7 ステータス変更

```http
PATCH /api/inquiries/{issue_id}/status
```

リクエスト:

```json
{
  "status_id": 3,
  "notes": "回答済みのため営業確認中に変更します。"
}
```

Redmine へ送信する例:

```json
{
  "issue": {
    "status_id": 3,
    "notes": "回答済みのため営業確認中に変更します。"
  }
}
```

### 7.4.8 担当者変更

```http
PATCH /api/inquiries/{issue_id}/assignee
```

リクエスト:

```json
{
  "assigned_to_id": 20,
  "notes": "技術担当者に確認を依頼します。"
}
```

### 7.4.9 優先度変更

```http
PATCH /api/inquiries/{issue_id}/priority
```

リクエスト:

```json
{
  "priority_id": 5,
  "notes": "顧客影響が大きいため優先度を高に変更します。"
}
```

### 7.4.10 クローズ

```http
POST /api/inquiries/{issue_id}/close
```

リクエスト:

```json
{
  "notes": "回答内容で解決したためクローズします。"
}
```

Backend は Redmine API に対して、クローズ用 status_id と notes を送信する。

---

## 8. 監査ログ

## 8.1 目的

問い合わせ対応が必ずリクエストとして処理され、クローズされたことを確認できるようにする。

## 8.2 保存対象

以下の操作を監査ログに保存する。

* チケット作成
* コメント追加
* ステータス変更
* 担当者変更
* 優先度変更
* クローズ
* Redmine API エラー

## 8.3 テーブル案

### audit_logs

| カラム              | 型         | 説明                    |
| ---------------- | --------- | --------------------- |
| id               | UUID      | 監査ログID                |
| issue_id         | integer   | Redmine Issue ID      |
| action           | varchar   | 操作種別                  |
| actor            | varchar   | 操作者                   |
| request_payload  | jsonb     | Backend API へのリクエスト   |
| redmine_payload  | jsonb     | Redmine API へ送信した内容   |
| redmine_response | jsonb     | Redmine API からのレスポンス  |
| status           | varchar   | `success` / `failure` |
| error_message    | text      | エラー内容                 |
| created_at       | timestamp | 作成日時                  |

---

## 9. Frontend 仕様

## 9.1 技術スタック

* React
* TypeScript
* Vite
* React Router
* TanStack Query
* UIライブラリは任意

  * MUI
  * Chakra UI
  * shadcn/ui
  * Mantine
  * いずれかを選定する

## 9.2 画面一覧

| 画面         | パス                     | 利用者     | 説明                   |
| ---------- | ---------------------- | ------- | -------------------- |
| ログイン画面     | `/login`               | 全員      | MVPでは簡易認証            |
| 営業向けチケット一覧 | `/sales/inquiries`     | 営業      | 作成済み・参照可能な問い合わせを一覧表示 |
| 問い合わせ作成    | `/sales/inquiries/new` | 営業      | 新規問い合わせを作成           |
| チケット詳細     | `/inquiries/:id`       | 全員      | コメント履歴、ステータス、担当者を確認  |
| 回答者向け一覧    | `/responder/inquiries` | サポート・技術 | 回答が必要なチケットを一覧表示      |
| 管理補助画面     | `/admin/settings`      | 管理者     | MVPでは環境情報表示程度        |

## 9.3 営業向け機能

営業担当者は以下を行える。

* 問い合わせ作成
* 自分が作成した問い合わせ一覧の確認
* 参照可能な問い合わせ一覧の確認
* 回答コメントの確認
* 追加質問コメントの投稿
* チケットのクローズ

## 9.4 回答者向け機能

回答者は以下を行える。

* 回答待ちチケット一覧の確認
* チケット詳細の確認
* 回答コメントの投稿
* ステータス変更
* 担当者変更
* 優先度変更
* 技術担当者へのアサイン
* 営業確認中へのステータス変更

## 9.5 チケット詳細画面

表示項目:

* チケットID
* 件名
* 説明
* ステータス
* 優先度
* 担当者
* 作成者
* 作成日時
* 更新日時
* コメント履歴
* コメント入力欄
* ステータス変更欄
* 担当者変更欄
* クローズボタン

---

## 10. Kubernetes / Helm 仕様

## 10.1 対象環境

初期検証環境:

* M1 Mac
* Docker Desktop Kubernetes

最終想定環境:

* オンプレ Kubernetes

## 10.2 Namespace

例:

```yaml
namespace: inquiry-system
```

## 10.3 Helm Chart に含めるリソース

MVPでは以下を含める。

* Deployment
* Service
* Ingress
* ConfigMap
* Secret
* livenessProbe
* readinessProbe

対象コンポーネント:

* frontend
* backend
* redmine
* postgresql

## 10.4 Backend Deployment

必要な設定:

* `REDMINE_BASE_URL`
* `REDMINE_API_KEY`
* `REDMINE_PROJECT_ID`
* `REDMINE_TRACKER_ID`
* `DATABASE_URL`
* `LOG_LEVEL`

Backend は Redmine と同じ namespace に配置する。
Redmine へは Service 名でアクセスする。

例:

```text
http://redmine:3000
```

## 10.5 Frontend Deployment

Frontend は Backend API の URL を環境変数で受け取る。

例:

```env
VITE_API_BASE_URL=/api
```

Frontend は Redmine API を直接呼び出してはいけない。

## 10.6 Redmine Service

Redmine は同一 namespace 内から Backend がアクセスできるようにする。

また、管理者が Redmine の初期設定やワークフロー定義を行えるように、Ingress 経由で社内ネットワークに公開できること。

初期は HTTP でよい。
将来的に HTTPS 化する。

## 10.7 PostgreSQL

Redmine と Backend 監査ログのDBとして PostgreSQL を利用する。

MVPでは同一 PostgreSQL インスタンス内に以下を分けて作成してよい。

* `redmine` database
* `inquiry_app` database

本番では必要に応じて分離を検討する。

---

## 11. Docker / ローカル開発

## 11.1 開発用 docker-compose

ローカルLLMが実装しやすいように、Kubernetes だけでなく docker-compose も提供する。

含めるサービス:

* frontend
* backend
* redmine
* postgresql

## 11.2 起動コマンド例

```bash
docker compose up -d
```

## 11.3 初期設定

起動後、管理者は Redmine にログインし、以下を設定する。

* REST API 有効化
* プロジェクト作成
* Tracker 作成
* ステータス作成
* ワークフロー作成
* 優先度設定
* ユーザー作成
* グループ作成
* ロール作成
* API Key 発行

---

## 12. 非機能要件

## 12.1 ログ

Backend は構造化ログを出力する。

出力項目:

* timestamp
* level
* request_id
* actor
* action
* issue_id
* status
* duration_ms
* error

## 12.2 タイムアウト

Redmine API 呼び出しには timeout を設定する。

デフォルト:

```text
HTTP_TIMEOUT_SECONDS=10
```

## 12.3 リトライ

MVPでは自動リトライは必須ではない。
ただし、ネットワーク一時エラーと Redmine API エラーは区別してログに残す。

## 12.4 バリデーション

Backend は Pydantic により入力値を検証する。

検証例:

* subject は必須
* description は必須
* notes は必須
* status_id は整数
* priority_id は整数
* assigned_to_id は整数
* 空文字は禁止

## 12.5 エラーハンドリング

Redmine API からのエラーは Backend API のエラー形式に変換する。

例:

```json
{
  "error": {
    "code": "REDMINE_VALIDATION_ERROR",
    "message": "Redmine validation failed",
    "details": [
      "Subject can't be blank"
    ]
  }
}
```

## 12.6 Health Check

Backend:

* `/healthz`
* `/readyz`

Frontend:

* HTTP 200 を返せること

Redmine:

* Service 到達性を確認する

---

## 13. セキュリティ要件

## 13.1 API Key

Redmine API Key は Kubernetes Secret に保存する。

禁止事項:

* Frontend に Redmine API Key を渡さない
* Git に API Key をコミットしない
* ConfigMap に API Key を保存しない

## 13.2 Frontend から Redmine API への直接アクセス禁止

Frontend は必ず Backend API を呼び出す。

理由:

* Redmine API Key を秘匿するため
* 監査ログを Backend で記録するため
* 認可制御を Backend に集約するため
* Redmine API の仕様変更を Frontend から隠蔽するため

## 13.3 認証

MVPでは Basic 認証でよい。

将来的には以下を検討する。

* LDAP
* Windows AD
* OIDC
* Keycloak
* oauth2-proxy
* Ingress 認証

---

## 14. テスト要件

## 14.1 Backend テスト

pytest により以下をテストする。

* チケット作成 API
* チケット一覧 API
* チケット詳細 API
* コメント追加 API
* ステータス変更 API
* 担当者変更 API
* 優先度変更 API
* クローズ API
* Redmine API エラー時の変換
* 監査ログ保存
* 入力バリデーション

## 14.2 Frontend テスト

最低限、以下を確認する。

* チケット一覧が表示される
* チケット作成フォームから送信できる
* チケット詳細が表示される
* コメントを追加できる
* ステータスを変更できる
* クローズできる

## 14.3 E2E 正常系

以下のシナリオを確認する。

```text
営業が問い合わせを作成する
  ↓
回答者が回答待ち一覧で確認する
  ↓
回答者がコメントを追加する
  ↓
回答者が営業確認中に変更する
  ↓
営業が回答を確認する
  ↓
営業が追加質問を投稿する
  ↓
回答者が追加回答する
  ↓
営業がクローズする
  ↓
監査ログで一連の操作を確認できる
```

---

## 15. 成果物

ローカルLLMには以下を生成させる。

```text
.
├── backend/
│   ├── app/
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── README.md
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── Dockerfile
│   └── README.md
├── charts/
│   └── inquiry-system/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── docker-compose.yml
├── .env.example
├── README.md
└── docs/
    ├── redmine-initial-setup.md
    ├── api-spec.md
    └── workflow.md
```

## 15.1 必須成果物

* Backend API
* Frontend
* Dockerfile
* docker-compose.yml
* Helm Chart
* Kubernetes manifests generated by Helm
* README
* `.env.example`
* Redmine 初期設定手順
* API仕様書
* テストコード
* 監査ログ用DBマイグレーション

---

## 16. 実装上の重要方針

## 16.1 Redmine を業務データの正とする

チケット本文、コメント、ステータス、担当者、優先度は Redmine を正とする。

Backend 独自DBには、原則として監査ログのみ保存する。

## 16.2 Backend は Redmine API の薄いラッパーにする

Backend は業務ロジックを持ちすぎない。
Redmine のワークフロー、ロール、ステータスを活用する。

ただし、Frontend に Redmine API の詳細を露出しないため、Backend で API を抽象化する。

## 16.3 Frontend は利用者別に画面を分ける

営業向けと回答者向けで一覧画面を分ける。

* 営業: 自分が作成した問い合わせ、参照可能な問い合わせ
* 回答者: 自分または自グループが対応すべき問い合わせ

## 16.4 Redmine 初期設定はドキュメント化する

MVPでは Redmine のワークフローやロールを完全自動作成しなくてもよい。
ただし、管理者が再現できるように手順書を必ず作成する。

---

## 17. 未確定事項

以下は実装前に決める必要がある。

| 項目                  | 現在の方針                                          |
| ------------------- | ---------------------------------------------- |
| Frontend UI ライブラリ   | 未定                                             |
| 認証方式                | MVPはBasic認証、将来LDAP/AD/OIDC                     |
| Redmine Helm Chart  | 公式Docker imageベースで自作するか、Bitnami Chartを利用するか要検討 |
| Redmine DB          | PostgreSQL 推奨                                  |
| Redmine 初期設定自動化     | MVPでは手順書対応                                     |
| ユーザーとRedmineユーザーの対応 | MVPでは簡易対応                                      |
| グループ単位の厳密な参照制御      | MVPではRedmine側設定を優先                             |
| HTTPS               | 将来対応                                           |

---

## 18. MVPの完了条件

MVPは以下を満たしたら完了とする。

* Docker Desktop Kubernetes 上に Helm でデプロイできる
* Frontend にアクセスできる
* Backend API が起動する
* Redmine が起動する
* PostgreSQL が起動する
* Frontend から問い合わせを作成できる
* 作成された問い合わせが Redmine チケットとして登録される
* 回答者が一覧からチケットを確認できる
* 回答者がコメントを追加できる
* 営業がコメントを確認できる
* 営業が追加質問を投稿できる
* 回答者が追加回答できる
* 営業がチケットをクローズできる
* 一連の操作が監査ログに保存される
* README の手順だけでローカル検証環境を再現できる

```

---

補足すると、**DBはPostgreSQL推奨**でよいと思います。Redmine自体はクロスデータベース対応のWebアプリで、BitnamiのRedmine Helm ChartもMariaDB/PostgreSQLを扱う構成になっています。:contentReference[oaicite:2]{index=2}  
FastAPI側の監査ログも考えると、PostgreSQLに寄せた方が扱いやすいです。
::contentReference[oaicite:3]{index=3}
```

[1]: https://www.redmine.org/projects/redmine/wiki/rest_api?utm_source=chatgpt.com "Rest api"
[2]: https://www.redmine.org/projects/redmine/wiki/download?utm_source=chatgpt.com "Download"


## 6. Telemetry（OpenTelemetry）
本プロジェクトは **OpenTelemetry** を利用して API のリクエストとレスポンスを観測し、Grafana Alloy コレクタへ送信します。Alloy は OTLP (gRPC) エンドポイントで受け取り、[otel‑lgtm](https://github.com/grafana/otel-lgtm) で可視化します。

### 6.1 送信先構成
| コンポーネント | エンドポイント | 備考 |
| ------------- | ------------- | ----- |
| Grafana Alloy | `localhost:4317` | OTLP (gRPC) ポート 4317 を使用（環境変数 `OTEL_EXPORTER_OTLP_ENDPOINT` で上書き可） |
| otel‑lgtm | `http://otel-lgtm:3000` | Grafana Dashboards が自動で生成される |

### 6.2 環境変数
| 変数 | デフォルト | 説明 |
| ---- | ---------- | ----- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `localhost:4317` | Alloy の OTLP エンドポイント |

### 6.3 依存パッケージ
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-grpc`
- `opentelemetry-instrumentation-fastapi`

これらは `requirements.txt` に追加されています。Docker Compose で `docker-compose.yml` に `otlp-exporter` を追加し、`docker compose up -d` で起動します。
