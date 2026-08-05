# Redmine 設定とワークフロー

## 前提

- Docker image: `redmine:6.1`
- Database: PostgreSQL 15
- REST API を有効化
- 固定プロジェクト: `internal-inquiry`（社内問い合わせ）
- トラッカー: `問い合わせ`

ポータルから作成するチケットは、リクエスト内のトラッカー指定にかかわらず `REDMINE_TRACKER_ID` の問い合わせトラッカーへマッピングされます。

## 初期化

```bash
docker compose up -d postgres redmine
python3 scripts/init_redmine.py
```

初期化処理は冪等で、既存リソースを確認して不足分のみを設定します。トラッカーは Redmine REST API から新規作成できないため、存在しない場合は Redmine 管理画面で作成してから再実行します。

`scripts/bootstrap_redmine.rb` は Docker 環境内で、REST API の有効化、ロール・ワークフロー、必要に応じた検証ユーザーの準備に利用されます。

## ステータス

Redmine 6.1 の標準ステータスを、ポータルでは次の業務ラベルとして扱います。

| ID | Redmine 標準名 | ポータルのラベル | API フィルター |
|---:|---|---|---|
| 1 | New | 新規 | `open` |
| 2 | In Progress | 対応中 | `in_progress` |
| 3 | Resolved | 回答済 | `answered` |
| 4 | Feedback | 追加質問 | `additional_question` |
| 5 | Closed | クローズ | `closed` |
| 6 | Rejected | クローズ待ち | `pending_close` |

既存環境の `Reopened` も追加質問として認識します。Backend は起動時に `/issue_statuses.json` を取得し、名前または slug から ID を解決します。Redmine が一時的に応答しない場合は標準 ID をフォールバックとして使用します。

## 基本フロー

```text
新規
  └─ 自分が対応する → 対応中
       └─ 回答 → 回答済
            ├─ 完了 → クローズ
            └─ 追加質問 → 追加質問（担当解除）
                 └─ 自分が対応する → 対応中
```

「自分が対応する」はログインユーザーを担当者に設定し、同時に「対応中」へ変更します。「追加質問」へ変更すると担当者を解除し、回答者の共有キューへ戻します。実際に許可される遷移は Redmine のロール別ワークフローに従います。

## ロール

| ロール | 主な操作 |
|---|---|
| 営業担当者 | 作成、閲覧、コメント、許可されたステータス変更 |
| サポート担当者 | 閲覧、担当引受、コメント、ステータス変更 |

回答者向け一覧には、未完了かつ未割り当て、または `サポート担当者` ロールのユーザーに割り当てられたチケットを表示します。

## API キー

- Backend の起動時キャッシュやメンバー取得には `.env` の管理用 `REDMINE_API_KEY` を使用します。
- 利用者のチケット操作には、ログイン時に Redmine から取得して Redis セッションへ保存した利用者自身の API キーを使用します。
- API キーをブラウザーへ返したり、ログへ出力したりしないでください。

## 監査ログ

`GET /tickets/{id}` は Redmine journals を次の2形式へ変換します。

- `audit_log`: コメントと項目変更を時系列表示する現行形式
- `notes`: コメントだけを返す後方互換形式

担当者 ID とステータス ID は、取得できたプロジェクトメンバー名・ステータス名へ変換します。

## ページネーション

`GET /tickets` は `limit`（1〜1000）と `offset`（0以上）を受け取ります。回答者向け一覧は Redmine 側でロールによる担当者絞り込みができないため、最大1000件を取得してから Backend で絞り込みとページ分割を行います。

## 結合テスト

Docker Compose 一式を起動後、リポジトリルートで `runn` を実行します。個別シナリオは `tests/*.yaml` にあります。

参考: [Redmine REST API](https://www.redmine.org/projects/redmine/wiki/Rest_api)
