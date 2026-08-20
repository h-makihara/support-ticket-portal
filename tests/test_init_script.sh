#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INIT_SCRIPT="$ROOT_DIR/scripts/init.sh"
TEST_DIR="$(mktemp -d -t support-ticket-portal-init.XXXXXX)"
TEST_BIN="$TEST_DIR/bin"
INIT_TEST_LOG="$TEST_DIR/commands.log"
FAILURES=0
INIT_OUTPUT=""
INIT_STATUS=0

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  FAILURES=$((FAILURES + 1))
}

mkdir -p "$TEST_BIN"

cat >"$TEST_BIN/docker" <<'EOF'
#!/usr/bin/env bash
printf 'docker|%s\n' "$*" >>"$INIT_TEST_LOG"
if [[ "${FAKE_DOCKER_FAIL_MIGRATION:-false}" == true &&
      " $* " == *" run "* && "$*" == *"RETIRE_LEGACY_REQUEST_FIELDS=true"* ]]; then
  echo "simulated migration failure" >&2
  exit 55
fi
if [[ "${FAKE_DOCKER_FAIL_RESTORE:-false}" == true &&
      "$*" == "compose up -d --force-recreate backend frontend" ]]; then
  echo "simulated restore failure" >&2
  exit 56
fi
if [[ "${FAKE_DOCKER_FAIL_STOP:-false}" == true &&
      "$*" == "compose stop frontend backend redmine" ]]; then
  echo "simulated stop failure" >&2
  exit 57
fi
EOF

cat >"$TEST_BIN/python3" <<'EOF'
#!/usr/bin/env bash
printf 'python3|%s\n' "$*" >>"$INIT_TEST_LOG"
EOF

chmod +x "$TEST_BIN/docker" "$TEST_BIN/python3"
export INIT_TEST_LOG FAKE_DOCKER_FAIL_MIGRATION FAKE_DOCKER_FAIL_RESTORE FAKE_DOCKER_FAIL_STOP

run_init() {
  : >"$INIT_TEST_LOG"
  if INIT_OUTPUT="$(PATH="$TEST_BIN:$PATH" "$INIT_SCRIPT" "$@" 2>&1)"; then
    INIT_STATUS=0
  else
    INIT_STATUS=$?
  fi
}

FAKE_DOCKER_FAIL_MIGRATION=false
FAKE_DOCKER_FAIL_RESTORE=false
FAKE_DOCKER_FAIL_STOP=false
run_init
if [[ "$INIT_STATUS" -ne 0 ]]; then
  fail "normal initialization must succeed, got $INIT_STATUS: $INIT_OUTPUT"
fi
if grep -q 'RETIRE_LEGACY_REQUEST_FIELDS=true\|compose stop frontend backend redmine' "$INIT_TEST_LOG"; then
  fail "normal initialization must not enter destructive maintenance: $(cat "$INIT_TEST_LOG")"
fi
if ! grep -q 'docker|compose exec -T -e RETIRE_LEGACY_REQUEST_FIELDS=false redmine bundle exec rails runner /usr/src/redmine/bootstrap_redmine.rb' "$INIT_TEST_LOG"; then
  fail "normal initialization must explicitly disable retirement: $(cat "$INIT_TEST_LOG")"
fi

run_init --tracker-migration
if [[ "$INIT_STATUS" -ne 0 ]]; then
  fail "explicit tracker migration must succeed, got $INIT_STATUS: $INIT_OUTPUT"
fi
stop_line="$(grep -n 'docker|compose stop frontend backend redmine' "$INIT_TEST_LOG" | cut -d: -f1)"
migration_line="$(grep -n 'docker|compose run --rm --no-deps -e RETIRE_LEGACY_REQUEST_FIELDS=true redmine bundle exec rails runner /usr/src/redmine/bootstrap_redmine.rb' "$INIT_TEST_LOG" | cut -d: -f1)"
restore_line="$(grep -n 'docker|compose up -d --wait postgres redmine' "$INIT_TEST_LOG" | tail -1 | cut -d: -f1)"
if [[ -z "$stop_line" || -z "$migration_line" || -z "$restore_line" ||
      "$stop_line" -ge "$migration_line" || "$migration_line" -ge "$restore_line" ]]; then
  fail "tracker migration must stop writers, opt in, then restore services: $(cat "$INIT_TEST_LOG")"
fi

FAKE_DOCKER_FAIL_MIGRATION=true
run_init --tracker-migration
if [[ "$INIT_STATUS" -eq 0 ]]; then
  fail "migration runner failure must fail initialization"
fi
if grep -q '^python3|' "$INIT_TEST_LOG" || grep -q 'docker|compose up -d --wait postgres redmine' "$INIT_TEST_LOG"; then
  fail "failed migration must leave portal and Redmine stopped: $(cat "$INIT_TEST_LOG")"
fi

FAKE_DOCKER_FAIL_MIGRATION=false
FAKE_DOCKER_FAIL_RESTORE=true
run_init --tracker-migration
if [[ "$INIT_STATUS" -eq 0 ]]; then
  fail "service restore failure must fail initialization"
fi
if [[ "$(tail -1 "$INIT_TEST_LOG")" != 'docker|compose stop frontend backend redmine' ]]; then
  fail "failed restore must return Compose to write-freeze state: $(cat "$INIT_TEST_LOG")"
fi

FAKE_DOCKER_FAIL_RESTORE=false
FAKE_DOCKER_FAIL_STOP=true
run_init --tracker-migration
if [[ "$INIT_STATUS" -eq 0 ]]; then
  fail "writer stop failure must fail initialization"
fi
if [[ "$INIT_OUTPUT" != *'warning: failed to enforce Compose write-freeze state'* ]]; then
  fail "failed safety stop must be reported to the operator: $INIT_OUTPUT"
fi

if [[ "$FAILURES" -ne 0 ]]; then
  exit 1
fi

echo "Compose initialization script tests passed"
