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
```

デプロイ、E2E、バックアップ、破棄の詳細は[Helmfileデプロイガイド](../docs/helmfile.md)を参照してください。

