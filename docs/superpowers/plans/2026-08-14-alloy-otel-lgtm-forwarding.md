# Alloy to OTel-LGTM Forwarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure the int Alloy gateway to forward logs, metrics, and traces to the separately deployed OTel-LGTM service over internal Kubernetes DNS and OTLP/gRPC.

**Architecture:** Preserve the existing Backend-to-sidecar and sidecar-to-Alloy OTLP/HTTP hops. Add a protocol-aware external exporter contract to the Helm chart, select OTLP/gRPC only for int, and keep dev/stg/prd on the existing OTLP/HTTP path.

**Tech Stack:** Helm 3 templates, Helmfile, Grafana Alloy River configuration, Kubernetes Service DNS, Ruby rendered-manifest assertions, Bash validation.

## Global Constraints

- Keep the Portal and OTel-LGTM Namespaces, Helm releases, and repositories separate.
- Use `otel-lgtm.otel-lgtm-int.svc.cluster.local:4317` from the Alloy Pod; do not use `otel-lgtm-int.localhost` for Pod-to-Pod forwarding.
- Use plaintext OTLP/gRPC only in int with `insecure: true`.
- Preserve the existing OTLP/HTTP behavior for dev, stg, and prd.
- Do not deploy or sync the chart as part of the code change.
- Follow test-driven development: observe each focused test fail before changing production configuration.

## File Structure

- `deploy/chart/values.yaml`: defines the default `observability.externalOtlp` values contract.
- `deploy/chart/templates/observability.yaml`: validates the contract and renders either the Alloy OTLP/HTTP or OTLP/gRPC exporter.
- `deploy/environments/int.yaml`: selects the internal OTel-LGTM Service DNS and plaintext OTLP/gRPC for int.
- `tests/helm/manifest_assertions.rb`: performs focused, parsed-manifest assertions for both exporter variants and invalid values.
- `scripts/validate-helm.sh`: runs the focused observability assertions and checks the selected exporter in every Helmfile environment.
- `docs/helmfile.md`: documents operator configuration and the int-specific destination.
- `docs/architecture.md`: documents the actual protocol and Namespace boundary in the runtime data path.

---

### Task 1: Protocol-aware Alloy exporter

**Files:**
- Modify: `tests/helm/manifest_assertions.rb`
- Modify: `scripts/validate-helm.sh`
- Modify: `deploy/chart/values.yaml`
- Modify: `deploy/chart/templates/observability.yaml`

**Interfaces:**
- Consumes: Helm values at `.Values.observability.externalOtlp.protocol`, `.endpoint`, and `.insecure`.
- Produces: an Alloy ConfigMap whose `config.alloy` contains exactly one external exporter, named `otelcol.exporter.otlphttp.external` for `http` or `otelcol.exporter.otlp.external` for `grpc`.
- Produces: the test entry point `ruby tests/helm/manifest_assertions.rb observability`.

- [ ] **Step 1: Write focused exporter and validation assertions**

Add a helper that returns the rendered Alloy configuration:

```ruby
def alloy_config(documents)
  resource(documents, "ConfigMap", "alloy-config").fetch("data").fetch("config.alloy")
end
```

Add an `assert_observability` mode with these exact checks:

```ruby
def assert_observability
  http = alloy_config(documents_for([]))
  raise "default must render OTLP/HTTP exporter" unless http.include?('otelcol.exporter.otlphttp "external"')
  raise "default batch must target OTLP/HTTP exporter" unless http.include?("logs    = [otelcol.exporter.otlphttp.external.input]")
  raise "default endpoint missing" unless http.include?('endpoint = "http://observability.example.invalid:4318"')
  raise "default must not render OTLP/gRPC exporter" if http.include?('otelcol.exporter.otlp "external"')

  grpc = alloy_config(documents_for([
    "observability.externalOtlp.protocol=grpc",
    "observability.externalOtlp.endpoint=otel-lgtm.otel-lgtm-int.svc.cluster.local:4317",
    "observability.externalOtlp.insecure=true"
  ]))
  raise "gRPC exporter missing" unless grpc.include?('otelcol.exporter.otlp "external"')
  raise "gRPC batch target missing" unless grpc.include?("logs    = [otelcol.exporter.otlp.external.input]")
  raise "gRPC endpoint missing" unless grpc.include?('endpoint = "otel-lgtm.otel-lgtm-int.svc.cluster.local:4317"')
  raise "gRPC plaintext TLS setting missing" unless grpc.match?(/tls \{\s+insecure = true\s+\}/m)
  raise "gRPC must not render OTLP\/HTTP exporter" if grpc.include?('otelcol.exporter.otlphttp "external"')

  assert_invalid_render(
    ["observability.externalOtlp.protocol=invalid"],
    "observability.externalOtlp.protocol must be http or grpc"
  )
  assert_invalid_render(
    ["observability.externalOtlp.endpoint="],
    "observability.externalOtlp.endpoint is required"
  )
end
```

Extend the CLI case with:

```ruby
when "observability" then assert_observability
```

Add this focused invocation after the three blue-green modes in `scripts/validate-helm.sh`:

```bash
ruby tests/helm/manifest_assertions.rb observability
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
ruby tests/helm/manifest_assertions.rb observability
```

Expected: FAIL because `observability.externalOtlp.protocol` does not exist and the chart always renders `otelcol.exporter.otlphttp`.

- [ ] **Step 3: Replace the scalar default with the protocol-aware values contract**

Replace `observability.externalOtlpEndpoint` in `deploy/chart/values.yaml` with:

```yaml
observability:
  enabled: true
  externalOtlp:
    protocol: http
    # Alloy appends the standard /v1/{logs,metrics,traces} paths for OTLP/HTTP.
    endpoint: "http://observability.example.invalid:4318"
    # Set true only for plaintext OTLP/gRPC inside a trusted cluster.
    insecure: false
  debugLogFlagAttribute: "ticket.portal.debug_enabled"
```

- [ ] **Step 4: Validate values and render the selected Alloy exporter**

At the beginning of the enabled block in `deploy/chart/templates/observability.yaml`, bind and validate the values:

```gotemplate
{{- $externalOtlp := .Values.observability.externalOtlp -}}
{{- $protocol := required "observability.externalOtlp.protocol is required" $externalOtlp.protocol -}}
{{- if not (has $protocol (list "http" "grpc")) -}}
{{- fail "observability.externalOtlp.protocol must be http or grpc" -}}
{{- end -}}
{{- $endpoint := required "observability.externalOtlp.endpoint is required" $externalOtlp.endpoint -}}
```

In the batch processor, render all three outputs using the same conditional target:

```gotemplate
        logs    = [{{ if eq $protocol "grpc" }}otelcol.exporter.otlp.external.input{{ else }}otelcol.exporter.otlphttp.external.input{{ end }}]
        metrics = [{{ if eq $protocol "grpc" }}otelcol.exporter.otlp.external.input{{ else }}otelcol.exporter.otlphttp.external.input{{ end }}]
        traces  = [{{ if eq $protocol "grpc" }}otelcol.exporter.otlp.external.input{{ else }}otelcol.exporter.otlphttp.external.input{{ end }}]
```

Replace the fixed exporter with:

```gotemplate
{{- if eq $protocol "grpc" }}
    otelcol.exporter.otlp "external" {
      client {
        endpoint = {{ $endpoint | quote }}
        tls {
          insecure = {{ $externalOtlp.insecure }}
        }
      }
    }
{{- else }}
    otelcol.exporter.otlphttp "external" {
      client {
        endpoint = {{ $endpoint | quote }}
      }
    }
{{- end }}
```

- [ ] **Step 5: Run the focused test and verify GREEN**

Run:

```bash
ruby tests/helm/manifest_assertions.rb observability
helm lint deploy/chart \
  --set secrets.redmineApiKey=x \
  --set secrets.redmineSecretKeyBase=x \
  --set secrets.postgresPassword=x \
  --set secrets.testAdminPassword=x \
  --set secrets.testSupportPassword=x \
  --set secrets.testSalesPassword=x
```

Expected: the observability assertions pass and Helm reports `1 chart(s) linted, 0 chart(s) failed`.

- [ ] **Step 6: Commit the protocol-aware exporter**

```bash
git add deploy/chart/values.yaml deploy/chart/templates/observability.yaml tests/helm/manifest_assertions.rb scripts/validate-helm.sh
git commit -m "feat: support OTLP gRPC Alloy forwarding"
```

---

### Task 2: Select the internal OTel-LGTM destination for int

**Files:**
- Modify: `deploy/environments/int.yaml`
- Modify: `scripts/validate-helm.sh`

**Interfaces:**
- Consumes: the `observability.externalOtlp` contract from Task 1.
- Produces: int Helmfile output targeting `otel-lgtm.otel-lgtm-int.svc.cluster.local:4317` with OTLP/gRPC and `insecure = true`.
- Preserves: dev/stg/prd Helmfile output with `otelcol.exporter.otlphttp "external"` and the default `.invalid` endpoint.

- [ ] **Step 1: Add four-environment exporter assertions before changing int values**

Within the existing environment loop in `scripts/validate-helm.sh`, after image assertions, add:

```bash
  if [[ "$environment" == "int" ]]; then
    assert_contains "$rendered" 'otelcol.exporter.otlp "external"' "int must render the OTLP/gRPC exporter"
    assert_contains "$rendered" 'endpoint = "otel-lgtm.otel-lgtm-int.svc.cluster.local:4317"' "int must target the internal OTel-LGTM Service"
    assert_contains "$rendered" 'insecure = true' "int internal OTLP/gRPC must use plaintext"
    if grep -Fq 'otelcol.exporter.otlphttp "external"' <<<"$rendered"; then
      echo "int must not render the external OTLP/HTTP exporter" >&2
      exit 1
    fi
  else
    assert_contains "$rendered" 'otelcol.exporter.otlphttp "external"' "$environment must preserve OTLP/HTTP forwarding"
    assert_contains "$rendered" 'endpoint = "http://observability.example.invalid:4318"' "$environment must preserve the default OTLP/HTTP endpoint"
  fi
```

- [ ] **Step 2: Run the full Helm validation and verify RED at int**

Run:

```bash
./scripts/validate-helm.sh
```

Expected: FAIL with `int must render the OTLP/gRPC exporter` because int still inherits the HTTP default.

- [ ] **Step 3: Configure int to use internal Kubernetes Service DNS**

Add to `deploy/environments/int.yaml`:

```yaml
observability:
  externalOtlp:
    protocol: grpc
    endpoint: "otel-lgtm.otel-lgtm-int.svc.cluster.local:4317"
    insecure: true
```

- [ ] **Step 4: Run focused int and non-int renders**

Load the validation-only secret values, then render each environment:

```bash
export REDMINE_API_KEY=validation-api-key
export REDMINE_SECRET_KEY_BASE=validation-secret-key-base
export POSTGRES_PASSWORD=validation-postgres-password
export TEST_ADMIN_PASSWORD=validation-admin-password
export TEST_SUPPORT_PASSWORD=validation-support-password
export TEST_SALES_PASSWORD=validation-sales-password
helmfile --environment int template | rg 'otelcol.exporter.otlp|otel-lgtm\.otel-lgtm-int|insecure = true'
helmfile --environment dev template | rg 'otelcol.exporter.otlphttp|observability\.example\.invalid'
helmfile --environment stg template | rg 'otelcol.exporter.otlphttp|observability\.example\.invalid'
helmfile --environment prd template | rg 'otelcol.exporter.otlphttp|observability\.example\.invalid'
```

Expected: int shows the gRPC exporter, internal Service DNS, and `insecure = true`; every other environment shows the OTLP/HTTP exporter and `.invalid` endpoint.

- [ ] **Step 5: Run the full Helm validation and verify GREEN**

Run:

```bash
./scripts/validate-helm.sh
```

Expected: `Helm/Helmfile validation passed for int, dev, stg, and prd`.

- [ ] **Step 6: Commit the int destination**

```bash
git add deploy/environments/int.yaml scripts/validate-helm.sh
git commit -m "feat: forward int telemetry to OTel LGTM"
```

---

### Task 3: Document the separated forwarding path

**Files:**
- Modify: `docs/helmfile.md`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: the final values keys and endpoint from Tasks 1 and 2.
- Produces: operator guidance for choosing HTTP versus gRPC and architecture documentation that distinguishes host-only `.localhost` access from Pod-internal Service DNS.

- [ ] **Step 1: Update Helmfile operator documentation**

Replace the scalar example in `docs/helmfile.md` with:

```yaml
observability:
  externalOtlp:
    protocol: grpc
    endpoint: "otel-lgtm.otel-lgtm-int.svc.cluster.local:4317"
    insecure: true
  debugLogFlagAttribute: "ticket.portal.debug_enabled"
```

Document these exact rules immediately after the example:

- `protocol` accepts only `http` or `grpc`.
- OTLP/HTTP endpoints include the scheme and omit `/v1/logs`, `/v1/metrics`, and `/v1/traces`.
- OTLP/gRPC endpoints use `host:port`; `insecure: true` is limited to trusted plaintext cluster traffic.
- int uses the cross-Namespace Service DNS `otel-lgtm.otel-lgtm-int.svc.cluster.local:4317`.
- `otel-lgtm-int.localhost:4317` remains a host-machine entry point and must not be used from an Alloy Pod because `.localhost` resolves to that Pod's own loopback.

- [ ] **Step 2: Update the architecture data path**

Change the final two hops in `docs/architecture.md` to:

```text
                                └─ Grafana Alloy (gateway Pod)
                                     └─ OTLP/gRPC (int, Kubernetes Service DNS)
                                          └─ OTel-LGTM (otel-lgtm-int Namespace)
```

In the observability section, state that Backend-to-sidecar and sidecar-to-Alloy remain OTLP/HTTP, while int Alloy-to-OTel-LGTM uses plaintext OTLP/gRPC over internal Service DNS. State that dev/stg/prd retain the environment-configured OTLP/HTTP exporter.

- [ ] **Step 3: Verify documentation matches implementation**

Run:

```bash
rg -n "externalOtlpEndpoint" deploy docs tests scripts
rg -n "externalOtlp|otel-lgtm\.otel-lgtm-int|OTLP/gRPC|localhost" docs/helmfile.md docs/architecture.md deploy/chart/values.yaml deploy/environments/int.yaml
git diff --check
```

Expected: the first command returns no matches; the second shows the new values keys, internal DNS, protocol explanation, and `.localhost` warning; `git diff --check` prints nothing.

- [ ] **Step 4: Run final verification**

Run:

```bash
ruby tests/helm/manifest_assertions.rb observability
./scripts/validate-helm.sh
git status --short
```

Expected: focused assertions and full validation pass; status lists only the two documentation files before the documentation commit.

- [ ] **Step 5: Commit documentation**

```bash
git add docs/helmfile.md docs/architecture.md
git commit -m "docs: explain Alloy OTel LGTM forwarding"
```

---

### Task 4: Final review and delivery

**Files:**
- Review: all files changed by Tasks 1-3

**Interfaces:**
- Consumes: the three independently committed deliverables.
- Produces: review evidence that the implementation satisfies the accepted design without deploying it.

- [ ] **Step 1: Review the complete change against the design**

Run:

```bash
git diff 4f63afc..HEAD -- deploy/chart deploy/environments/int.yaml tests/helm scripts/validate-helm.sh docs/helmfile.md docs/architecture.md
```

Verify that only int selects gRPC/internal DNS, no `.localhost` endpoint is rendered for Alloy, and no deployment command was added.

- [ ] **Step 2: Run clean final verification**

Run:

```bash
./scripts/validate-helm.sh
git diff --check 4f63afc..HEAD
git status --short --branch
```

Expected: validation passes, the diff check is silent, and the worktree is clean.

- [ ] **Step 3: Request code review**

Use `superpowers:requesting-code-review` to inspect the full implementation against `docs/superpowers/specs/2026-08-14-alloy-otel-lgtm-forwarding-design.md`. Address any Critical or Important findings with focused regression tests before reporting completion.
