#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! cmp -s scripts/bootstrap_redmine.rb deploy/chart/files/bootstrap_redmine.rb; then
  echo "deploy/chart/files/bootstrap_redmine.rb is out of sync with scripts/bootstrap_redmine.rb" >&2
  exit 1
fi

export REDMINE_API_KEY=validation-api-key
export REDMINE_SECRET_KEY_BASE=validation-secret-key-base
export POSTGRES_PASSWORD=validation-postgres-password
export TEST_ADMIN_PASSWORD=validation-admin-password
export TEST_SUPPORT_PASSWORD=validation-support-password
export TEST_SALES_PASSWORD=validation-sales-password

helm lint deploy/chart \
  --set secrets.redmineApiKey="$REDMINE_API_KEY" \
  --set secrets.redmineSecretKeyBase="$REDMINE_SECRET_KEY_BASE" \
  --set secrets.postgresPassword="$POSTGRES_PASSWORD" \
  --set secrets.testAdminPassword="$TEST_ADMIN_PASSWORD" \
  --set secrets.testSupportPassword="$TEST_SUPPORT_PASSWORD" \
  --set secrets.testSalesPassword="$TEST_SALES_PASSWORD"

for environment in int dev stg prd; do
  rendered="$(helmfile --environment "$environment" template)"
  expected_ingress_class="traefik"
  if [[ "$environment" == "int" ]]; then
    expected_ingress_class="traefik-int"
    grep -q 'kind: IngressClass' <<<"$rendered"
    grep -q 'name: traefik-int' <<<"$rendered"
  elif grep -q 'app.kubernetes.io/name: traefik' <<<"$rendered"; then
    echo "$environment must not render the bundled Traefik release" >&2
    exit 1
  fi
  grep -q "ingressClassName: $expected_ingress_class" <<<"$rendered"
  if [[ "$environment" == "stg" || "$environment" == "prd" ]]; then
    if grep -Eq 'image: "(otel/opentelemetry-collector-contrib|grafana/alloy):latest"' <<<"$rendered"; then
      echo "$environment must pin OpenTelemetry Collector and Alloy image tags" >&2
      exit 1
    fi
  else
    grep -q 'image: "otel/opentelemetry-collector-contrib:latest"' <<<"$rendered"
    grep -q 'image: "grafana/alloy:latest"' <<<"$rendered"
  fi
done

echo "Helm/Helmfile validation passed for int, dev, stg, and prd"
