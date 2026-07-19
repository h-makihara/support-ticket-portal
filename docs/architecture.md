# システムアーキテクチャ

以下は主要コンポーネントと通信フローです。

```
Browser
   └─ HTTP (REST API)

Frontend (React/TS)
   └─ GET/POST … API endpoints

Backend API (FastAPI/Python)
   └─ Calls Redmine REST API

Redmine (6.1.x)
   └─ Stores tickets, comments, statuses

PostgreSQL
   └─ Data store for Redmine
```

* **Frontend** は Vite + React/TypeScript で構築。
* **Backend API** は FastAPI で実装。Redmine API をラップ。
* **Redmine** は OSS 版 6.1.x を使用。

## デプロイ

Helm Chart を使用して Kubernetes にデプロイ。

```yaml
redmine:
  image:
    repository: redmine
    tag: "6.1"
```

* PostgreSQL は外部サービスまたは StatefulSet として構成。

```yaml
postgresql:
  image: postgres:15
```

## セキュリティ

* Redmine API キー（X‑Redmine‑API‑Key）を使用。
* フロントエンドは HTTPS（In‑gress）で保護。
```

