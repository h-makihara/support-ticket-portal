#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_SCRIPT="$ROOT_DIR/scripts/helmfile-deploy.sh"
TEST_DIR="$(mktemp -d -t support-ticket-portal-deploy.XXXXXX)"
TEST_BIN="$TEST_DIR/bin"
TEST_ROOT="$TEST_DIR/root"
PORTAL_TEST_LOG="$TEST_DIR/commands.log"
FAILURES=0
DEPLOY_OUTPUT=""
DEPLOY_STATUS=0

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  FAILURES=$((FAILURES + 1))
}

write_fake_clis() {
  mkdir -p "$TEST_BIN" "$TEST_ROOT/deploy/env" "$TEST_ROOT/deploy/environments" "$TEST_ROOT/deploy/chart"
  cp "$ROOT_DIR/deploy/environments/dev.yaml" "$TEST_ROOT/deploy/environments/dev.yaml"
  cp "$ROOT_DIR/deploy/chart/values.yaml" "$TEST_ROOT/deploy/chart/values.yaml"
  cat >"$TEST_ROOT/deploy/env/dev.env" <<'EOF'
REDMINE_API_KEY=test-api-key
REDMINE_SECRET_KEY_BASE=test-secret-key
POSTGRES_PASSWORD=test-postgres-password
TEST_ADMIN_PASSWORD=test-admin-password
TEST_SUPPORT_PASSWORD=test-support-password
TEST_SALES_PASSWORD=test-sales-password
EOF

  cat >"$TEST_BIN/helm" <<'EOF'
#!/usr/bin/env bash
printf 'helm|%s|namespace=%s|phase=%s\n' "$*" "${PORTAL_NAMESPACE:-}" "${PORTAL_BLUE_GREEN_PHASE:-}" >>"$PORTAL_TEST_LOG"
if [[ "${1:-}" == list ]]; then
  if [[ -z "${FAKE_HELM_RELEASE_ROWS:-}" ]]; then
    printf '[]\n'
  else
    read -r name namespace <<<"$FAKE_HELM_RELEASE_ROWS"
    filter=''
    for argument in "$@"; do
      if [[ "$argument" == ^*'$' ]]; then
        filter="$argument"
      fi
    done
    if [[ "$filter" == "^${name}$" ]]; then
      printf '[{"name":"%s","namespace":"%s"}]\n' "$name" "$namespace"
    else
      printf '[]\n'
    fi
  fi
fi
EOF

  cat >"$TEST_BIN/kubectl" <<'EOF'
#!/usr/bin/env bash
printf 'kubectl|%s|namespace=%s|phase=%s\n' "$*" "${PORTAL_NAMESPACE:-}" "${PORTAL_BLUE_GREEN_PHASE:-}" >>"$PORTAL_TEST_LOG"
if [[ "${FAKE_LEGACY_DEPLOYMENTS:-}" == *backend* && "${FAKE_LEGACY_DEPLOYMENTS:-}" == *frontend* ]]; then
  printf 'deployment.apps/backend\ndeployment.apps/frontend\n'
  exit 0
fi
exit 1
EOF

  cat >"$TEST_BIN/helmfile" <<'EOF'
#!/usr/bin/env bash
printf 'helmfile|%s|namespace=%s|phase=%s\n' "$*" "${PORTAL_NAMESPACE:-}" "${PORTAL_BLUE_GREEN_PHASE:-}" >>"$PORTAL_TEST_LOG"
EOF

  chmod +x "$TEST_BIN/helm" "$TEST_BIN/kubectl" "$TEST_BIN/helmfile"
}

run_deploy() {
  : >"$PORTAL_TEST_LOG"
  if DEPLOY_OUTPUT="$(
    PATH="$TEST_BIN:$PATH" \
      PORTAL_ROOT_DIR="$TEST_ROOT" \
      PORTAL_TEST_LOG="$PORTAL_TEST_LOG" \
      PORTAL_BLUE_GREEN_PHASE= \
      "$DEPLOY_SCRIPT" "$@" 2>&1
  )"; then
    DEPLOY_STATUS=0
  else
    DEPLOY_STATUS=$?
  fi
}

assert_log_empty() {
  if [[ -s "$PORTAL_TEST_LOG" ]]; then
    fail "expected no CLI calls, got: $(cat "$PORTAL_TEST_LOG")"
  fi
}

assert_output_contains() {
  local expected="$1"
  if [[ "$DEPLOY_OUTPUT" != *"$expected"* ]]; then
    fail "expected output to contain '$expected', got: $DEPLOY_OUTPUT"
  fi
}

assert_exit_2() {
  "$@"
  if [[ "$DEPLOY_STATUS" -ne 2 ]]; then
    fail "expected exit 2, got $DEPLOY_STATUS"
  fi
}

assert_fails_before_helmfile() {
  "$@"
  if [[ "$DEPLOY_STATUS" -eq 0 ]]; then
    fail "expected deployment to fail"
  fi
  if grep -q '^helmfile|' "$PORTAL_TEST_LOG"; then
    fail "expected failure before helmfile, got: $(cat "$PORTAL_TEST_LOG")"
  fi
  assert_output_contains 'support-ticket-portal-dev already exists in namespace other-space; this command relocates one environment and does not create parallel copies'
}

assert_phases() {
  local expected="$*"
  local actual
  actual="$(sed -n 's/^helmfile|.*|phase=//p' "$PORTAL_TEST_LOG" | paste -sd ' ' -)"
  if [[ "$actual" != "$expected" ]]; then
    fail "expected phases '$expected', got '$actual'"
  fi
}

assert_single_unphased_helmfile() {
  local action="$1"
  local phase_calls
  phase_calls="$(sed -n 's/^helmfile|.*|phase=//p' "$PORTAL_TEST_LOG")"
  if [[ "$phase_calls" != '' ]]; then
    fail "$action must not invoke the three-phase state machine, got phases: $phase_calls"
  fi
  local helmfile_calls
  helmfile_calls="$(grep -c '^helmfile|' "$PORTAL_TEST_LOG" || true)"
  if [[ "$helmfile_calls" -ne 1 ]]; then
    fail "$action expected one unphased helmfile call, got: $(cat "$PORTAL_TEST_LOG")"
  fi
}

assert_no_helm_preflight() {
  local action="$1"
  if grep -q '^helm|' "$PORTAL_TEST_LOG"; then
    fail "$action must not inspect release inventory, got: $(cat "$PORTAL_TEST_LOG")"
  fi
}

write_fake_clis
export FAKE_HELM_RELEASE_ROWS FAKE_LEGACY_DEPLOYMENTS

FAKE_HELM_RELEASE_ROWS=''
FAKE_LEGACY_DEPLOYMENTS=''
run_deploy dev info
assert_log_empty
assert_output_contains 'Namespace   : support-ticket-portal-dev'

run_deploy dev info team-space
assert_output_contains 'Namespace   : team-space'

assert_exit_2 run_deploy dev sync team-space unexpected-fourth

FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev other-space'
assert_fails_before_helmfile run_deploy dev sync team-space

FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev team-space'
FAKE_LEGACY_DEPLOYMENTS='backend frontend'
run_deploy dev sync team-space
assert_phases migration coexist active

FAKE_LEGACY_DEPLOYMENTS=''
run_deploy dev sync team-space
assert_phases active

FAKE_LEGACY_DEPLOYMENTS='backend frontend'
FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev other-space'
run_deploy dev diff team-space
if [[ "$DEPLOY_STATUS" -ne 0 ]]; then
  fail "diff must warn without failing, got exit $DEPLOY_STATUS"
fi
assert_output_contains 'warning: support-ticket-portal-dev already exists in namespace other-space; this command relocates one environment and does not create parallel copies'
assert_single_unphased_helmfile diff

for action in template destroy; do
  run_deploy dev "$action" team-space
  assert_single_unphased_helmfile "$action"
  assert_no_helm_preflight "$action"
done

if [[ "$FAILURES" -ne 0 ]]; then
  exit 1
fi

echo "Deploy script tests passed"
