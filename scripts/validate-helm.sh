#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck source=scripts/lib/helmfile-env.sh
source "$ROOT_DIR/scripts/lib/helmfile-env.sh"

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local message="$3"
  if ! grep -Fq "$needle" <<<"$haystack"; then
    echo "$message" >&2
    exit 1
  fi
}

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
  portal_select_environment "$environment"
  rendered="$(helmfile --environment "$environment" template)"
  traefik_install="$(portal_environment_value traefik install)"
  bundled_class="$(portal_environment_value traefik bundledIngressClass)"
  external_class="$(portal_environment_value traefik externalIngressClass)"
  test_users_enabled="$(portal_nested_environment_value app testUsers enabled)"

  if [[ "$traefik_install" == "true" ]]; then
    expected_ingress_class="$bundled_class"
    assert_contains "$rendered" 'kind: IngressClass' "$environment must render the bundled Traefik IngressClass"
    assert_contains "$rendered" "name: $bundled_class" "$environment must render IngressClass $bundled_class"
  elif grep -q 'app.kubernetes.io/name: traefik' <<<"$rendered"; then
    echo "$environment must not render the bundled Traefik release" >&2
    exit 1
  else
    expected_ingress_class="$external_class"
  fi
  assert_contains "$rendered" "ingressClassName: $expected_ingress_class" "$environment must use IngressClass $expected_ingress_class"
  assert_contains "$rendered" "host: \"${PORTAL_URL#*://}\"" "$environment Portal URL must match the shared script convention"

  assert_contains "$rendered" "value: \"$test_users_enabled\"" "$environment must render its test-user enablement"
  if [[ "$test_users_enabled" == "true" ]]; then
    assert_contains "$rendered" "value: \"$environment-admin\"" "$environment must render its admin test user"
    assert_contains "$rendered" "value: \"$environment-support\"" "$environment must render its support test user"
    assert_contains "$rendered" "value: \"$environment-sales\"" "$environment must render its sales test user"
  fi

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
