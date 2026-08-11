# システムアーキテクチャ

## Backend のレイヤー構成

BackendはDDDを基礎に、内側の業務概念がFastAPI・Redis・Redmineへ依存しない構造にしています。

```text
backend/
├── domain/
│   ├── models/             # Ticket、SessionDataなどの業務モデル
│   └── services/           # 優先度変更などの業務ポリシー
├── application/
│   ├── schemas/            # APIのINPUT / OUTPUT契約
│   ├── presenters/         # ドメインモデルから公開OUTPUTへの変換
│   └── ports.py            # 外部永続化に要求するインターフェース
├── infrastructure/
│   ├── redmine/            # Redmine JSONとの変換（腐敗防止層）
│   └── session_store.py    # RedisセッションとRedmine認証
├── presentation/api/       # HTTP固有の応答・エラー処理
├── app.py                  # Composition RootとFastAPIルート
└── auth.py                 # 旧import向け互換ファサード
```

依存方向は `presentation → application → domain`、`infrastructure → application/domain` です。`app.py` はComposition Rootとして具象アダプターを組み立てます。Redmineのissue JSONは `infrastructure/redmine/mappers.py` でドメインの `Ticket` へ変換し、support専用フィールドの公開可否はapplication presenterで制御します。

HTTP契約は [Backend API仕様](api.md) にまとめています。PydanticのINPUT/OUTPUTスキーマを全ルートへ明示しているため、`/openapi.json`、`/docs`、`/redoc` と文書の型定義は同じ実装を正とします。

## 実行構成

```text
Browser
  └─ Frontend (React/nginx, :3001)
       └─ /api
            └─ Backend (FastAPI, :8000)
                 ├─ Redmine REST API (:3000)
                 │    └─ PostgreSQL 15
                 ├─ Redis 7.4 (session)
                 └─ OTLP/HTTP (:4318, localhost)
                      └─ OpenTelemetry Collector (same Pod sidecar)
                           └─ OTLP/HTTP
                                └─ Grafana Alloy (gateway Pod)
                                     └─ OTLP/HTTP
                                          └─ External observability backend
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

FastAPI のリクエストと httpx による Redmine API 呼び出しを OpenTelemetry で計測します。Backend はトレースとPythonログをOTLP/HTTPで同一PodのCollectorへ送り、Collectorは別PodのGrafana Alloyへ、Alloyは外部の可観測性基盤へ転送します。

Backendのログレベルは既定でDEBUGです。Sidecar CollectorではINFO（severity number 9）未満を除外しますが、ログ属性 `ticket.portal.debug_enabled=true` が付いたレコードだけはDEBUGでも通過します。将来バックエンドで対象ログへ属性を付ける場合は、次のように指定できます。

```python
logger.debug(
    "diagnostic details",
    extra={"ticket.portal.debug_enabled": True},
)
```

属性名はHelm valuesの `observability.debugLogFlagAttribute` で変更できます。ヘルスチェックは `GET /health` で、設定値を含まないliveness応答のみを返します。

## デプロイ

Docker Composeによるローカル実行に加え、Helmfileでint/dev/stg/prd環境へデプロイできます。

Kubernetesでは環境ごとに`support-ticket-portal-<env>` Namespaceを使用します。PortalとRedmineのホスト名は`<namespace-prefix>-<env>-<feature>.<domain>`から生成します。Traefikは環境別設定により、環境専用ControllerをHelmfileで同時管理する方式と、既存Controllerを利用する方式を切り替えられます。

PortalとRedmineのIngressは常時作成します。int/devではAPI検証用のBackend Ingressも作成し、Swagger UIとReDocを公開します。stg/prdではBackend Ingressを作成しません。通常業務はPortalを利用し、Redmineの直接操作が必要な管理作業では環境別Redmine URLを利用します。

int/dev/stgのテストユーザー名はHelmfile環境名から`<env>-admin`、`<env>-support`、`<env>-sales`として生成します。パスワードだけをGit管理外の環境別secretファイルからKubernetes Secretへ渡します。prdではテストユーザーを無効化します。

OpenTelemetry設定は実行方式ごとに分離しています。Docker Composeは `deploy/docker/otel-collector.yaml` と `deploy/docker/alloy.alloy` を参照し、Kubernetesは `deploy/chart/templates/observability.yaml` が生成するConfigMapを参照します。
