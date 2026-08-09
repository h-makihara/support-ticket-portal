#!/usr/bin/env bash

# Shared environment conventions for Helmfile deployment and E2E scripts.
# This file is sourced by other scripts; do not execute it directly.

PORTAL_ROOT_DIR="${PORTAL_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

portal_yaml_scalar() {
  local value="$1"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

portal_yaml_value() {
  local file="$1"
  local section="$2"
  local key="$3"

  awk -v section="$section" -v key="$key" '
    $0 == section ":" { in_section = 1; next }
    in_section && /^[^ ]/ { exit }
    in_section && $1 == key ":" { print $2; exit }
  ' "$file"
}

portal_yaml_nested_value() {
  local file="$1"
  local section="$2"
  local subsection="$3"
  local key="$4"

  awk -v section="$section" -v subsection="$subsection" -v key="$key" '
    $0 == section ":" { in_section = 1; next }
    in_section && /^[^ ]/ { exit }
    in_section && $0 == "  " subsection ":" { in_subsection = 1; next }
    in_subsection && /^  [^ ]/ { exit }
    in_subsection && $1 == key ":" { print $2; exit }
  ' "$file"
}

portal_select_environment() {
  local environment="${1:-}"
  local allow_production="${2:-true}"

  case "$environment" in
    int|dev|stg) ;;
    prd)
      if [[ "$allow_production" != "true" ]]; then
        echo "prd is not allowed for this command" >&2
        return 2
      fi
      ;;
    *)
      echo "environment must be one of: int, dev, stg, prd" >&2
      return 2
      ;;
  esac

  PORTAL_ENVIRONMENT="$environment"
  PORTAL_NAMESPACE="support-ticket-portal-$environment"
  PORTAL_VALUES_FILE="$PORTAL_ROOT_DIR/deploy/environments/$environment.yaml"
  PORTAL_CHART_VALUES_FILE="$PORTAL_ROOT_DIR/deploy/chart/values.yaml"
  PORTAL_ENV_FILE="$PORTAL_ROOT_DIR/deploy/env/$environment.env"

  local url_namespace url_domain portal_host redmine_host portal_tls redmine_tls
  url_namespace="$(portal_environment_value url namespace)"
  url_domain="$(portal_environment_value url domain)"
  [[ -n "$url_namespace" ]] || url_namespace="$(portal_chart_value url namespace)"
  [[ -n "$url_domain" ]] || url_domain="$(portal_chart_value url domain)"
  PORTAL_URL_NAMESPACE="$(portal_yaml_scalar "$url_namespace")"
  PORTAL_URL_DOMAIN="$(portal_yaml_scalar "$url_domain")"

  portal_host="$(portal_yaml_scalar "$(portal_environment_value ingress host)")"
  redmine_host="$(portal_yaml_scalar "$(portal_environment_value redmineIngress host)")"
  [[ -n "$portal_host" ]] || portal_host="$(portal_yaml_scalar "$(portal_chart_value ingress host)")"
  [[ -n "$redmine_host" ]] || redmine_host="$(portal_yaml_scalar "$(portal_chart_value redmineIngress host)")"
  [[ -n "$portal_host" ]] || portal_host="$PORTAL_URL_NAMESPACE-$environment-portal.$PORTAL_URL_DOMAIN"
  [[ -n "$redmine_host" ]] || redmine_host="$PORTAL_URL_NAMESPACE-$environment-redmine.$PORTAL_URL_DOMAIN"

  portal_tls="$(portal_nested_environment_value ingress tls enabled)"
  redmine_tls="$(portal_nested_environment_value redmineIngress tls enabled)"
  [[ -n "$portal_tls" ]] || portal_tls="$(portal_chart_nested_value ingress tls enabled)"
  [[ -n "$redmine_tls" ]] || redmine_tls="$(portal_chart_nested_value redmineIngress tls enabled)"
  PORTAL_URL="$(if [[ "$portal_tls" == "true" ]]; then printf https; else printf http; fi)://$portal_host"
  PORTAL_REDMINE_URL="$(if [[ "$redmine_tls" == "true" ]]; then printf https; else printf http; fi)://$redmine_host"
  PORTAL_TEST_ADMIN_USERNAME="$environment-admin"
  PORTAL_TEST_SUPPORT_USERNAME="$environment-support"
  PORTAL_TEST_SALES_USERNAME="$environment-sales"
}

portal_load_secret_env() {
  if [[ ! -f "$PORTAL_ENV_FILE" ]]; then
    echo "missing $PORTAL_ENV_FILE (copy deploy/env/$PORTAL_ENVIRONMENT.env.example first)" >&2
    return 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$PORTAL_ENV_FILE"
  set +a
}

portal_require_deploy_secrets() {
  local required=(REDMINE_API_KEY REDMINE_SECRET_KEY_BASE POSTGRES_PASSWORD)
  local name value

  if [[ "$PORTAL_ENVIRONMENT" != "prd" ]]; then
    required+=(TEST_ADMIN_PASSWORD TEST_SUPPORT_PASSWORD TEST_SALES_PASSWORD)
  fi

  for name in "${required[@]}"; do
    value="${!name:-}"
    if [[ -z "$value" || "$value" == replace-with-* ]]; then
      echo "$name must be set to a non-placeholder value in $PORTAL_ENV_FILE" >&2
      return 1
    fi
  done
}

portal_environment_value() {
  local section="$1"
  local key="$2"
  portal_yaml_value "$PORTAL_VALUES_FILE" "$section" "$key"
}

portal_nested_environment_value() {
  local section="$1"
  local subsection="$2"
  local key="$3"
  portal_yaml_nested_value "$PORTAL_VALUES_FILE" "$section" "$subsection" "$key"
}

portal_chart_value() {
  local section="$1"
  local key="$2"
  portal_yaml_value "$PORTAL_CHART_VALUES_FILE" "$section" "$key"
}

portal_chart_nested_value() {
  local section="$1"
  local subsection="$2"
  local key="$3"
  portal_yaml_nested_value "$PORTAL_CHART_VALUES_FILE" "$section" "$subsection" "$key"
}

portal_print_info() {
  local test_users_enabled traefik_install bundled_class external_class
  test_users_enabled="$(portal_nested_environment_value app testUsers enabled)"
  traefik_install="$(portal_environment_value traefik install)"
  bundled_class="$(portal_environment_value traefik bundledIngressClass)"
  external_class="$(portal_environment_value traefik externalIngressClass)"

  echo "Environment : $PORTAL_ENVIRONMENT"
  echo "Namespace   : $PORTAL_NAMESPACE"
  echo "Portal URL  : $PORTAL_URL"
  echo "Redmine URL : $PORTAL_REDMINE_URL"
  if [[ "$traefik_install" == "true" ]]; then
    echo "Traefik     : bundled ($bundled_class)"
  else
    echo "Traefik     : external ($external_class)"
  fi
  echo "Values      : $PORTAL_VALUES_FILE"
  echo "Secrets     : $PORTAL_ENV_FILE"

  if [[ "$test_users_enabled" == "true" ]]; then
    echo "Test users  : enabled"
    echo "  admin     : $PORTAL_TEST_ADMIN_USERNAME (TEST_ADMIN_PASSWORD)"
    echo "  support   : $PORTAL_TEST_SUPPORT_USERNAME (TEST_SUPPORT_PASSWORD)"
    echo "  sales     : $PORTAL_TEST_SALES_USERNAME (TEST_SALES_PASSWORD)"
  else
    echo "Test users  : disabled"
  fi
}
