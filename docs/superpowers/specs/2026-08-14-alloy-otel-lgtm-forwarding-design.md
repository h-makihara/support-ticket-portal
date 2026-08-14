# Alloy to OTel-LGTM Forwarding Design

## Goal

`support-ticket-portal-int` NamespaceのAlloy gatewayから、別Namespaceで稼働するOTel-LGTMへログ・メトリクス・トレースをOTLP/gRPCで転送する。

## Current Environment

両システムは同じ`docker-desktop` Kubernetesクラスタ内で、次のようにNamespaceとHelm releaseが分離されている。

- 送信元: `support-ticket-portal-int` Namespaceの`alloy` Deployment
- 送信先: `otel-lgtm-int` Namespaceの`otel-lgtm` Service
- OTel-LGTM Service: OTLP/gRPC `4317`、OTLP/HTTP `4318`
- 検証済み内部DNS: `otel-lgtm.otel-lgtm-int.svc.cluster.local` → `10.96.157.18`

外部公開名`otel-lgtm-int.localhost`はホストマシンからの利用に残す。`.localhost`は各実行環境自身のloopbackを示すため、Alloy Podからの転送先には使用しない。

## Architecture

アプリBackendは従来どおりOTLP/HTTPでlocalhostのsidecar Collectorへ送る。sidecar Collectorは従来どおり同一NamespaceのAlloy ServiceへOTLP/HTTPで送る。変更するのはAlloyから外部backendへ出る最後のhopだけである。

```text
Backend
  -> sidecar Collector (:4318, OTLP/HTTP)
  -> Alloy Service (:4318, OTLP/HTTP)
  -> otel-lgtm.otel-lgtm-int.svc.cluster.local:4317 (OTLP/gRPC, plaintext)
  -> OTel-LGTM
```

Namespace、release、設定リポジトリは分離したまま、Kubernetes Service DNSを接続契約として使用する。Ingress Controller、LoadBalancer外部IP、Mac側のhosts設定には依存しない。

## Values Contract

現在の単一`observability.externalOtlpEndpoint`を、protocolを明示する構造へ置き換える。

```yaml
observability:
  externalOtlp:
    protocol: http
    endpoint: "http://observability.example.invalid:4318"
    insecure: false
```

設定の意味は次のとおり。

- `protocol`: `http`または`grpc`のみ
- `endpoint`: protocolに対応するAlloy exporterの接続先
- `insecure`: gRPCのplaintext接続時に`true`。HTTPではendpointのschemeを使用する

int環境は次の値で上書きする。

```yaml
observability:
  externalOtlp:
    protocol: grpc
    endpoint: "otel-lgtm.otel-lgtm-int.svc.cluster.local:4317"
    insecure: true
```

dev、stg、prdは既存既定値を継承し、OTLP/HTTP exporterをrenderする。これにより今回の変更はintの転送先だけに限定される。

## Alloy Rendering

`deploy/chart/templates/observability.yaml`はprotocolに応じてexporterとbatch processorの出力先を切り替える。

- `http`: `otelcol.exporter.otlphttp "external"`
- `grpc`: `otelcol.exporter.otlp "external"`

gRPC exporterでは次のRiver構造をrenderする。

```alloy
otelcol.exporter.otlp "external" {
  client {
    endpoint = "otel-lgtm.otel-lgtm-int.svc.cluster.local:4317"
    tls {
      insecure = true
    }
  }
}
```

`protocol`が`http`/`grpc`以外、またはendpointが空の場合はHelm templateを明示的に失敗させる。ConfigMap checksumは`observability`全体を対象としているため、設定変更時にAlloy Podは自動rolloutする。

## Failure and Security Behavior

- OTel-LGTMが停止中でもPortalのリクエスト処理を停止させない。Alloyが再送・エラー記録を担当する
- 送信先検査にIngressや外部DNSを使わない
- 現在のOTel-LGTMは平文・認証なしなので、`insecure: true`はintの信頼されたローカルクラスタ内だけで使用する
- 将来クラスタを分離する場合は、到達可能な実DNS名とTLSを用意し、`endpoint`と`insecure`だけを環境値で変更する

## Testing

静的検証で次をresource/config単位に確認する。

1. int renderは`otelcol.exporter.otlp`を使用する
2. int endpointは内部Service DNSの`:4317`
3. int gRPC TLS blockは`insecure = true`
4. dev/stg/prd renderは従来の`otelcol.exporter.otlphttp`を使用する
5. 不正protocolと空endpointはrender errorになる
6. 既存の4環境Helm/Helmfile検証を維持する

可能な場合はデプロイ後にAlloy rollout、Alloy log、Grafana上のログ/トレース受信を確認する。実クラスタへの`sync`はコード変更とは別の明示的な運用操作とし、自動実行しない。

## Documentation

`docs/helmfile.md`と`docs/architecture.md`を更新し、次を明記する。

- BackendからAlloyまではOTLP/HTTP
- intのAlloyからOTel-LGTMまではOTLP/gRPC
- Pod内では`.localhost`ではなくKubernetes Service DNSを使用する理由
- 他環境のprotocol/endpoint設定方法

## Acceptance Criteria

- int Helm renderのAlloy ConfigMapが内部DNSのOTLP/gRPC exporterを持つ
- dev/stg/prdのOTLP/HTTP exporterに回帰がない
- 不正設定がtemplate時に失敗する
- Chart lintと全4環境renderが成功する
- NamespaceとHelm releaseの分離状態を維持する
