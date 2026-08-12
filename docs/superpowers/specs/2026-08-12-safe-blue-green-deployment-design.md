# Safe Blue-Green Deployment Design

## Goal

Frontend と Backend を同じ slot の組として事前検証してから切り替えられる Blue-Green 構成にし、旧単一 Deployment からの初回更新でも Service の endpoint を失わないようにする。また、利用者が初回配置時に Kubernetes Namespace を選択でき、省略時は従来の `support-ticket-portal-<environment>` を使う。

## Scope

- Frontend と Backend の Blue-Green 化
- 旧 `frontend` / `backend` Deployment からの安全な移行
- inactive slot の結合 smoke test / E2E
- deploy / E2E / backup / destroy における Namespace の一貫した指定
- Helm render と shell behavior の構造的な回帰テスト

PostgreSQL、Redis、Redmine、Secret、bootstrap Job、observability gateway は slot 間で共有する。Namespace 間のデータ移行や、同じ environment を複数 Namespace へ並行配置する機能は対象外とする。

## Namespace Contract

コマンドの Namespace は「その environment を最初に配置する場所」であり、preview 環境の複製識別子ではない。

- 未指定時: `support-ticket-portal-<environment>`
- 指定時: 利用者が指定した DNS label（小文字英数字と `-`、最大63文字）
- Helm release 名、Ingress host、Traefik IngressClass 名は environment 基準のまま維持する
- 同一 environment の release が別 Namespace に存在する状態で `sync` しようとした場合は、デプロイスクリプトが適用前に停止して競合を説明する
- `destroy` は指定された Namespace だけを対象とし、暗黙に別 Namespace の release を削除しない
- Namespace の変更は単純な Helm upgrade ではなく、PVC と ingress の移設を伴う別運用であることを文書化する

`info` と `template` はクラスタ接続なしでも利用できる状態を維持する。クラスタ上の重複 release 検査は変更系の `sync` で実施する。`diff` は指定先の差分確認を妨げないよう警告に留める。

## Steady-State Architecture

### Workloads

Frontend と Backend は `blue` / `green` の2 slotを持つ。

- Deployment: `frontend-blue`, `frontend-green`, `backend-blue`, `backend-green`
- slot label: `app.kubernetes.io/slot: blue|green`
- 各 slot は独立した Backend / Frontend image tag を持つ
- PostgreSQL、Redis、Redmine、Secret は両 slot から共有する

### Services and Routing

各 slot に固定された Service を作る。

- `backend-blue` → blue Backend Pod
- `backend-green` → green Backend Pod
- `frontend-blue` → blue Frontend Pod
- `frontend-green` → green Frontend Pod

安定した外部入口として `frontend` Service を維持し、`blueGreen.activeSlot` の Frontend Podだけを選択する。Portal Ingress は引き続き `frontend` を参照する。

Frontend Podには slot 固有の Nginx ConfigMap をmountする。blue Frontendの`/api/`は`backend-blue`、green Frontendは`backend-green`へproxyする。このためPortalの切替は`frontend` Service selectorの1箇所だけで完結し、FrontendとBackendの世代が混在しない。

Backend Ingress を有効にする環境では、安定した `backend` Service を残して `activeSlot` のBackend Podを選択する。これはAPIの直接公開用であり、Portal内通信には使わない。Helmが`frontend`と`backend`のselectorを別々に更新する短時間はdirect Backend APIだけがPortalと異なるslotを向く可能性があるため、両世代のAPI互換性を切替条件とする。

### Inactive Slot Verification

inactive slot の `frontend-<slot>` Service をport-forwardすれば、同じslotのBackendまで含む結合経路を確認できる。

```bash
kubectl -n "$NAMESPACE" port-forward service/frontend-green 18081:80
curl --fail http://127.0.0.1:18081/
curl --fail http://127.0.0.1:18081/api/health
```

E2E script は `--namespace <namespace>` と `--slot blue|green` を受け付ける。`--slot` 指定時は対象slotのFrontend Serviceへport-forwardし、Ingressを使わずにテストする。省略時は従来どおり安定Frontendを検証する。

## Legacy Upgrade Migration

旧chartにはslot labelのない`frontend` / `backend` Deploymentと、slot selectorのない同名Serviceが存在する。Serviceへslot selectorを先に追加すると新Deploymentがreadyになるまでendpointが0になるため、`sync`は次の順序を守る。

1. デプロイスクリプトが対象releaseの存在と、旧Deploymentにslot labelがないことをread-onlyで確認する。
2. 旧構成の場合、Helmfileをmigration phaseで同期する。
   - 旧Deployment名とimmutable selectorを維持する
   - Pod templateへ`app.kubernetes.io/slot: blue`を追加してrolloutする
   - 安定Service selectorにはslotを追加しない
   - green workloadとslot別Serviceはまだ作らない
3. Helmfileの`wait`により、旧Deploymentの全Podがblue label付きでreadyになるまで待つ。
4. coexist phaseを同期する。
   - blue / green workloadとslot別Serviceを作る
   - 旧Deploymentを同じmanifest内に残す
   - 安定Service selectorにはslotを追加せず、旧Podへの経路を維持する
5. Helmfileの`wait`により、新しいblue / green Deploymentがreadyになるまで待つ。
6. 通常のactive phaseを同期する。
   - `frontend-blue` / `backend-blue` とgreen workloadを作る
   - slot別Serviceを作る
   - 安定Serviceをactive slotへ切り替える
   - 旧Deploymentをmanifestから除き、Helmに削除させる

migration / coexist phaseは内部的な一時overrideであり、environment valuesへ恒久設定しない。新規releaseでは旧Deploymentが存在しないため両phaseを省略し、通常phaseを1回だけ同期する。`diff`、`template`、`destroy`ではmigrationを自動実行しない。

通常phaseの適用順序だけでは、新しいblue Podのready前にService切替や旧Deployment削除が起きる可能性がある。そのためmigration phaseで旧Podにblue labelを付け、coexist phaseで旧Podを残したまま新Deploymentをreadyにする。active phase開始時には新active Podがすでにreadyであり、Service selectorの変更後に旧Deploymentが削除されてもendpointを維持できる。

## Deployment Workflow

通常の切替は2回の同期で行う。

1. `activeSlot`を変えず、inactive slotのFrontend / Backend tagを更新して`sync`する。
2. inactive slotのrollout statusとslot Frontend経由のsmoke testまたはE2Eを実行する。
3. `activeSlot`をinactive slotへ変更して再度`sync`する。
4. 安定URLで確認する。

rollbackは`activeSlot`を直前のslotへ戻して`sync`する。データベースmigrationは両slotから同時利用できるexpand/contract方式など、少なくとも切替期間中は後方互換にする。

## Script Interfaces

### Deploy

既存互換の位置引数を維持する。

```text
helmfile-deploy.sh <environment> [sync|diff|template|destroy|info] [namespace]
```

4個以上の引数はusageと終了コード2で拒否する。`sync`だけがlegacy migrationと別Namespaceの同一release検査を行う。

### E2E

Playwright引数と衝突しない明示optionを追加する。

```text
helmfile-e2e.sh <environment> [--namespace <namespace>] [--slot blue|green] [playwright arguments...]
```

Namespace省略時はdeploy scriptと同じ既定値を使う。

## Error Handling

- 不正なenvironment、Namespace、slot、過剰引数は適用前に終了コード2で失敗させる
- 別Namespaceに同名releaseがある`sync`は、検出したNamespaceを表示して適用前に失敗させる
- migration phaseが失敗した場合は通常phaseを実行しない
- inactive slotのready確認やE2Eが失敗した場合、利用者は`activeSlot`を変更しない
- Helmfileの`atomic`と`wait`は各phase内の失敗rollbackとreadiness待ちに利用するが、複数Service更新のtransactionとは表現しない

## Testing Strategy

テストは文字列の存在だけでなく、rendered YAMLをresource kind/name単位で抽出して検証する。

1. default active blue / active greenの両方をrenderする
2. 安定Frontend Serviceが指定slotだけを選ぶことを確認する
3. slot別Serviceが同色Podを選ぶことを確認する
4. 各FrontendのNginx設定が同色Backend Serviceを参照することを確認する
5. distinct tagを指定し、4 Deploymentが正しいimageを使うことを確認する
6. 不正active slotと不足slotをrender errorにする
7. migration phaseで旧Deployment名・immutable selector・slotなしService selector・blue Pod labelを確認する
8. deploy scriptをmock `helm` / `kubectl` / `helmfile`で実行し、旧releaseだけmigration / coexist / activeの3段階sync、新規releaseはactiveの1段階sync、別Namespace競合は適用前停止になることを確認する
9. custom Namespaceが全release namespace、Traefik watch list、E2E port-forwardへ伝播することを確認する
10. int / dev / stg / prdの既存Helm検証を維持する

可能ならDisposable clusterで直前commitのchartをinstallしてから新scriptでupgradeし、切替中にFrontend / Backend ServiceのEndpointSliceが0件にならないことを統合確認する。このクラスタテストをローカル必須条件にはせず、CIまたはリリース前検証として文書化する。

## Documentation Updates

- `docs/helmfile.md`: 初回自動migration、通常の切替、inactive E2E、rollback、Namespace契約を記載
- backup / restore / destroyの全コマンドへ`"$NAMESPACE"`を渡す
- custom Namespaceは並行preview用途ではなく、初回配置先の選択であることを明記
- 常時2slot分のFrontend / Backend resourceを消費することを明記
- `deploy/README.md`とMakefile helpを新しいE2E optionと運用契約へ合わせる

## Acceptance Criteria

- 旧単一Deploymentからのscripted `sync`で、安定Serviceに一致するready Podが常に存在する移行順序になっている
- Portal経由のFrontendとBackendは常に同じslotになる
- inactive slotをPortalと同じ経路で結合テストできる
- active slotをvaluesだけで切替・rollbackできる
- Namespace省略時の既存挙動を維持する
- custom Namespaceがdeploy、E2E、backup、destroyで一貫する
- 同一environmentの別Namespace重複を`sync`前に検出する
- 全4環境のlint/renderと追加されたscript/renderテストが通る
