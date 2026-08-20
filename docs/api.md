# Backend API 仕様

## 契約と共通規約

Backend API は FastAPI が公開する JSON/REST インターフェースです。ブラウザーからは nginx の `/api` 経由、開発環境では Backend のルートから直接アクセスします。正規の機械可読仕様は実行中の `GET /openapi.json`、閲覧用UIは `/docs`（Swagger UI）と `/redoc` です。

- Content-Type: `application/json`
- 認証: ログイン後に発行される `HttpOnly` セッションCookie
- 日時: Redmineが返すISO 8601文字列
- 成功応答: 各エンドポイント固有のOUTPUTスキーマ
- エラー応答: `{ "detail": string }`
- 認証なし／期限切れ: `401`
- 入力不正: `422`、権限不足: `403`、競合: `409`
- Redmineの応答を透過する箇所では、そのHTTPステータスと本文を `detail` に格納する

入力・出力スキーマの実装は `backend/application/schemas/` に集約し、ルートの `response_model` で実レスポンスも検証します。パスパラメーター `ticket_id` は整数、`faq_id` は英数字・`_`・`-` のみです。

## 共通OUTPUT

### `DetailOutput`

```json
{ "detail": "処理結果の説明" }
```

### `PaginationOutput`

| フィールド | 型 | 意味 |
|---|---:|---|
| `limit` | integer | 1ページの最大件数 |
| `offset` | integer | 取得開始位置（0始まり） |
| `total_count` | integer | 条件一致総件数 |
| `has_more` | boolean | 後続ページの有無 |

## 認証 API

### `POST /auth/login`

INPUT `LoginInput`: `username: string`, `password: string`（必須）。空白のユーザー名または空のパスワードは `422`、認証失敗は情報漏えいを避けて一律 `401` です。

OUTPUT `AuthSessionOutput`:

```json
{
  "authenticated": true,
  "user": { "id": 7, "username": "support", "name": "Support User", "roles": ["support"] }
}
```

`roles` は `sales`、`support`、`admin` の配列です。Redmine APIキーとセッションIDはOUTPUTに含めません。

### `GET /auth/session`

INPUTなし。OUTPUTは `AuthSessionOutput`。現在のCookieが無効なら `401` です。

### `POST /auth/logout`

INPUTなし。セッションを削除してCookieを無効化します。OUTPUTは `DetailOutput`。

## チケット API

### チケットOUTPUT

`TicketOutput` のフィールドは次のとおりです。

| フィールド | 型 | 備考 |
|---|---|---|
| `id` | integer | Redmine issue ID |
| `tracker` | `"inquiry"` / `"report"` / `"customer_visit"` | トラッカーキー |
| `tracker_name` | string | 表示名（問い合わせ、報告書、客先同行） |
| `subject`, `description`, `status` | string | 基本情報 |
| `priority` | integer | Redmine優先度ID |
| `priority_name` | string | 表示名 |
| `assignee` | `{id, name}` / null | 現在の担当者 |
| `latest_support_responder` | `{id, name}` / null | 回答者一覧でのみ返す |
| `created_on`, `updated_on` | string | ISO 8601日時 |
| `customer_id` | string | 顧客ID |
| `report_delivered` | boolean / null | 報告書トラッカーでのみ `support` に返す |
| `schedule_assigned` | boolean / null | 客先同行トラッカーでのみ `support` に返す |
| `notes` | array | 詳細取得で返す互換コメント一覧 |
| `audit_log` | array | 詳細取得で返すコメント・変更履歴 |

`audit_log[].type` は `comment` / `change` / `both`。変更要素は `field`, `display_field`, `old_value`, `new_value` を持ちます。

### `POST /tickets`

INPUT `CreateTicketInput`:

| フィールド | 型 | 必須 | 既定値／規則 |
|---|---:|:---:|---|
| `tracker` | `"inquiry"` / `"report"` / `"customer_visit"` | ✓ | 問い合わせ、報告書、客先同行のいずれかを選択 |
| `subject` | string | ✓ | trim後に空不可 |
| `description` | string | ✓ | trim後に空不可 |
| `priority` | integer / null | | Redmine優先度ID |
| `customer_id` | string | | `""` |
| `report_delivered` | boolean | | `false`、報告書トラッカーでのみsupportが反映 |
| `schedule_assigned` | boolean | | `false`、客先同行トラッカーでのみsupportが反映 |

OUTPUTは `TicketOutput`。報告書と客先同行の両方を依頼する場合は、トラッカーごとに別の `POST /tickets` を実行します。

### `GET /tickets`

Query INPUT: `status?: string`, `view?: "responder"`, `limit?: integer`（1〜1000へ丸める）、`offset?: integer`（0以上へ丸める）。OUTPUTは `{ tickets: TicketOutput[], pagination: PaginationOutput }`。

- `sales`: 自分が起票または自分に割り当てられたチケットのみ
- `support`: 通常一覧を閲覧可能
- `view=responder`: supportのみ。未完了かつ未割当またはsupport担当のチケット

### `GET /tickets/{ticket_id}`

INPUTは `ticket_id`。OUTPUTは履歴を含む `TicketOutput`。

### 更新系

| Method / Path | INPUT | OUTPUT | 主な規則 |
|---|---|---|---|
| `PATCH /tickets/{id}/custom-fields` | `UpdateCustomFieldsInput`（全項目optional、1項目以上） | `DetailOutput` | support専用項目をsalesが更新すると`403`。報告書渡し済みは報告書、予定・担当者アサイン済みは客先同行でのみ更新可 |
| `POST /tickets/{id}/comments` | `{body: string}` | `DetailOutput` | trim後に空不可 |
| `POST /tickets/{id}/answer` | `{body: string}` | `DetailOutput` | supportのみ。対応済み化して起票者へ戻す |
| `PATCH /tickets/{id}/assignee` | なし | `DetailOutput` | supportのみ。自分へ割当て、対応中にする |
| `PATCH /tickets/{id}/status` | `{status_id: integer}` | `DetailOutput` | 対応待ちへ戻す場合は担当解除 |
| `PATCH /tickets/{id}/priority` | `{priority_id: integer}` | `DetailOutput` | Redmine列挙値にないIDは`400` |

カスタムフィールドの要件フラグを新たに有効化すると、対応待ち・未割当に戻して優先度を1段階上げます。完了フラグを有効化すると、対応済み・起票者割当を優先します。

## FAQ API

`FaqOutput` は `id`, `question`, `answer`, `version`, `author`, `created_on`, `updated_on` を返します。読み取りは `sales` / `support` / `admin`、書き込みは `support` / `admin` が可能です。

| Method / Path | INPUT | OUTPUT |
|---|---|---|
| `GET /faqs` | Query `q=""`, `limit=20`（1〜100）, `offset=0` | `{faqs: FaqOutput[], pagination}` |
| `POST /faqs` | `{question, answer}` | `FaqOutput` (`201`) |
| `GET /faqs/{faq_id}` | パスID | `FaqOutput` |
| `PUT /faqs/{faq_id}` | `{question, answer, version}` | `FaqOutput` |
| `DELETE /faqs/{faq_id}` | パスID | `DetailOutput` |

質問はtrim後1〜200文字、改行不可。回答はtrim後に必須です。更新時の `version` は1以上で、競合時は `409` を返します。

## メタデータ・運用 API

| Method / Path | INPUT | OUTPUT | 認証 |
|---|---|---|---|
| `GET /status/options` | なし | `[{id: integer, label: string}]` | 必須 |
| `GET /priority/options` | なし | `[{id, label, is_default}]` | 必須 |
| `GET /health` | なし | `{status: "healthy"}` | 不要 |

## 互換性方針

- URL、HTTP method、既存JSONフィールドは維持する。
- support専用フィールドはsales向けOUTPUTへ追加しない。
- `tracker_id` はクライアント互換のためINPUTに残すが処理には使用しない。
- Python側の旧 `backend.auth` と `backend.app` の主要importは移行期間中ファサード／aliasとして維持する。
