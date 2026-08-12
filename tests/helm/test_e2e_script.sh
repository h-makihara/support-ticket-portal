#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT_DIR/scripts/helmfile-e2e.sh"
TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/support-ticket-portal-e2e.XXXXXX")"
FAKE_BIN="$TEST_DIR/bin"
COMMAND_LOG="$TEST_DIR/commands.log"
PORTAL_ROOT="$TEST_DIR/portal-root"

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local expected="$1"
  grep -Fqx "$expected" "$COMMAND_LOG" || fail "missing command: $expected"
}

assert_kubectl_called() {
  assert_contains "kubectl $1"
}

assert_npm_called() {
  assert_contains "npm $1"
}

assert_namespace_is() {
  grep -Fqx "kubectl -n $1 port-forward service/frontend 18080:80" "$COMMAND_LOG" \
    || fail "namespace was not $1"
}

assert_stable_service_fallback() {
  grep -Fqx "kubectl -n team-space port-forward $1 18080:80" "$COMMAND_LOG" \
    || fail "stable service fallback did not use $1"
}

assert_exit_2() {
  set +e
  "$@" >/dev/null 2>&1
  local status=$?
  set -e
  [[ "$status" -eq 2 ]] || fail "expected exit 2, got $status"
}

setup_fakes() {
  mkdir -p "$FAKE_BIN" "$PORTAL_ROOT"
  cp -R "$ROOT_DIR/deploy" "$PORTAL_ROOT/deploy"
  cp "$PORTAL_ROOT/deploy/env/dev.env.example" "$PORTAL_ROOT/deploy/env/dev.env"

  cat >"$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
case "${*: -1}" in
  http://127.0.0.1:*) exit 0 ;;
  *) exit 1 ;;
esac
EOF
cat >"$FAKE_BIN/kubectl" <<'EOF'
#!/usr/bin/env bash
{
  printf 'kubectl'
  printf ' %s' "$@"
  printf '\n'
} >>"$FAKE_COMMAND_LOG"
while :; do
  command sleep 60
done
EOF
  cat >"$FAKE_BIN/npm" <<'EOF'
#!/usr/bin/env bash
args=("$@")
if [[ "${args[0]:-}" == "exec" ]]; then
  args=("${args[@]:1}")
fi
if [[ "${args[0]:-}" == "--" ]]; then
  args=("${args[@]:1}")
fi
printf 'npm'
printf ' %s' "${args[@]}"
printf '\n'
EOF
  cat >"$FAKE_BIN/npx" <<'EOF'
#!/usr/bin/env bash
exec "$(dirname "$0")/npm" "$@"
EOF
  cat >"$FAKE_BIN/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$FAKE_BIN/curl" "$FAKE_BIN/kubectl" "$FAKE_BIN/npm" "$FAKE_BIN/npx" "$FAKE_BIN/sleep"
}

run_e2e() {
  : >"$COMMAND_LOG"
  PATH="$FAKE_BIN:$PATH" FAKE_COMMAND_LOG="$COMMAND_LOG" PORTAL_ROOT_DIR="$PORTAL_ROOT" "$SCRIPT" "$@" >>"$COMMAND_LOG" 2>&1
}

setup_fakes

run_e2e dev --namespace team-space --slot green e2e/ticket-creation.spec.ts
assert_kubectl_called '-n team-space port-forward service/frontend-green 18080:80'
assert_npm_called 'playwright test e2e/ticket-creation.spec.ts'
if grep -Fq 'Ingress is unavailable' "$COMMAND_LOG"; then
  fail 'slot mode probed ingress instead of port-forwarding immediately'
fi

run_e2e dev --namespace team-space e2e/faq.spec.ts
assert_namespace_is team-space
assert_stable_service_fallback 'service/frontend'

assert_exit_2 run_e2e dev --slot red
assert_exit_2 run_e2e dev --namespace

echo "PASS: helmfile E2E script namespace and slot options"
