# Changelog

## v0.3.0 — ページネーション & エラーハンドリング (2026-07-19)

### 新機能

#### Backend: ページネーション対応 (`src/backend/app.py`)

`GET /tickets` に `limit`/`offset` パラメータを追加：

```bash
# デフォルト (limit=100, offset=0)
GET /tickets

# 明示的なページ指定
GET /tickets?limit=20&offset=40

# ステータスフィルタと組み合わせ可能
GET /tickets?status=open&limit=10&offset=0
```

レスポンス形式:
```json
{
  "tickets": [...],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total_count": 150,
    "has_more": true
  }
}
```

- **上限制約**: limit は最大 1000 に制限、offset は非負整数
- **Redmine API 連携**: Redmine の `limit`/`offset` パラメータを直接転送

#### Frontend: ページネーション UI (`frontend/src/pages/TicketList.tsx`, `AnswerTicketList.tsx`)

| 機能 | 説明 |
|------|------|
| 前へ/次へ ボタン | 前後のページへの移動 |
| ページ番号一覧 | 現在5ページ表示（左右に2ページずつ） |
| 合計件数表示 | フィルタ後の総チケット数をステータスバーに表示 |
| Auto-reset | ステータスフィルタ変更時に1ページ目にリセット |

#### Frontend: エラーハンドリング改善 (全ページ)

| ページ | 追加機能 |
|--------|---------|
| `TicketList.tsx` | APIエラー時のバナー表示 + 再試行ボタン |
| `AnswerTicketList.tsx` | 同上 |
| `TicketDetail.tsx` | 取得失敗時、コメント追加失敗時、ステータス更新失敗時の個別ハンドリング |
| `TicketCreate.tsx` | 作成失敗時のエラーメッセージ表示 |

エラー状態:
- 🔴 API接続不良 → エラーバナー + 再試行ボタン
- 🟡 必須入力漏れ → フォーム検証エラー
- ⚪ 処理中 → ローディングインジケータ（スピナ/テキスト）

### テスト追加

#### `tests/pagination_test.yaml` (新規作成)

| Step | 検証項目 |
|------|---------|
| 1 | Backend の起動確認 |
| 2 | レスポンスに pagination キーが含まれる |
| 3 | limit パラメータで件数が制限される |
| 4 | offset パラメータでスキップされる |
| 5 | デフォルトlimitが正しく適用される |
| 6 | has_more フィールドが正しく計算される |

---

## v0.2.0 — Redmine 初期化スクリプト追加 (2026-07-19)

### 新機能

#### `scripts/init_redmine.py` (新規作成, 257行)

Redmine REST API を叩いて、以下のリソースを自動作成します：

| リソース | 識別子/名前 | 説明 |
|---------|-----------|------|
| プロジェクト | `internal-inquiry` / 「社内問い合わせ」 | チケット管理用プロジェクト |
| トラッカー | `問い合わせ` | 営業→サポートの問い合わせ |
| ロール | `営業担当者` | チケット作成・確認・クローズ権限 |
| ロール | `サポート担当者` | 回答・ステータス更新権限 |

- **冪等性 (Idempotent)**: 既に存在するリソースはスキップします。
- **.env 自動生成**: API Key / プロジェクト ID を `.env` に書き出します。
- **Redmine 待機**: Redmine が起動するまで最大180秒待機します。

#### `scripts/init.sh` (更新, 46行)

全手順を自動実行：

```bash
./scripts/init.sh
# → docker compose up postgres+redmine → init_redmine.py → backend+frontend+tempo
```

#### Backend: ステータス動的解決 (`src/backend/app.py`, 334行)

- Redmine 起動時に `/issue_statuses.json` を叩いてステータスマッピングを構築
- Redmine に接続できない場合、デフォルトマッピング (New=1, In Progress=2, Reopened=3, Closed=4) にフォールバック
- `GET /status/options`: フロントエンド向けのステータスドロップダウン用データ

#### Backend: ジャーナル（コメント履歴）取得 (`src/backend/app.py`)

- `GET /tickets/{id}` で `?include=journals` を使い、Redmine の journals データを取得
- `_journals_to_notes()`: Redmine journals → frontend が扱いやすい `notes[]` 形式に変換
- journal entries からテキストコメントのみを抽出（ステータス変更ログなどは除外）

#### Frontend: API Client 更新 (`frontend/src/api/client.ts`, 62行)

- `getTicketStatusOptions()`: `/status/options` を呼ぶ新APIメソッド追加

#### Frontend: ステータスドロップダウンの動的化 (`frontend/src/pages/TicketDetail.tsx`, 109行)

- Redmine から取得したステータス一覧をドロップダウンに表示
- ハードコード済みの4ステータス → API から取得するように変更

### テスト

#### `tests/init_test.yaml` (新規作成, 112行)

runn を使用して、以下を8ステップで検証：

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

### ドキュメント更新

| ファイル | 変更内容 |
|---------|---------|
| `docs/setup.md` (新規) | セットアップガイド・クイックスタート |
| `docs/redmine.md` (更新) | 初期化スクリプトの説明追加、ステータス定義見直し |
| `docs/index.md` (更新) | ドキュメント構造の整理・テスト項目追加 |

### ステータス定義の変更

旧: カスタムステータス6種（新規・回答待ち・営業確認中・追加質問あり・技術確認中・クローズ）

新: Redmine デフォルト4種（New/In Progress/Reopened/Closed）→ 英語キーマッピングで解釈

| ID | Redmine Status | 英語キー | 役割 |
|---|---|---|---|
| 1 | New | `open` | 新規受付（営業作成直後） |
| 2 | In Progress | `in_progress` | サポート対応中・技術確認中 |
| 3 | Reopened | `feedback` | 追加質問 / フィードバック待ち |
| 4 | Closed | `closed` | 完了・クローズ |

---

## v0.1.0 — MVP 実装 (2026-05-21 ~ 2026-07-18)

### 初期実装

- **Backend API** (FastAPI): チケットCRUD、コメント追加、ステータス更新、OpenTelemetryトレース
- **Frontend** (React/Vite/TS): チケット一覧・作成・詳細画面、回答者向け画面
- **Docker Compose**: Redmine 6.1, PostgreSQL 15, Backend, Frontend(nginx), Tempo
- **ドキュメント**: 概要・アーキテクチャ・Redmine設定・MVPスコープ
