# Helmfile デプロイ

Docker Compose は従来どおりローカル開発に利用できます。Kubernetes へのデプロイは、リポジトリ直下の `helmfile.yaml.gotmpl` と `deploy/chart` を利用します。

## 構成と環境切替

| 環境 | Namespace | Portal host | Redmine host | Backend host | テストユーザー |
|---|---|---|---|---|---|
| int | `support-ticket-portal-int` | `support-ticket-portal-int-portal.localhost` | `support-ticket-portal-int-redmine.localhost` | `support-ticket-portal-int-backend.localhost` | 有効 |
| dev | `support-ticket-portal-dev` | `support-ticket-portal-dev-portal.localhost` | `support-ticket-portal-dev-redmine.localhost` | `support-ticket-portal-dev-backend.localhost` | 有効 |
| stg | `support-ticket-portal-stg` | `support-ticket-portal-stg-portal.localhost` | `support-ticket-portal-stg-redmine.localhost` | 非公開 | 有効 |
| prd | `support-ticket-portal-prd` | `support-ticket-portal-prd-portal.localhost` | `support-ticket-portal-prd-redmine.localhost` | 非公開 | 無効 |

ホスト名は `<namespace>-<environment>-<feature>.<domain>` の規則で生成します。既定値では namespace が `support-ticket-portal`、environment が `int` など、feature が `portal` または `redmine` です。環境固有値は `deploy/environments/<env>.yaml`、シークレットは Git 管理外の `deploy/env/<env>.env` に分離されています。Backend 固有の環境変数は各 values の `app.backendEnv` に追加でき、既定で `DEPLOY_ENVIRONMENT` が環境名へ切り替わります。

現在の環境情報は、シークレット値を表示せずに確認できます。

```bash
./scripts/helmfile-deploy.sh int info
# Namespaceを明示する場合（省略時は support-ticket-portal-int）
./scripts/helmfile-deploy.sh int info team-preview
```

このコマンドはNamespace、Portal/Redmine URL、int/devで有効なBackend・Swagger UI・ReDoc URL、Traefik方式、valuesとsecretファイルの場所、テストユーザー名と対応するパスワード変数名を表示します。

Chart は Frontend、Backend（OpenTelemetry Collector sidecar）、Grafana Alloy gateway、Redmine、PostgreSQL、Redis、Traefik Ingress と、Redmine のプロジェクト・ロール・ワークフロー・テストユーザーを作る冪等な bootstrap Job を含みます。

Docker Compose用のCollector/Alloy設定は `deploy/docker` に分離されています。Helm Chartはそれらを参照せず、Kubernetes専用の `templates/observability.yaml` からConfigMapを生成します。

## OpenTelemetry転送先

Alloyから外部可観測性基盤へ送るOTLP/HTTPのベースURLを、環境別valuesで設定します。URLには `/v1/logs` 等のsignal pathを含めません。未設定事故を見分けやすくするため既定値は到達不能な `.invalid` ドメインです。実環境へのデプロイ前に必ず置き換えてください。

```yaml
observability:
  externalOtlpEndpoint: "https://otel.example.com:4318"
  debugLogFlagAttribute: "ticket.portal.debug_enabled"
```

Backendは `http://localhost:4318` のsidecarへログとトレースを送ります。sidecarはINFO以上、および `debugLogFlagAttribute` で指定したboolean属性が `true` のDEBUGログだけをAlloyへ通します。パイプラインはmetricsも受信・転送できるため、Backend側でmetricsを追加した際にGateway構成を変更する必要はありません。

Collector/Alloyイメージはint/devで `latest`、stg/prdで固定タグを使用します。現在の固定値はCollector `0.158.0`、Alloy `v1.18.1` です。

## 前提

- Kubernetes クラスタと、そのクラスタを指す現在の kube-context
- Helm 3、Helmfile、kubectl
- Traefikを同時導入しない環境では、valuesの`traefik.externalIngressClass`と同名の既存Ingress Controller
- Traefikを同時導入する環境では、公式Helm repository `https://traefik.github.io/charts`へのネットワークアクセス
- 動的 PVC provisioning が可能な既定 StorageClass、または values の `persistence.storageClass`
- クラスタから pull できる Backend/Frontend コンテナイメージ

既定のアプリイメージは `support-ticket-portal/backend:<env>` と `support-ticket-portal/frontend:<env>` です。実レジストリに合わせて各 `deploy/environments/<env>.yaml` の repository/tag と、必要なら `imagePullSecrets` を変更します。

例:

```bash
docker build -f backend/Dockerfile -t registry.example.com/support-ticket-portal/backend:int .
docker build -f frontend/Dockerfile -t registry.example.com/support-ticket-portal/frontend:int frontend
docker push registry.example.com/support-ticket-portal/backend:int
docker push registry.example.com/support-ticket-portal/frontend:int
```

## デプロイ

環境ごとにサンプルをコピーし、プレースホルダーを十分に強い固有値へ置き換えます。この `.env` は Git から除外されます。

```bash
cp deploy/env/int.env.example deploy/env/int.env
${EDITOR:-vi} deploy/env/int.env

# 差分確認
./scripts/helmfile-deploy.sh int diff

# デプロイまたは更新
./scripts/helmfile-deploy.sh int sync

# 任意のNamespaceへデプロイ
./scripts/helmfile-deploy.sh int sync team-preview

# 状態確認
kubectl -n support-ticket-portal-int get pods,ingress
```

環境名を `dev`、`stg`、`prd` に変えると、values、Namespace、イメージタグ、Ingress host、テストユーザー設定がまとめて切り替わります。

コマンド形式は `helmfile-deploy.sh <environment> [action] [namespace]` です。Namespace引数を省略した場合は従来どおり `support-ticket-portal-<environment>` を使います。指定値はKubernetesのDNS label（小文字英数字と`-`、最大63文字）として検証され、Helm releaseと組み込みTraefikの監視対象の両方へ反映されます。URLのhostはNamespaceとは独立しており、従来どおりvaluesの`url.namespace`または各Ingressの`host`で設定します。

## Blue-Greenデプロイ

FrontendとBackendはそれぞれ`blue`、`green`の2つのDeploymentとして常時起動します。Ingressが参照する`frontend`、`backend` Serviceは、`blueGreen.activeSlot`のslot labelを持つPodだけを選択します。PostgreSQL、Redis、Redmineなどの永続系コンポーネントは両slotで共有します。

```yaml
blueGreen:
  activeSlot: blue
  slots:
    blue:
      backendTag: "2026.08.1"
      frontendTag: "2026.08.1"
    green:
      backendTag: "2026.08.2"
      frontendTag: "2026.08.2"
```

空のslot tagは従来の`images.backend.tag`または`images.frontend.tag`へフォールバックします。切替時は、次の2段階で同期します。

1. 現在の`activeSlot`は変えず、inactive slotの`backendTag`と`frontendTag`だけを新バージョンへ更新して`sync`します。
2. `kubectl -n <namespace> rollout status deployment/backend-<inactive>`と`frontend-<inactive>`でreadyを確認します。
3. `activeSlot`をinactive slotへ変更し、もう一度`sync`します。安定ServiceのselectorがFrontend/Backendとも新slotへ切り替わります。

切替後に問題があれば、`activeSlot`を直前のslotへ戻して`sync`するとrollbackできます。データベースschemaは両slotから同時利用できる後方互換なmigrationにしてください。

### Traefikを一緒に導入・破棄するか切り替える

各[環境別values](../deploy/environments/int.yaml)の`traefik.install`で切り替えます。

組み込みTraefikは公式chart `traefik/traefik` のversion `41.2.0`へ固定しています。

```yaml
traefik:
  install: true
  bundledIngressClass: traefik-int
  externalIngressClass: traefik
  serviceType: LoadBalancer
```

- `install: true`: 環境専用Traefikをアプリより先に導入します。`helmfile destroy`ではアプリと一緒に削除します。
- `install: false`: Traefik releaseを作らず、`externalIngressClass`で指定した既存Controllerを利用します。以前`true`で導入したTraefikがあれば、次回`sync`で削除します。

`install`だけを切り替えれば、Portal/RedmineのIngressClassも`bundledIngressClass`と`externalIngressClass`の間で自動的に切り替わります。同じクラスタへ複数環境のTraefikを導入する場合は、`traefik-int`、`traefik-dev`のように環境ごとに異なる`bundledIngressClass`を指定してください。組み込みTraefikはIngressClass参照のためClusterRoleを作成しますが、リソースの監視対象は`support-ticket-portal-<env>` Namespaceだけに制限します。標準Ingressだけを使用するため、Traefik CRDは導入しません。

Docker Desktopでは`serviceType: LoadBalancer`により、通常はHTTP/HTTPSがlocalhostの80/443番へ公開されます。クラスタがLoadBalancer Serviceに対応しない場合は、環境に応じてNodePortや外部LoadBalancerの設定が必要です。

設定変更後は通常どおり同期します。

```bash
./scripts/helmfile-deploy.sh int sync
kubectl -n support-ticket-portal-int get pods,service,ingress
kubectl get ingressclass
```

`template` は Secret の内容も標準出力へ render するため、出力をログや共有ファイルへ保存しないでください。

## バックアップして環境を破棄する

一時的に環境を作成し、必要なデータだけを保管して完全に破棄する場合は、次の順序で操作します。

1. 書き込みを止める。
2. PostgreSQL と Redmine 添付ファイルをバックアップする。
3. バックアップを検証する。
4. アプリと、管理対象の場合はTraefikのHelm releaseを削除する。
5. Namespace、PVC、PV の残存を確認して完全に削除する。

Redmine の主要データは PostgreSQL にありますが、添付ファイルは `redmine-files` PVC にあります。どちらか一方だけでは完全なバックアップになりません。また、再構築には同じ環境の values、イメージバージョン、シークレットも必要です。

### 1. 対象クラスタと環境の確認

次の例は int 環境をバックアップします。作業前に kube-context と Namespace を必ず確認してください。

```bash
ENVIRONMENT=int
NAMESPACE="support-ticket-portal-${ENVIRONMENT}"
BACKUP_DIR="backups/${ENVIRONMENT}/$(date +%Y%m%d-%H%M%S)"

kubectl config current-context
kubectl -n "$NAMESPACE" get deploy,statefulset,pod,pvc,ingress
mkdir -p "$BACKUP_DIR"
```

`backups/` は機密データを含むため、Git に追加せず、暗号化された保管先へ移動してください。

### 2. 書き込みの停止

Portal 経由の更新を防ぐため Backend を停止します。Redmine 用 Ingress を別途有効化している場合は、そちらからの直接操作も停止してください。

```bash
kubectl -n "$NAMESPACE" scale deployment/backend-blue deployment/backend-green --replicas=0
kubectl -n "$NAMESPACE" rollout status deployment/backend-blue --timeout=120s
kubectl -n "$NAMESPACE" rollout status deployment/backend-green --timeout=120s
```

バックアップ後に環境を破棄しない場合は、`./scripts/helmfile-deploy.sh "$ENVIRONMENT" sync` で values の replica 数へ戻せます。

### 3. PostgreSQL と添付ファイルのバックアップ

PostgreSQL は custom format で dump します。添付ファイルは Redmine Pod から tar archive として取得します。

```bash
kubectl -n "$NAMESPACE" exec statefulset/postgres -- \
  pg_dump -U postgres -d redmine --format=custom \
  > "$BACKUP_DIR/redmine-postgres.dump"

kubectl -n "$NAMESPACE" exec deployment/redmine -- \
  tar -czf - -C /usr/src/redmine files \
  > "$BACKUP_DIR/redmine-files.tar.gz"

cp "deploy/environments/${ENVIRONMENT}.yaml" "$BACKUP_DIR/environment-values.yaml"

kubectl -n "$NAMESPACE" get deployment -o \
  jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.template.spec.containers[*]}{.image}{" "}{end}{"\n"}{end}' \
  > "$BACKUP_DIR/images.txt"
```

`deploy/env/<env>.env` はバックアップディレクトリへ平文コピーせず、パスワードマネージャーや Secret Manager などの暗号化された保管先へ別途保存します。少なくとも `REDMINE_API_KEY`、`REDMINE_SECRET_KEY_BASE`、`POSTGRES_PASSWORD` と、必要ならテストユーザーのパスワードが再構築時に必要です。

### 4. バックアップの検証

ファイルが空でないこと、PostgreSQL dump の目次を読めること、添付ファイル archive を展開せずに一覧できることを確認します。

```bash
test -s "$BACKUP_DIR/redmine-postgres.dump"
test -s "$BACKUP_DIR/redmine-files.tar.gz"
pg_restore --list "$BACKUP_DIR/redmine-postgres.dump" >/dev/null
tar -tzf "$BACKUP_DIR/redmine-files.tar.gz" >/dev/null

(
  cd "$BACKUP_DIR"
  shasum -a 256 redmine-postgres.dump redmine-files.tar.gz \
    environment-values.yaml images.txt > SHA256SUMS
)
```

`pg_restore` コマンドが手元にない場合は、PostgreSQL 15 のクライアントまたはコンテナで検証します。重要な環境では、別 Namespace/クラスタへのリストア試験が完了するまで元環境を破棄しないでください。

### 5. Helm release の削除

バックアップ検証後に release を削除します。`traefik.install: true`の場合は依存関係の逆順でアプリ、Traefikの順に両releaseを削除します。この操作により Deployment、Service、Ingress、Secret、および Helm が直接管理する `redmine-files` PVC が削除されます。先に実行すると添付ファイルを回収できなくなる可能性があります。

```bash
./scripts/helmfile-deploy.sh "$ENVIRONMENT" destroy

helm -n "$NAMESPACE" list --all
kubectl -n "$NAMESPACE" get all,ingress,pvc
kubectl get ingressclass
```

PostgreSQL StatefulSet の `volumeClaimTemplates` から作られた PVC は、release 削除後も残る場合があります。`helmfile destroy` だけを完全破棄とは見なさないでください。

### 6. Namespace とストレージの完全削除

バックアップの保管を確認したら Namespace を削除します。これにより、Namespace 内に残っている PVC、Secret、失敗した Job なども削除されます。

```bash
kubectl delete namespace "$NAMESPACE"
kubectl get namespace "$NAMESPACE"
kubectl get pv
```

最後の `kubectl get namespace` が `NotFound` になれば Namespace の削除は完了です。PV の実体が削除されるか残るかは StorageClass の `reclaimPolicy` が `Delete` か `Retain` かで異なります。`Retain` の PV やクラウドディスクが残った場合は、PV名、ストレージID、対象環境が一致することを確認してから、クラスタ/クラウド側の手順で削除してください。

### 7. 再作成時

空の環境は、保管してある環境別シークレットを `deploy/env/<env>.env` に戻して、通常どおり作成できます。

```bash
./scripts/helmfile-deploy.sh "$ENVIRONMENT" sync
```

過去データを戻す場合は、同じ Redmine/PostgreSQL のメジャーバージョンを使用し、PostgreSQL dump と `redmine-files.tar.gz` を必ず同じバックアップ世代から復元します。復元後にバージョンアップする場合は、まず元バージョンで復元確認してから段階的に更新してください。

## DNS、Traefik、TLS

`.localhost` はローカルマシンの loopback へ名前解決されます。Docker Desktop、k3d、kind などで Traefik の HTTP entrypoint が localhost に公開されていれば、追加の hosts 設定なしで次のようにアクセスできます。

```text
http://support-ticket-portal-int-portal.localhost
```

URLの共通要素は [values.yaml](../deploy/chart/values.yaml) で設定します。

```yaml
url:
  namespace: support-ticket-portal
  domain: localhost
```

この設定から `support-ticket-portal-int-portal.localhost`、`support-ticket-portal-int-redmine.localhost`、int/devでは`support-ticket-portal-int-backend.localhost`形式のホストが生成されます。共有クラスタでは `url.domain` を実際の wildcard DNS 配下（例: `apps.example.com`）へ変更し、`*.apps.example.com` を Traefik の LoadBalancer IP/CNAME に向けます。特定機能だけ例外にする場合は `ingress.host`、`redmineIngress.host`、`backendIngress.host`を明示します。Traefik は HTTP routing を行いますが、DNS レコード自体は作りません。

例えば `url.namespace: namespace` の場合、int の Redmine URL は `namespace-int-redmine.localhost` になります。

Redmine Ingressはすべての環境で常時作成されます。Redmineの手動操作が必要な場合は、表に記載した`<namespace>-<environment>-redmine.<domain>`形式のURLへアクセスします。公開範囲を制限する場合は、Traefik Middleware、ネットワーク境界、認証プロキシなどクラスタ側のアクセス制御を設定してください。

Backend Ingressはint/devだけで作成されます。Swagger UIは`<Backend URL>/docs`、ReDocは`<Backend URL>/redoc`です。「Try it out」を含むAPI検証に対応するためBackend Service全体を同一ホストへルーティングします。stg/prdではIngress自体を生成しません。共有環境では必要に応じてIngress annotationやネットワーク境界でアクセス元を制限してください。

組み込みTraefikを使う場合、IngressClassは環境別`traefik.bundledIngressClass`からPortalとRedmineのIngressへ自動設定されます。既存Controllerを使う場合は`traefik.externalIngressClass`が設定されます。

TLS を有効化する場合は対象の`ingress.tls.enabled`、`redmineIngress.tls.enabled`、または`backendIngress.tls.enabled`を有効にして既存TLS Secret名を設定します。PortalをHTTPSにする場合は`app.sessionCookieSecure: true`にします。cert-managerを使う場合は各Ingressの`annotations`にissuer annotationを追加します。

## E2E

### テストユーザーの定義

テストユーザーを有効にするかは[環境別values](../deploy/environments/int.yaml)の`app.testUsers.enabled`で定義します。ユーザー名はHelmfileの環境名から一意に生成され、環境別valuesやE2Eスクリプトへ個別に重複定義しません。

| ロール | ユーザー名 | パスワード変数 |
|---|---|---|
| 管理者 | `<env>-admin` | `TEST_ADMIN_PASSWORD` |
| サポート | `<env>-support` | `TEST_SUPPORT_PASSWORD` |
| 営業 | `<env>-sales` | `TEST_SALES_PASSWORD` |

例えばint環境では`int-admin`、`int-support`、`int-sales`です。パスワードの実値はGit管理外の`deploy/env/int.env`に置き、`deploy/env/int.env.example`は変数名を示す雛形としてのみ使います。

Helmのpost-install/post-upgrade bootstrap Jobは、有効な環境でこれらのRedmineユーザーを作成または更新します。prdは`app.testUsers.enabled: false`であり、E2Eスクリプトもprdの実行を拒否します。

### Playwrightの実行

デプロイ後のPlaywright E2Eは次のコマンドで実行します。

```bash
./scripts/helmfile-e2e.sh int
./scripts/helmfile-e2e.sh dev e2e/ticket-creation.spec.ts
```

共有クラスタなど既定ホスト名を変更した場合は `E2E_BASE_URL=https://... ./scripts/helmfile-e2e.sh stg` のように上書きします。prd はスクリプト側でも拒否し、テストユーザーを作りません。

既定の `.localhost` Ingressへ接続できない場合、E2EスクリプトはFrontend Serviceを `127.0.0.1:18080` へ一時的にport-forwardしてテストを続行します。ポートは `E2E_PORT_FORWARD_PORT` で変更できます。明示的に `E2E_BASE_URL` を設定した場合は自動フォールバックしません。

### ログインできない場合

まず入力値と定義元を確認します。

```bash
./scripts/helmfile-deploy.sh int info
kubectl -n support-ticket-portal-int get job,pod
```

bootstrap Jobは成功後に自動削除されるため、Jobが表示されないこと自体は異常ではありません。ユーザーの存在と有効状態をパスワードを表示せずに確認する場合は、次を実行します。

```bash
kubectl -n support-ticket-portal-int exec deployment/redmine -- \
  bundle exec rails runner \
  'puts User.where(login: %w[int-admin int-support int-sales]).pluck(:login, :status)'
```

Redmineのstatus `1`は有効です。ユーザーが存在しない場合、`deploy/env/int.env`のパスワードを確認してから`./scripts/helmfile-deploy.sh int sync`を再実行し、bootstrap Jobを実行します。

## 検証と保守

```bash
make helm-validate
```

この検証は chart の lint、4 環境の render、および Compose/Helm が共有する Redmine bootstrap スクリプトの同期を確認します。`scripts/bootstrap_redmine.rb` を変更した場合は `deploy/chart/files/bootstrap_redmine.rb` に同じ変更を反映してください。

さらに、環境ごとのTraefik導入有無とIngressClass、URL規則、テストユーザー名、stg/prdの固定済みobservabilityイメージタグを検証します。

## 導入時に確定する値

実クラスタへ適用する前に、次を確定してください。

1. Backend/Frontend のコンテナレジストリと pull 認証方式
2. 環境別の実ドメイン、Traefik の IngressClass 名、DNS の管理先
3. TLS の発行方法と Secret 名
4. StorageClass、PVC 容量、バックアップ/リストア方針
5. 本番の replica/resource requests/limits、Alloyの外部OTLP転送先と認証・TLS要件
6. `.env` の代わりに External Secrets、SOPS、Vault 等を使うか
