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
CALLER_PHASE=""

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
  case "${FAKE_HELM_MODE:-rows}" in
    fail)
      echo "simulated helm failure" >&2
      exit 42
      ;;
    malformed)
      printf 'not-json\n'
      exit 0
      ;;
    non-list)
      printf '{"name":"not-a-list"}\n'
      exit 0
      ;;
  esac

  filter=''
  for argument in "$@"; do
    if [[ "$argument" == ^*'$' ]]; then
      filter="$argument"
    fi
  done
  printf '['
  separator=''
  while read -r name namespace; do
    if [[ "$filter" == "^${name}$" ]]; then
      printf '%s{"name":"%s","namespace":"%s"}' "$separator" "$name" "$namespace"
      separator=,
    fi
  done <<<"${FAKE_HELM_RELEASE_ROWS:-}"
  printf ']\n'
fi
EOF

  cat >"$TEST_BIN/kubectl" <<'EOF'
#!/usr/bin/env bash
printf 'kubectl|%s|namespace=%s|phase=%s|tracker_migration=%s\n' "$*" "${PORTAL_NAMESPACE:-}" "${PORTAL_BLUE_GREEN_PHASE:-}" "${PORTAL_TRACKER_MIGRATION:-}" >>"$PORTAL_TEST_LOG"
case " $* " in
  *" get deployment "*)
    if [[ "$*" == *--selector=app.kubernetes.io/instance=* ]]; then
      printf '%s' "${FAKE_WRITER_DEPLOYMENTS:-}"
    elif [[ "$*" != *--ignore-not-found* ]]; then
      echo "kubectl fake requires --ignore-not-found for deployment discovery" >&2
      exit 44
    else
      if [[ "${FAKE_KUBECTL_MODE:-ok}" == fail ]]; then
        echo "simulated kubectl failure" >&2
        exit 43
      fi
      if [[ "${FAKE_LEGACY_DEPLOYMENTS:-}" == *backend* ]]; then
        printf 'deployment.apps/backend\n'
      fi
      if [[ "${FAKE_LEGACY_DEPLOYMENTS:-}" == *frontend* ]]; then
        printf 'deployment.apps/frontend\n'
      fi
    fi
    ;;
  *" get pod "*)
    printf '%s' "${FAKE_WRITER_PODS:-}"
    ;;
  *" scale deployment"*)
    if [[ "${FAKE_KUBECTL_FAIL_SCALE:-false}" == true ]]; then
      echo "simulated scale failure" >&2
      exit 46
    fi
    ;;
  *" wait --for=delete "*) ;;
  *)
    echo "unexpected kubectl call: $*" >&2
    exit 44
    ;;
esac
EOF

  cat >"$TEST_BIN/helmfile" <<'EOF'
#!/usr/bin/env bash
printf 'helmfile|%s|namespace=%s|phase=%s|tracker_migration=%s\n' "$*" "${PORTAL_NAMESPACE:-}" "${PORTAL_BLUE_GREEN_PHASE:-}" "${PORTAL_TRACKER_MIGRATION:-}" >>"$PORTAL_TEST_LOG"
call_number="$(grep -c '^helmfile|' "$PORTAL_TEST_LOG")"
if [[ "${FAKE_HELMFILE_FAIL_ON_CALL:-0}" == "$call_number" ]]; then
  echo "simulated helmfile failure $call_number" >&2
  exit 45
fi
EOF

  chmod +x "$TEST_BIN/helm" "$TEST_BIN/kubectl" "$TEST_BIN/helmfile"
}

run_deploy() {
  : >"$PORTAL_TEST_LOG"
  if DEPLOY_OUTPUT="$(
    PATH="$TEST_BIN:$PATH" \
      PORTAL_ROOT_DIR="$TEST_ROOT" \
      PORTAL_TEST_LOG="$PORTAL_TEST_LOG" \
      PORTAL_BLUE_GREEN_PHASE="$CALLER_PHASE" \
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
  local expected="$1"
  shift
  "$@"
  if [[ "$DEPLOY_STATUS" -eq 0 ]]; then
    fail "expected deployment to fail"
  fi
  if grep -q '^helmfile|' "$PORTAL_TEST_LOG"; then
    fail "expected failure before helmfile, got: $(cat "$PORTAL_TEST_LOG")"
  fi
  assert_output_contains "$expected"
}

assert_operational_failure_before_helmfile() {
  local expected="$1"
  shift
  "$@"
  if [[ "$DEPLOY_STATUS" -eq 0 ]]; then
    fail "expected deployment to fail"
  fi
  if grep -q '^helmfile|' "$PORTAL_TEST_LOG"; then
    fail "expected operational failure before helmfile, got: $(cat "$PORTAL_TEST_LOG")"
  fi
  assert_output_contains "$expected"
}

assert_phases() {
  local expected="$*"
  local actual
  actual="$(sed -n 's/^helmfile|.*|phase=\([^|]*\).*/\1/p' "$PORTAL_TEST_LOG" | paste -sd ' ' -)"
  if [[ "$actual" != "$expected" ]]; then
    fail "expected phases '$expected', got '$actual'"
  fi
}

assert_tracker_migration_sequence() {
  local scale_line migration_line restore_line
  scale_line="$(grep -n 'kubectl|.* scale .*--replicas=0' "$PORTAL_TEST_LOG" | head -1 | cut -d: -f1)"
  migration_line="$(grep -n '^helmfile|.*tracker_migration=true$' "$PORTAL_TEST_LOG" | head -1 | cut -d: -f1)"
  restore_line="$(grep -n '^helmfile|.*tracker_migration=false$' "$PORTAL_TEST_LOG" | tail -1 | cut -d: -f1)"
  if [[ -z "$scale_line" || -z "$migration_line" || -z "$restore_line" ||
        "$scale_line" -ge "$migration_line" || "$migration_line" -ge "$restore_line" ]]; then
    fail "tracker migration must scale writers to zero, opt in, then restore normally: $(cat "$PORTAL_TEST_LOG")"
  fi
}

assert_single_unphased_helmfile() {
  local action="$1"
  local phase_calls
  phase_calls="$(sed -n 's/^helmfile|.*|phase=\([^|]*\).*/\1/p' "$PORTAL_TEST_LOG")"
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
export FAKE_HELM_MODE FAKE_HELM_RELEASE_ROWS FAKE_KUBECTL_MODE FAKE_LEGACY_DEPLOYMENTS
export FAKE_WRITER_DEPLOYMENTS FAKE_WRITER_PODS FAKE_HELMFILE_FAIL_ON_CALL FAKE_KUBECTL_FAIL_SCALE

CALLER_PHASE=''
FAKE_HELM_MODE=rows
FAKE_HELM_RELEASE_ROWS=''
FAKE_KUBECTL_MODE=ok
FAKE_LEGACY_DEPLOYMENTS=''
FAKE_WRITER_DEPLOYMENTS=$'deployment.apps/backend-blue\ndeployment.apps/backend-green\ndeployment.apps/frontend-blue\ndeployment.apps/frontend-green\ndeployment.apps/redmine\n'
FAKE_WRITER_PODS=''
FAKE_HELMFILE_FAIL_ON_CALL=0
FAKE_KUBECTL_FAIL_SCALE=false
run_deploy dev info
assert_log_empty
assert_output_contains 'Namespace   : support-ticket-portal-dev'

run_deploy dev info team-space
assert_output_contains 'Namespace   : team-space'

assert_exit_2 run_deploy dev sync team-space unexpected-fourth

FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev other-space'
assert_fails_before_helmfile 'support-ticket-portal-dev already exists in namespace other-space; this command relocates one environment and does not create parallel copies' run_deploy dev sync team-space

FAKE_HELM_RELEASE_ROWS=$'support-ticket-portal-dev team-space\nsupport-ticket-portal-dev other-space'
assert_fails_before_helmfile 'support-ticket-portal-dev already exists in namespace other-space; this command relocates one environment and does not create parallel copies' run_deploy dev sync team-space

FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev-traefik other-space'
assert_fails_before_helmfile 'support-ticket-portal-dev-traefik already exists in namespace other-space; this command relocates one environment and does not create parallel copies' run_deploy dev sync team-space

FAKE_HELM_MODE=fail
FAKE_HELM_RELEASE_ROWS=''
assert_operational_failure_before_helmfile 'failed to inspect Helm releases' run_deploy dev sync team-space

FAKE_HELM_MODE=malformed
assert_operational_failure_before_helmfile 'failed to parse Helm release inventory' run_deploy dev sync team-space

FAKE_HELM_MODE=non-list
assert_operational_failure_before_helmfile 'failed to parse Helm release inventory' run_deploy dev sync team-space

FAKE_HELM_MODE=rows
FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev team-space'
FAKE_LEGACY_DEPLOYMENTS='backend frontend'
run_deploy dev sync team-space
assert_phases migration coexist active

FAKE_KUBECTL_MODE=fail
assert_operational_failure_before_helmfile 'failed to inspect legacy Deployments' run_deploy dev sync team-space

FAKE_KUBECTL_MODE=ok
FAKE_LEGACY_DEPLOYMENTS='backend'
run_deploy dev sync team-space
assert_phases migration coexist active

FAKE_LEGACY_DEPLOYMENTS='frontend'
run_deploy dev sync team-space
assert_phases migration coexist active

FAKE_LEGACY_DEPLOYMENTS=''
run_deploy dev sync team-space
assert_phases active
if ! grep -q '^helmfile|.*tracker_migration=false$' "$PORTAL_TEST_LOG"; then
  fail "normal sync must explicitly disable tracker retirement: $(cat "$PORTAL_TEST_LOG")"
fi

FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev team-space'
FAKE_WRITER_PODS=$'pod/backend-blue-1\npod/frontend-blue-1\npod/redmine-1\n'
run_deploy dev tracker-migration team-space
if [[ "$DEPLOY_STATUS" -ne 0 ]]; then
  fail "tracker migration must succeed, got exit $DEPLOY_STATUS: $DEPLOY_OUTPUT"
fi
assert_tracker_migration_sequence
if ! grep -q 'kubectl|.* scale deployment.apps/backend-blue deployment.apps/backend-green deployment.apps/frontend-blue deployment.apps/frontend-green deployment.apps/redmine --replicas=0' "$PORTAL_TEST_LOG"; then
  fail "tracker migration must explicitly scale every discovered writer Deployment: $(cat "$PORTAL_TEST_LOG")"
fi
for pod in backend-blue-1 frontend-blue-1 redmine-1; do
  if ! grep -q "kubectl|.* wait --for=delete pod/$pod " "$PORTAL_TEST_LOG"; then
    fail "tracker migration must wait for $pod to stop: $(cat "$PORTAL_TEST_LOG")"
  fi
done

FAKE_HELMFILE_FAIL_ON_CALL=2
run_deploy dev tracker-migration team-space
if [[ "$DEPLOY_STATUS" -eq 0 ]]; then
  fail "tracker migration must report a failed normal restore"
fi
scale_calls="$(grep -c 'kubectl|.* scale .*--replicas=0' "$PORTAL_TEST_LOG")"
if [[ "$scale_calls" -ne 2 ]]; then
  fail "failed restore must enforce the zero-replica safe state: $(cat "$PORTAL_TEST_LOG")"
fi
FAKE_HELMFILE_FAIL_ON_CALL=0
FAKE_WRITER_PODS=''

FAKE_KUBECTL_FAIL_SCALE=true
run_deploy dev tracker-migration team-space
if [[ "$DEPLOY_STATUS" -eq 0 ]]; then
  fail "tracker migration must fail when writers cannot be scaled to zero"
fi
assert_output_contains 'warning: failed to verify zero-replica maintenance state'
FAKE_KUBECTL_FAIL_SCALE=false

FAKE_WRITER_DEPLOYMENTS=$'deployment.apps/backend-blue\ndeployment.apps/frontend-blue\n'
run_deploy dev tracker-migration team-space
if [[ "$DEPLOY_STATUS" -eq 0 ]]; then
  fail "tracker migration must fail if a writer Deployment type is missing"
fi
assert_output_contains 'failed to find backend, frontend, and Redmine Deployments'
if grep -q '^helmfile|' "$PORTAL_TEST_LOG"; then
  fail "missing writer Deployments must fail before destructive bootstrap: $(cat "$PORTAL_TEST_LOG")"
fi
FAKE_WRITER_DEPLOYMENTS=$'deployment.apps/backend-blue\ndeployment.apps/backend-green\ndeployment.apps/frontend-blue\ndeployment.apps/frontend-green\ndeployment.apps/redmine\n'

FAKE_LEGACY_DEPLOYMENTS='backend frontend'
FAKE_HELM_RELEASE_ROWS='support-ticket-portal-dev other-space'
CALLER_PHASE=migration
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
CALLER_PHASE=''

if [[ "$FAILURES" -ne 0 ]]; then
  exit 1
fi

echo "Deploy script tests passed"
