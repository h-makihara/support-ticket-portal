# Safe Blue-Green Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frontend/backend blue-green pair independently verifiable and safely migrate an existing single-Deployment release without losing stable Service endpoints, while treating an optional Namespace as the environment's single placement target.

**Architecture:** Stable Portal traffic switches only the `frontend` Service; each frontend slot mounts an Nginx config that proxies to the matching backend slot Service. A deploy-script state machine renders `migration`, `coexist`, then `active` phases only when legacy Deployments exist, and rejects the same environment release in another Namespace before sync. Shell behavior is tested with fake CLIs, while rendered manifests are parsed structurally with Ruby's standard YAML library.

**Tech Stack:** Bash 3.2-compatible shell, Helm 3, Helmfile, Kubernetes apps/v1 and networking.k8s.io/v1, Ruby YAML/minitest for manifest assertions, Playwright E2E.

## Global Constraints

- Namespace omission must continue to select `support-ticket-portal-<environment>`.
- A custom Namespace is a single placement target, not a preview/parallel-copy identifier.
- The legacy Deployment immutable selectors must never be changed in place.
- Portal requests must always pair a frontend slot with the backend Service of the same slot.
- PostgreSQL, Redis, Redmine, Secret, bootstrap, and Alloy remain shared.
- `info` and `template` remain usable without a live Kubernetes cluster.
- No new runtime dependency may be added for tests; use system Ruby standard libraries and shell tools already required by the project.
- Every behavior change follows RED → GREEN → REFACTOR, with the failing command and expected failure recorded below.

---

## File Structure

- `deploy/chart/templates/app.yaml`: stable and slot Services plus phase orchestration; no container details.
- `deploy/chart/templates/_app.tpl`: parameterized legacy and slot Deployment renderers, keeping Backend/Frontend container definitions in one place.
- `deploy/chart/templates/frontend-config.yaml`: per-slot Nginx ConfigMaps used only by slot Frontends.
- `deploy/chart/values.yaml`: documented `blueGreen.phase` internal default and public slot settings.
- `helmfile.yaml.gotmpl`: inject `PORTAL_BLUE_GREEN_PHASE` into only the application release.
- `scripts/helmfile-deploy.sh`: argument guard, duplicate-release preflight, and legacy three-phase state machine.
- `scripts/lib/helmfile-env.sh`: shared Namespace validation and release-name helpers.
- `scripts/helmfile-e2e.sh`: explicit Namespace/slot option parsing and slot Service forwarding.
- `tests/helm/manifest_assertions.rb`: structural rendered-YAML tests.
- `tests/helm/test_deploy_script.sh`: fake-cluster deploy CLI behavior tests.
- `tests/helm/test_e2e_script.sh`: E2E option/Service-selection tests using fake commands.
- `scripts/validate-helm.sh`: invokes focused tests, then retains four-environment validation.
- `docs/helmfile.md`, `docs/testing.md`, `deploy/README.md`, `README.md`, `Makefile`: operator-facing commands and safety contract.

---

### Task 1: Structural Manifest Contract Tests

**Files:**
- Create: `tests/helm/manifest_assertions.rb`
- Modify: `scripts/validate-helm.sh`

**Interfaces:**
- Consumes: `helm template support-ticket-portal deploy/chart` output on stdin/file.
- Produces: executable assertions for `active`, `migration`, and `coexist` manifests.

- [ ] **Step 1: Create a resource-aware failing test**

Implement `tests/helm/manifest_assertions.rb` using `YAML.load_stream` and helpers with these exact interfaces:

```ruby
require "yaml"

def resource(documents, kind, name)
  documents.fetch([kind, name])
end

def selector(documents, kind, name)
  resource(documents, kind, name).fetch("spec").fetch("selector")
end

def deployment_image(documents, name, container)
  containers = resource(documents, "Deployment", name)
    .dig("spec", "template", "spec", "containers")
  containers.find { |item| item.fetch("name") == container }.fetch("image")
end
```

Render an active-green manifest with distinct tags and assert:

```ruby
raise "frontend must select green" unless selector(docs, "Service", "frontend")["app.kubernetes.io/slot"] == "green"
raise "backend must select green" unless selector(docs, "Service", "backend")["app.kubernetes.io/slot"] == "green"
%w[blue green].each do |slot|
  raise "backend slot selector" unless selector(docs, "Service", "backend-#{slot}")["app.kubernetes.io/slot"] == slot
  raise "frontend slot selector" unless selector(docs, "Service", "frontend-#{slot}")["app.kubernetes.io/slot"] == slot
end
raise "wrong blue backend image" unless deployment_image(docs, "backend-blue", "backend").end_with?(":backend-blue-test")
raise "wrong green frontend image" unless deployment_image(docs, "frontend-green", "frontend").end_with?(":frontend-green-test")
```

Also assert that ConfigMap `frontend-blue-nginx` contains `proxy_pass http://backend-blue:8000/;` and the green ConfigMap contains `backend-green`.

- [ ] **Step 2: Run the active manifest test and verify RED**

Run:

```bash
ruby tests/helm/manifest_assertions.rb active
```

Expected: FAIL because `backend-blue`, `frontend-blue`, and slot Nginx ConfigMaps do not exist.

- [ ] **Step 3: Add migration/coexist failing assertions**

For `migration`, assert all of the following:

```ruby
raise unless resource(docs, "Deployment", "backend").dig("spec", "selector", "matchLabels").keys.sort == ["app.kubernetes.io/instance", "app.kubernetes.io/name"]
raise unless resource(docs, "Deployment", "backend").dig("spec", "template", "metadata", "labels", "app.kubernetes.io/slot") == "blue"
raise if selector(docs, "Service", "backend").key?("app.kubernetes.io/slot")
raise if docs.key?(["Deployment", "backend-blue"])
```

For `coexist`, assert legacy and both slot Deployments exist, and stable Services select only `blue`.

- [ ] **Step 4: Run migration/coexist tests and verify RED**

Run:

```bash
ruby tests/helm/manifest_assertions.rb migration
ruby tests/helm/manifest_assertions.rb coexist
```

Expected: FAIL because the chart does not support `blueGreen.phase` and never renders legacy Deployments.

- [ ] **Step 5: Add negative render assertions**

Test `blueGreen.activeSlot=red`, deleted `blueGreen.slots.green`, and `blueGreen.phase=unknown`. Each `helm template` command must exit nonzero and contain its precise validation message.

- [ ] **Step 6: Commit the RED tests**

```bash
git add tests/helm/manifest_assertions.rb scripts/validate-helm.sh
git commit -m "test: define safe blue-green manifest contract"
```

---

### Task 2: Phase-Aware Chart and Slot-Paired Routing

**Files:**
- Create: `deploy/chart/templates/_app.tpl`
- Create: `deploy/chart/templates/frontend-config.yaml`
- Modify: `deploy/chart/templates/app.yaml`
- Modify: `deploy/chart/values.yaml`
- Modify: `helmfile.yaml.gotmpl`

**Interfaces:**
- Consumes: `.Values.blueGreen.phase` in `migration|coexist|active`, `.Values.blueGreen.activeSlot`, and the two slot tag maps.
- Produces: phase-safe Kubernetes resources and slot-paired Nginx routing.

- [ ] **Step 1: Add phase validation and Helmfile injection**

Add this internal value:

```yaml
blueGreen:
  # Internal deploy-script phase. Operators normally leave this as active.
  phase: active
```

Inject it in the application release values only:

```yaml
blueGreen:
  phase: {{ env "PORTAL_BLUE_GREEN_PHASE" | default "active" | quote }}
```

At template entry, fail unless phase is one of `migration`, `coexist`, `active`; continue validating both required slots and `activeSlot`.

- [ ] **Step 2: Extract shared Deployment renderers**

Create `_app.tpl` definitions `portal.backendDeployment` and `portal.frontendDeployment` accepting a dict with `root`, `name`, `slot`, `backendTag`, `frontendTag`, and `legacy`.

For `legacy: true`:

- names are `backend` and `frontend`
- immutable `spec.selector.matchLabels` contains only name and instance
- Pod template adds `app.kubernetes.io/slot: blue`
- Frontend uses the image's existing `/etc/nginx/conf.d/default.conf`

For `legacy: false`:

- names include the slot
- selectors and Pod labels contain the slot
- Frontend mounts ConfigMap `frontend-<slot>-nginx` at `/etc/nginx/conf.d/default.conf` with `subPath: default.conf`

Keep all existing Backend environment variables, probes, resources, imagePullSecrets, observability sidecar, checksums, and volume definitions unchanged.

- [ ] **Step 3: Render phase-specific Services and Deployments**

Refactor `app.yaml` so:

- `migration`: stable Services have no slot selector; render legacy Deployments only.
- `coexist`: stable Services select blue; render legacy Deployments, four slot Services, and four slot Deployments.
- `active`: stable Services select `activeSlot`; render four slot Services and four slot Deployments; do not render legacy Deployments.

Slot Services must select name + instance + matching slot. Stable Service names remain `frontend` and `backend`.

- [ ] **Step 4: Generate per-slot Nginx ConfigMaps**

Create `frontend-config.yaml` for coexist/active phases. Each `default.conf` preserves the existing SPA settings and headers, with only this slot-specific upstream change:

```nginx
location /api/ {
    proxy_pass http://backend-{{ $slot }}:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Origin $http_origin;
}
```

Add a checksum annotation of the rendered slot config to each slot Frontend Pod template.

- [ ] **Step 5: Run structural tests and verify GREEN**

Run:

```bash
ruby tests/helm/manifest_assertions.rb active
ruby tests/helm/manifest_assertions.rb migration
ruby tests/helm/manifest_assertions.rb coexist
helm lint deploy/chart --set secrets.redmineApiKey=x --set secrets.redmineSecretKeyBase=x --set secrets.postgresPassword=x --set secrets.testAdminPassword=x --set secrets.testSupportPassword=x --set secrets.testSalesPassword=x
```

Expected: all commands exit 0; invalid phase/slot subtests still prove nonzero rendering.

- [ ] **Step 6: Refactor duplicate YAML while tests remain green**

Ensure container definitions exist only in `_app.tpl`, phase orchestration only in `app.yaml`, and Nginx config only in `frontend-config.yaml`. Re-run the commands from Step 5.

- [ ] **Step 7: Commit**

```bash
git add deploy/chart/templates/_app.tpl deploy/chart/templates/frontend-config.yaml deploy/chart/templates/app.yaml deploy/chart/values.yaml helmfile.yaml.gotmpl tests/helm/manifest_assertions.rb
git commit -m "feat: pair blue-green frontend and backend slots"
```

---

### Task 3: Safe Deploy State Machine and Namespace Collision Guard

**Files:**
- Create: `tests/helm/test_deploy_script.sh`
- Modify: `scripts/helmfile-deploy.sh`
- Modify: `scripts/lib/helmfile-env.sh`

**Interfaces:**
- Consumes: positional `<environment> [action] [namespace]`, Helm release inventory, legacy Deployment presence.
- Produces: zero/one/three Helmfile sync calls and an apply-before-collision safety gate.

- [ ] **Step 1: Write fake-CLI RED tests**

In a temporary directory, create executable `helm`, `kubectl`, and `helmfile` fakes that append their full argument list plus `PORTAL_NAMESPACE` and `PORTAL_BLUE_GREEN_PHASE` to `$PORTAL_TEST_LOG`.

Cover these exact cases:

```bash
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
```

The fakes must also assert that `diff`, `template`, and `destroy` never invoke the three-phase state machine.

- [ ] **Step 2: Run deploy script tests and verify RED**

Run:

```bash
bash tests/helm/test_deploy_script.sh
```

Expected: FAIL because excessive arguments are accepted, duplicate releases are not inspected, and legacy releases receive only one unphased sync.

- [ ] **Step 3: Add shared release helpers**

In `helmfile-env.sh`, set:

```bash
PORTAL_RELEASE="support-ticket-portal-$environment"
PORTAL_TRAEFIK_RELEASE="$PORTAL_RELEASE-traefik"
```

Add `portal_usage_deploy` and keep Namespace validation in `portal_select_environment` so deploy and E2E use the same rule.

- [ ] **Step 4: Implement duplicate Namespace preflight**

For `sync`, inspect both release names using `helm list --all-namespaces --all --filter "^${release}$" --output json`. Parse JSON with `python3 -c` and collect namespaces that differ from `PORTAL_NAMESPACE`.

If any conflict exists, exit before Helmfile with a message containing:

```text
support-ticket-portal-dev already exists in namespace other-space; this command relocates one environment and does not create parallel copies
```

Do not run this preflight for `info` or `template`. For `diff`, print the same condition as a warning without failing. `destroy` operates only on the explicitly selected Namespace.

- [ ] **Step 5: Implement resumable legacy phases**

Detect legacy state with:

```bash
kubectl -n "$PORTAL_NAMESPACE" get deployment backend frontend -o name
```

When both legacy Deployments exist, run:

```bash
PORTAL_BLUE_GREEN_PHASE=migration helmfile --environment "$PORTAL_ENVIRONMENT" sync
PORTAL_BLUE_GREEN_PHASE=coexist helmfile --environment "$PORTAL_ENVIRONMENT" sync
PORTAL_BLUE_GREEN_PHASE=active helmfile --environment "$PORTAL_ENVIRONMENT" sync
```

Export the phase for Helmfile templating. If migration fails, `set -e` prevents later phases. Re-running after a partial success is safe: if legacy Deployments still exist, all three idempotent phases run again; after active succeeds, only active runs on future syncs.

- [ ] **Step 6: Run deploy script tests and verify GREEN**

Run:

```bash
bash tests/helm/test_deploy_script.sh
bash -n scripts/helmfile-deploy.sh scripts/lib/helmfile-env.sh tests/helm/test_deploy_script.sh
```

Expected: both exit 0.

- [ ] **Step 7: Commit**

```bash
git add scripts/helmfile-deploy.sh scripts/lib/helmfile-env.sh tests/helm/test_deploy_script.sh
git commit -m "fix: migrate legacy Helm releases without endpoint loss"
```

---

### Task 4: Namespace- and Slot-Aware E2E

**Files:**
- Create: `tests/helm/test_e2e_script.sh`
- Modify: `scripts/helmfile-e2e.sh`

**Interfaces:**
- Consumes: `<environment> [--namespace N] [--slot blue|green] [Playwright args...]`.
- Produces: E2E against stable ingress/Service or a forced slot Service.

- [ ] **Step 1: Write E2E CLI RED tests**

Use fake `curl`, `kubectl`, `npm`, and `sleep` executables. Assert:

```bash
run_e2e dev --namespace team-space --slot green e2e/ticket-creation.spec.ts
assert_kubectl_called '-n team-space port-forward service/frontend-green 18080:80'
assert_npm_called 'playwright test e2e/ticket-creation.spec.ts'

run_e2e dev --namespace team-space e2e/faq.spec.ts
assert_namespace_is team-space
assert_stable_service_fallback 'service/frontend'

assert_exit_2 run_e2e dev --slot red
assert_exit_2 run_e2e dev --namespace
```

Force slot mode to skip ingress probing; it must always port-forward the chosen slot Service.

- [ ] **Step 2: Run and verify RED**

Run:

```bash
bash tests/helm/test_e2e_script.sh
```

Expected: FAIL because current option parsing forwards `--namespace` and `--slot` to Playwright and always uses the default Namespace/stable Service.

- [ ] **Step 3: Implement option parsing**

After shifting the environment, parse recognized options until the first Playwright argument. Validate the slot with `blue|green`, call `portal_select_environment "$ENVIRONMENT" false "$NAMESPACE"`, and preserve the remaining arguments exactly in `"$@"`.

Select the Service as:

```bash
frontend_service="frontend"
if [[ -n "$SLOT" ]]; then
  frontend_service="frontend-$SLOT"
fi
```

If `SLOT` is set, bypass ingress and port-forward immediately. Otherwise retain the current ingress-first fallback.

- [ ] **Step 4: Run and verify GREEN**

Run:

```bash
bash tests/helm/test_e2e_script.sh
bash -n scripts/helmfile-e2e.sh tests/helm/test_e2e_script.sh
```

Expected: both exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/helmfile-e2e.sh tests/helm/test_e2e_script.sh
git commit -m "test: verify inactive blue-green slots end to end"
```

---

### Task 5: Operator Documentation and Full Validation

**Files:**
- Modify: `scripts/validate-helm.sh`
- Modify: `docs/helmfile.md`
- Modify: `docs/testing.md`
- Modify: `deploy/README.md`
- Modify: `README.md`
- Modify: `Makefile`

**Interfaces:**
- Consumes: behavior delivered in Tasks 1–4.
- Produces: one validation entry point and accurate operator runbooks.

- [ ] **Step 1: Wire focused tests into validation**

At the start of `scripts/validate-helm.sh`, after bootstrap-file consistency, invoke:

```bash
ruby tests/helm/manifest_assertions.rb active
ruby tests/helm/manifest_assertions.rb migration
ruby tests/helm/manifest_assertions.rb coexist
bash tests/helm/test_deploy_script.sh
bash tests/helm/test_e2e_script.sh
```

Replace broad `assert_contains "app.kubernetes.io/slot: blue"` checks with the structural test; retain all four-environment IngressClass, URL, test-user, and image pin assertions.

- [ ] **Step 2: Correct deployment and migration documentation**

Update `docs/helmfile.md` with:

- automatic three-phase migration on the first `sync` from legacy chart
- two-sync normal release workflow
- `kubectl rollout status` for both inactive Deployments
- inactive smoke test and `helmfile-e2e.sh dev --namespace "$NAMESPACE" --slot green`
- rollback by restoring `activeSlot`
- explicit statement that two application slots double Frontend/Backend requested capacity
- custom Namespace as initial placement only, with duplicate-release rejection
- Namespace relocation requiring backup/destroy/recreate rather than parallel sync

- [ ] **Step 3: Fix every Namespace-sensitive runbook command**

In backup, restore, and destroy examples, pass `"$NAMESPACE"` as the third deploy argument:

```bash
./scripts/helmfile-deploy.sh "$ENVIRONMENT" sync "$NAMESPACE"
./scripts/helmfile-deploy.sh "$ENVIRONMENT" destroy "$NAMESPACE"
```

Before destroy, show `helm -n "$NAMESPACE" list --all` and require the operator to compare environment and Namespace.

- [ ] **Step 4: Update concise entry-point docs**

Update `README.md`, `deploy/README.md`, `docs/testing.md`, and Makefile help with these discoverable examples:

```bash
./scripts/helmfile-deploy.sh int sync team-space
./scripts/helmfile-e2e.sh int --namespace team-space --slot green
```

Do not describe custom Namespace as permitting multiple copies of one environment.

- [ ] **Step 5: Run fresh full verification**

Run:

```bash
./scripts/validate-helm.sh
git diff --check
bash -n scripts/*.sh scripts/lib/*.sh tests/helm/*.sh
```

If `shellcheck` is installed, additionally run:

```bash
shellcheck scripts/helmfile-deploy.sh scripts/helmfile-e2e.sh scripts/lib/helmfile-env.sh scripts/validate-helm.sh tests/helm/*.sh
```

Expected: every command exits 0. The Helm validation output must explicitly report int, dev, stg, and prd passed.

- [ ] **Step 6: Review the complete range**

Dispatch `superpowers:requesting-code-review` over `d15b7e1..HEAD`, verify each finding against the codebase, fix all Critical and Important findings one at a time, and re-run Step 5 after any change.

- [ ] **Step 7: Commit**

```bash
git add scripts/validate-helm.sh docs/helmfile.md docs/testing.md deploy/README.md README.md Makefile
git commit -m "docs: document safe blue-green operations"
```

---

## Plan Self-Review

- Spec coverage: legacy endpoint continuity, paired routing, inactive verification, slot switching, Namespace defaults/collision protection, E2E propagation, backup/destroy correctness, and four-environment validation each map to a task.
- Dependency order: manifest tests precede chart changes; chart phase support precedes deploy state machine; shared Namespace validation precedes E2E options; documentation follows verified behavior.
- Interface consistency: phases are exactly `migration|coexist|active`; slots are exactly `blue|green`; deploy Namespace remains positional argument 3; E2E Namespace and slot are explicit named options.
- Scope: no database migration automation, preview-environment identity, or unrelated application refactor is included.
