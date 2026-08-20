# Kubernetesデプロイ資材

このディレクトリは、Docker Composeを残したままKubernetesへデプロイするための資材をまとめています。

| パス | 役割 |
|---|---|
| `chart/` | Portal、Redmine、PostgreSQL、Redis、OpenTelemetryのHelm chart |
| `environments/<env>.yaml` | int/dev/stg/prdの非機密な環境差分 |
| `env/<env>.env` | Git管理外の環境別シークレット |
| `env/<env>.env.example` | シークレットファイルの雛形 |
| `docker/` | Docker Compose専用のOpenTelemetry設定 |

環境のURL、Namespace、Traefik方式、テストユーザー名は、シークレットを用意する前でも確認できます。

```bash
./scripts/helmfile-deploy.sh int info
./scripts/helmfile-deploy.sh int sync team-space
# バックアップ後にだけ実行する旧要否フィールド移行
./scripts/helmfile-deploy.sh int tracker-migration team-space
./scripts/helmfile-e2e.sh int --namespace team-space --slot green
```

第3引数でNamespaceを指定できます。省略時は`support-ticket-portal-<env>`です。custom Namespaceは環境の最初の配置先であり、同じenvironmentを複数Namespaceへ並行配置するものではありません。Frontend/Backendは`blueGreen.activeSlot`で安定Serviceの接続先を切り替えるBlue-Green構成です。切替手順、E2E、バックアップ、破棄の詳細は[Helmfileデプロイガイド](../docs/helmfile.md)を参照してください。
