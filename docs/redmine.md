# Redmine 環境

## バージョン

- Redmine 6.1.x（最新安定版）
- PostgreSQL 15 (Docker)

## Docker Compose

Minimal Docker Compose configuration is provided in the repository root
(`docker-compose.yml`). Running the stack will start Redmine (v6.1) backed by a
PostgreSQL database.

```bash
docker compose up -d postgres redmine backend frontend tempo
```

After the containers are up, Redmine will be accessible at `http://localhost:3000`.
The stack is pre‑configured with:

* **Default user** – `admin / admin`
* **API key** – obtained automatically via the initialization script.

## 初期化スクリプト

プロジェクトのセットアップを自動で行うスクリプトが用意されています。

```bash
# 全手順 (docker起動 → Redmine初期化 → Backend/Frontend起動)
./scripts/init.sh

# Redmine API のみ（既に Docker が動いている場合）
python3 scripts/init_redmine.py
```

### 環境変数（デフォルト値含む）

| 変数名 | デフォルト | 説明 |
|-------|-----------|------|
| `REDMINE_URL` | `http://localhost:3000` | Redmine の URL |
| `ADMIN_USER` | `admin` | Redmine admin ユーザー名 |
| `ADMIN_PASS` | `admin` | Redmine admin パスワード |

スクリプトの実行後、`.env` ファイルに API Key / プロジェクト ID が自動的に書き出されます。

## セットアップされるリソース

初期化スクリプトは以下を自動作成します（冪等性あり — 既存ならスキップ）：

| リソース | 名前/識別子 | 説明 |
|---------|-----------|------|
| プロジェクト | `internal-inquiry` / 「社内問い合わせ」 | チケット管理用プロジェクト |
| トラッカー | `問い合わせ` | 営業→サポートの問い合わせ |
| ステータス | Redmine デフォルト利用（下記参照） | |
| ロール | `営業担当者` | チケット作成・確認・クローズ権限 |
| ロール | `サポート担当者` | 回答・ステータス更新権限 |

## ステータス定義

Redmine デフォルトの 4 つのステータスをそのまま使用し、フロントエンド/バックエンド側で以下のように解釈します：

| Redmine デフォルト ID | Redmine Status | 英語キー | 役割 |
|---|---|---|---|
| 1 | New | `open` | 新規受付（営業作成直後） |
| 2 | In Progress | `in_progress` | サポート対応中・技術確認中 |
| 3 | Reopened | `feedback` | 追加質問 / フィードバック待ち |
| 4 | Closed | `closed` | 完了・クローズ |

### ステータス遷移イメージ

```
[新規] ──作成──→ [open]
                    │
                 (サポート対応)
                    ↓
               [in_progress]
                    │
              (回答完了/フィードバック)
                    ↓
              [feedback / Reopened]
                    │
            ┌───────┴────────┐
          営業確認        追加質問あり
             ↓                ↓
         [closed] ←── [feedback loop ...]
```

## API キー

- Redmine REST API は `X-Redmine-API-Key` ヘッダーで認証。
- 初期化スクリプト実行時に自動取得・`.env` に保存されます。

## テスト

runn を使用して、初期化の正しさを確認できます：

```bash
# Docker compose が動いている状態で
runn -e REDMINE_URL=http://localhost:3000 tests/init_test.yaml
```

### テスト内容

| Step | 検証項目 |
|------|---------|
| 1 | Redmine の HTTP レスポンス確認 |
| 2 | admin アカウントで API Key が取得できる |
| 3 | プロジェクト `internal-inquiry` が存在する |
| 4 | トラッカー `問い合わせ` が存在する |
| 5 | デフォルトステータス (New/In Progress/Reopened/Closed) が存在する |
| 6 | カスタムロール「営業担当者」「サポート担当者」が作成されている |
| 7 | Backend API `/status/options` が動作する |
| 8 | チケット一覧 API `/tickets` が正常に応答する |

## 参照

- [Redmine API ドキュメント](https://www.redmine.org/projects/redmine/wiki/Rest_api)

## ページネーション

Backend API は `GET /tickets` でページネーションをサポートしています：

| パラメータ | 説明 | デフォルト | 最大値 |
|-----------|------|----------|--------|
| `limit` | 1ページの件数 | 100 | 1000 |
| `offset` | スキップ件数 | 0 | - |

レスポンス例:
```json
{
  "tickets": [ ... ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total_count": 150,
    "has_more": true
  }
}
```

## エラーハンドリング

フロントエンドは以下のようにエラーを処理します：

| エラースコープ | 表示方法 | アクション |
|---------------|---------|-----------|
| API接続不良 | 赤字バナー + 再試行ボタン | リトライ可能 |
| フォーム検証失敗 | インラインメッセージ | 入力修正 |
| 処理中 | ローディングインジケータ | 待機 |

## テスト

runn を使用して、初期化の正しさとページネーションの動作を確認できます：

```bash
# Docker compose が動いている状態で
runn tests/init_test.yaml       # Redmine 初期化テスト
runn tests/pagination_test.yaml # ページネーションテスト
runn                           # .runn.yaml に定義された全テスト実行
```

## 監査ログ機能

### API 仕様

`GET /tickets/{id}` のレスポンスに `audit_log` フィールドが含まれます：

```json
{
  "id": 123,
  "subject": "テスト",
  "description": "...",
  "audit_log": [
    {
      "type": "comment",
      "author": "admin",
      "created_on": "2024-01-01T00:00:00Z",
      "comment": "初期コメント",
      "changes": []
    },
    {
      "type": "change",
      "author": "admin",
      "created_on": "2024-01-01T00:05:00Z",
      "changes": [
        {
          "field": "status_id",
          "display_field": "ステータス",
          "old_value": "New",
          "new_value": "In Progress"
        }
      ]
    },
    {
      "type": "both",
      "author": "user",
      "created_on": "2024-01-02T10:00:00Z",
      "comment": "ステータス変更とコメント同時",
      "changes": [
        {
          "field": "priority_id",
          "display_field": "優先度",
          "old_value": "Low",
          "new_value": "High"
        }
      ]
    }
  ]
}
```

### フィールド名マッピング

Backend は Redmine の `prop_key` を日本語ラベルに変換します：

| prop_key | 表示ラベル |
|----------|-----------|
| tracker_id | タッカー |
| status_id | ステータス |
| priority_id | 優先度 |
| assigned_to_id | 担当者 |
| subject | 件名 |
| description | 説明 |

### 監査ログの表示

フロントエンドでは `AuditLog` コンポーネントがタイムライン形式で履歴を表示します：

- 💬 青色ドット: コメント追加
- 🔄 オレンジ色ドット: フィールド変更
- テーブル形式でフィールド変更の一覧（変更前/変更後）


echo "Redmine docs updated with audit log documentation"