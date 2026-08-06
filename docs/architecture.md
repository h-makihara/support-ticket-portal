# システムアーキテクチャ

## 実行構成

```text
Browser
  └─ Frontend (React/nginx, :3001)
       └─ /api
            └─ Backend (FastAPI, :8000)
                 ├─ Redmine REST API (:3000)
                 │    └─ PostgreSQL 15
                 ├─ Redis 7.4 (session)
                 └─ OpenTelemetry OTLP
                      └─ Tempo (:4317 / :3200)
```

nginx は `/api/*` を Backend に転送します。Frontend が Redmine API を直接呼ぶことはありません。

## 認証

1. Frontend が Redmine のユーザー名とパスワードを Backend の `POST /auth/login` へ送信する。
2. Backend が Redmine の `GET /users/current.json` で認証する。
3. Redmine が返した利用者 API キーを、6時間の有効期限付きで Redis に保存する。
4. ブラウザーにはランダムなセッション ID を `HttpOnly` Cookie で返す。
5. 以降の Redmine 操作には、セッション内の利用者 API キーを使用する。

本番環境では HTTPS を終端し、`SESSION_COOKIE_SECURE=true` に設定します。

## チケット処理

- 一覧は Redmine の Issues API を `limit` / `offset` 付きで取得する。
- 通常一覧は画面初期表示時に全ページを取得し、ステータス絞り込みと20件単位のページングをブラウザー内で行う。サポート担当者は手動で再取得できる。
- 回答者向け一覧は、未完了チケットを取得後、「未割り当て」または「サポート担当者に割り当て済み」に絞る。表示ページ内の journals を並行取得して前回のサポート対応者を求め、個別の履歴取得に失敗した場合も一覧自体は返す。
- 「自分が対応する」操作では、担当者をログインユーザーに設定し、同時に「対応中」へ変更する。
- 詳細では journals を取得し、コメントとフィールド変更を監査ログへ整形する。
- 再質問・追加質問で「対応待ち」へ戻す際は担当者を解除し、共有キューへ戻す。
- 優先度の選択肢は Redmine の列挙値を正とし、作成・詳細画面で共通利用する。「報告書が必要」または「客先同行が必要」が新たに有効になった場合は列挙順で1段階上げ、最大値では据え置く。

## 可観測性

FastAPI のリクエストと httpx による Redmine API 呼び出しを OpenTelemetry で計測し、OTLP gRPC で Tempo へ送信します。ヘルスチェックは `GET /health` で、設定値を含まない liveness 応答のみを返します。

## デプロイ

現行の提供形態は Docker Compose です。Kubernetes / Helm 定義はこのリポジトリには含まれていません。
