# Changelog

## 2026-08-10

### Backend DDDレイヤーとAPI契約

- Backendを `domain` / `application` / `infrastructure` / `presentation` の責務へ分離
- Redmine issue JSONをドメインモデルへ変換する腐敗防止層を追加
- 全APIにPydanticのINPUT/OUTPUTスキーマとOpenAPIタグを定義
- `backend.auth` と `backend.app` の既存import互換性を維持
- Backend API仕様とアーキテクチャ、ドキュメント索引を更新

## Unreleased

### Changed

- int/devに限定したBackend Ingressを追加し、環境別URLからSwagger UIとReDocへアクセス可能に変更
- Redmine Wikiを保存元とするFAQ一覧・検索・詳細・作成・編集・削除、ロール別認可、初期FAQ、Playwright E2Eを追加
- Helmfileの環境情報・URL・テストユーザー規則を共通スクリプトへ集約し、`helmfile-deploy.sh <env> info`でシークレットを表示せず確認可能に変更
- Helmのテストユーザー設定を環境名ベースの`<env>-admin/support/sales`へ統一し、環境valuesとE2E間の重複定義を削除
- 環境専用Traefikと既存Ingress Controllerの切替、Helmfile E2E、ログイン確認、バックアップ・破棄手順をデプロイドキュメントへ統合
- Redmine Ingressを全環境で常時作成し、環境別URLから管理画面を直接操作できる構成へ変更
- 営業・サポートの独立セッションを使う Playwright E2E を導入し、作成、サポート回答、対応要否、クローズを観点別に実行可能に変更
- 問い合わせ作成から3回のサポート対応、クローズまでを検証する13ステップのフルリグレッションを追加
- 変更箇所に応じたE2E選択基準と、大きな変更でのフルリグレッション必須ルールをテストガイドへ追加
- 優先度の選択肢を Redmine から取得し、チケット作成・一覧・詳細・変更で一貫して表示
- 「報告書が必要」または「客先同行が必要」を有効にした際、Redmine の列挙順で優先度を1段階自動引き上げ（上限では据え置き）
- 通常一覧のステータス絞り込みをクライアント側キャッシュへ移し、サポート担当者向け手動更新を追加
- 回答者向け一覧に前回のサポート対応者を追加し、個別履歴の取得失敗が一覧全体へ波及しないよう改善
- 優先度の上限・再引き上げ防止・不整合ページングなどの境界条件テストを追加
- Backend の重複していた例外ハンドラーとヘルスチェック定義を統合
- 予期しない例外で内部メッセージや型情報を API 利用者へ公開しないよう変更
- チケット件名・本文・コメントの前後空白を正規化し、空白だけの入力を拒否
- Frontend の監査ログ型を `Ticket` に追加し、型安全でないキャストを削除
- Frontend 依存関係を更新し、再現可能な `package-lock.json` と `npm ci` を採用
- README、セットアップ、アーキテクチャ、Redmine ドキュメントを現行実装へ更新

## v0.4.0 — 監査ログ機能追加 (2026-07-19)

### 新機能

#### Backend: 監査ログ API (`backend/app.py`)

チケット詳細の `audit_log` フィールドに、以下の情報が含まれる：

| フィールド | タイプ | 説明 |
|-----------|--------|------|
| type | "comment" \| "change" \| "both" | エントリータイプ |
| author | string | 変更者名 |
| created_on | string | 変更時刻 |
| comment | string? | コメント本文（存在する場合） |
| changes[] | AuditChange[] | フィールド変更一覧 |

AuditChange:
| field | display_field | old_value | new_value | 説明 |
|-------|-------------|-----------|-----------|------|
| prop_key | フィールド名 | 変更前 | 変更後 | Redmine journal details から取得 |

フィールド名マッピング：
```python
_FIELD_NAME_MAP = {
    "tracker": "トラッカー",
    "status": "ステータス",
    "priority": "優先度",
    "category": "カテゴリ",
    "assigned_to": "担当者",
    "subject": "件名",
    "description": "説明",
    # ... etc.
}
```

#### Frontend: 監査ログコンポーネント (`components/AuditLog.tsx`)

タイムライン形式で変更履歴を表示：
- 💬 コメント（青色ドット）
- 🔄 フィールド変更（オレンジ色ドット）
- フィールド変更表（フィールド名 | 変更前 | 変更後）
- 作成順ソート（古い順）

### テスト追加

#### `tests/audit_test.yaml` (新規作成)

| Step | 検証項目 |
|------|---------|
| 1 | Backend の起動確認 |
| 2 | テスト用チケット作成 |
| 3 | audit_log キーが API レスポンスに含まれる |
| 4 | コメント追加 → 監査ログ更新 |
| 5 | コメントが audit_log に記録される |
| 6 | ステータス変更 → 監査ログ更新 |
| 7 | ステータス変更が audit_log に記録される |

### ドキュメント更新

| ファイル | 変更内容 |
|---------|---------|
| `docs/redmine.md` (更新) | 監査ログ機能の説明追加 |
| `docs/changelog.md` (更新) | v0.4.0 の変更履歴追記 |

---

## v0.3.0 — ページネーション & エラーハンドリング (2026-07-19)

### 新機能

#### Backend: ページネーション対応 (`backend/app.py`)

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

---

## v0.1.0 — MVP 実装 (2026-05-21 ~ 2026-07-18)

### 初期実装

- **Backend API** (FastAPI): チケットCRUD、コメント追加、ステータス更新、OpenTelemetryトレース
- **Frontend** (React/Vite/TS): チケット一覧・作成・詳細画面、回答者向け画面
- **Docker Compose**: Redmine 6.1, PostgreSQL 15, Backend, Frontend(nginx), Tempo
- **ドキュメント**: 概要・アーキテクチャ・Redmine設定・MVPスコープ
