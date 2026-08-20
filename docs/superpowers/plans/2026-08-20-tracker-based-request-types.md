# Tracker-based Request Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace report/visit requirement flags with a required choice among the `問い合わせ`, `報告書`, and `客先同行` Redmine trackers.

**Architecture:** Redmine bootstrap owns tracker creation, field associations, and the one-time destructive legacy migration. The FastAPI boundary accepts a stable tracker key, resolves it through Redmine's tracker list, and returns the key plus display name; React renders the same three choices and tracker-specific completion controls. Existing routes and screens remain shared across tracker types.

**Tech Stack:** Ruby/Redmine Rails runner, Python 3.12/FastAPI/Pydantic/httpx/pytest, React 19/TypeScript/Vitest/Testing Library, Docker Compose, Helm.

## Global Constraints

- A ticket belongs to exactly one of `inquiry`, `report`, or `customer_visit`; users create two tickets when two specialized workflows are needed.
- Delete all existing issues in the support project exactly once when either legacy field is found, then delete `報告書要否` and `客先同行要否`.
- Keep `報告書渡し済み` support-only and available only on `報告書`.
- Keep `予定・担当者アサイン済み` support-only and available only on `客先同行`.
- Do not add numeric tracker-ID environment variables or tracker-specific pages.
- Keep `scripts/bootstrap_redmine.rb` and `deploy/chart/files/bootstrap_redmine.rb` byte-for-byte identical.
- Add no dependencies.

---

### Task 1: Provision the three trackers and retire legacy Redmine data

**Files:**
- Modify: `scripts/bootstrap_redmine.rb`
- Modify: `deploy/chart/files/bootstrap_redmine.rb`
- Modify: `scripts/init_redmine.py`
- Modify: `tests/test_init_redmine.py`
- Modify: `tests/init_test.yaml`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `deploy/chart/values.yaml`
- Modify: `deploy/chart/templates/_app.tpl`

**Interfaces:**
- Produces: `TRACKER_NAMES = ("問い合わせ", "報告書", "客先同行")` in `scripts/init_redmine.py`.
- Produces: `ensure_trackers(client: httpx.Client, api_key: str) -> dict[str, int]`.
- Produces: Redmine trackers with the shared workflow and field associations defined in the design.
- Removes: `REDMINE_TRACKER_ID` and `REDMINE_TRACKER_NAME` runtime configuration.

- [ ] **Step 1: Replace the single-tracker initializer test with failing three-tracker tests**

Add tests shaped as follows to `tests/test_init_redmine.py`:

```python
def test_ensure_trackers_returns_all_portal_tracker_ids():
    def handler(request):
        assert request.url.path == "/trackers.json"
        return httpx.Response(200, json={"trackers": [
            {"id": 3, "name": "問い合わせ"},
            {"id": 4, "name": "報告書"},
            {"id": 5, "name": "客先同行"},
        ]})

    with client_for(handler) as client:
        assert init_redmine.ensure_trackers(client, "api-key") == {
            "問い合わせ": 3,
            "報告書": 4,
            "客先同行": 5,
        }


def test_missing_tracker_does_not_attempt_unsupported_post(capsys):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"trackers": [
            {"id": 3, "name": "問い合わせ"},
        ]})

    with client_for(handler) as client:
        with pytest.raises(SystemExit):
            init_redmine.ensure_trackers(client, "api-key")

    assert [request.method for request in requests] == ["GET"]
    assert "報告書, 客先同行" in capsys.readouterr().out
```

Also change `tests/init_test.yaml` tracker assertions to collect tracker names and assert all three Japanese names are present.

- [ ] **Step 2: Run the initializer tests and verify they fail**

Run: `uv run --group test pytest tests/test_init_redmine.py -q`

Expected: FAIL because `ensure_trackers` and `TRACKER_NAMES` do not exist.

- [ ] **Step 3: Implement three-tracker verification in the standalone initializer**

In `scripts/init_redmine.py`, replace `TRACKER_NAME` and `ensure_tracker` with:

```python
TRACKER_NAMES = ("問い合わせ", "報告書", "客先同行")


def ensure_trackers(client: httpx.Client, api_key: str) -> dict[str, int]:
    trackers = _get(client, "trackers", api_key).get("trackers", [])
    ids = {tracker["name"]: tracker["id"] for tracker in trackers}
    missing = [name for name in TRACKER_NAMES if name not in ids]
    if missing:
        print(f"  ✗ Missing trackers: {', '.join(missing)}")
        print("    Run the redmine-init service to provision administration resources")
        sys.exit(1)
    for name in TRACKER_NAMES:
        print(f"  ✓ Tracker '{name}' (ID={ids[name]}) already exists")
    return {name: ids[name] for name in TRACKER_NAMES}
```

Call `ensure_trackers` from `main`, stop passing a tracker ID to `write_env`, and stop writing `REDMINE_TRACKER_ID` to `.env`.

- [ ] **Step 4: Implement tracker provisioning, field assignment, and the one-time migration**

In `scripts/bootstrap_redmine.rb`:

```ruby
tracker_names = ["問い合わせ", "報告書", "客先同行"]
trackers = tracker_names.to_h do |name|
  tracker = Tracker.find_or_initialize_by(name: name)
  tracker.default_status = statuses.fetch("対応待ち")
  tracker.save!
  [name, tracker]
end
```

Set `project.trackers = trackers.values`. Immediately after saving the project, add a transaction guarded by legacy fields attached to this project:

```ruby
legacy_fields = IssueCustomField.where(name: ["報告書要否", "客先同行要否"])
if legacy_fields.any? { |field| field.projects.exists?(project.id) }
  ActiveRecord::Base.transaction do
    project.issues.find_each(&:destroy!)
    legacy_fields.each(&:destroy!)
  end
end
```

Replace the custom-field array with tracker names per field:

```ruby
custom_field_definitions = [
  ["顧客ID", "string", "", false, tracker_names],
  ["報告書渡し済み", "bool", "0", true, ["報告書"]],
  ["予定・担当者アサイン済み", "bool", "0", true, ["客先同行"]]
]
```

Assign `custom_field.trackers = field_tracker_names.map { |name| trackers.fetch(name) }`, update FAQ seed answers to instruct creating a `報告書` or `客先同行` ticket, and iterate workflows over `trackers.values` only. Copy the completed file to `deploy/chart/files/bootstrap_redmine.rb` with a formatting/copy command so both copies remain identical.

- [ ] **Step 5: Remove obsolete tracker-ID configuration**

Remove `REDMINE_TRACKER_NAME` from the Redmine Compose service, `REDMINE_TRACKER_ID` from the backend Compose service and `.env.example`, `app.redmineTrackerId` from Helm values, and the corresponding environment entry from `deploy/chart/templates/_app.tpl`.

- [ ] **Step 6: Run focused initializer and deployment validation**

Run:

```bash
uv run --group test pytest tests/test_init_redmine.py -q
./scripts/validate-helm.sh
```

Expected: initializer tests PASS; Helm validation reports the bootstrap copies are synchronized and all templates valid.

- [ ] **Step 7: Commit the Redmine provisioning change**

```bash
git add scripts/bootstrap_redmine.rb deploy/chart/files/bootstrap_redmine.rb scripts/init_redmine.py tests/test_init_redmine.py tests/init_test.yaml docker-compose.yml .env.example deploy/chart/values.yaml deploy/chart/templates/_app.tpl
git commit -m "feat: provision request type trackers"
```

---

### Task 2: Make tracker type part of the backend contract

**Files:**
- Modify: `backend/domain/models/ticket.py`
- Modify: `backend/domain/services/ticket_policy.py`
- Modify: `backend/application/schemas/ticket.py`
- Modify: `backend/application/presenters/ticket.py`
- Modify: `backend/infrastructure/redmine/mappers.py`
- Modify: `backend/app.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_tickets.py`
- Modify: `tests/test_helpers.py`
- Modify: `tests/test_api_contract.py`

**Interfaces:**
- Produces: `TrackerKey = Literal["inquiry", "report", "customer_visit"]`.
- Produces: `TRACKER_NAMES: dict[TrackerKey, str]` and inverse `TRACKER_KEYS_BY_NAME`.
- Produces: `CreateTicketInput.tracker: TrackerKey`.
- Produces: `TicketOutput.tracker: TrackerKey` and `TicketOutput.tracker_name: str`.
- Produces: `_tracker_id(tracker: TrackerKey) -> int`, resolving the allowlisted name through `/trackers.json`.
- Removes: `report_required`, `customer_visit_required`, and all automatic priority escalation code.

- [ ] **Step 1: Update backend fixtures and write failing creation-contract tests**

Update `tests/conftest.py` so every issue contains a tracker object, the tracker list is:

```python
MOCK_TRACKERS = [
    {"id": 3, "name": "問い合わせ"},
    {"id": 4, "name": "報告書"},
    {"id": 5, "name": "客先同行"},
]
```

Remove legacy custom fields from mocked issues and `/custom_fields.json`. Add parameterized tests to `tests/test_tickets.py`:

```python
@pytest.mark.parametrize(("tracker", "tracker_id"), [
    ("inquiry", 3),
    ("report", 4),
    ("customer_visit", 5),
])
def test_create_ticket_maps_allowed_tracker_key(client, tracker, tracker_id):
    response = client.post("/tickets", json={
        "tracker": tracker,
        "subject": "新規依頼",
        "description": "詳細",
    })
    assert response.status_code == 200
    request = next(call.request for call in respx.calls
                   if call.request.method == "POST" and call.request.url.path == "/issues.json")
    assert json.loads(request.content)["issue"]["tracker_id"] == tracker_id


@pytest.mark.parametrize("payload", [
    {"subject": "件名", "description": "本文"},
    {"tracker": "Bug", "subject": "件名", "description": "本文"},
])
def test_create_ticket_rejects_missing_or_unknown_tracker(client, payload):
    assert client.post("/tickets", json=payload).status_code == 422
```

Add a missing-config test that replaces the `/trackers.json` mock with only `問い合わせ`, posts `tracker="report"`, and expects HTTP 503 with `報告書` in the detail. Assert creation custom fields contain `顧客ID` plus only the selected tracker's completion field for support sessions.

- [ ] **Step 2: Write failing output and tracker-specific update tests**

Assert ticket detail/list output contains:

```python
assert data["tracker"] == "report"
assert data["tracker_name"] == "報告書"
assert "report_required" not in data
assert "customer_visit_required" not in data
```

Add tests proving `report_delivered` is returned/accepted only for `report`, `schedule_assigned` only for `customer_visit`, and either mismatched completion field returns HTTP 422 without sending a Redmine PUT. Keep the existing sales-role 403 tests for support-only fields.

- [ ] **Step 3: Run focused backend tests and verify they fail**

Run:

```bash
uv run --group test pytest tests/test_tickets.py tests/test_helpers.py tests/test_api_contract.py -q
```

Expected: FAIL on missing tracker schema/model fields and legacy field behavior.

- [ ] **Step 4: Add tracker types to the domain, mapper, presenter, and schemas**

In `backend/domain/models/ticket.py`, define:

```python
from typing import Literal

TrackerKey = Literal["inquiry", "report", "customer_visit"]
TRACKER_NAMES: dict[TrackerKey, str] = {
    "inquiry": "問い合わせ",
    "report": "報告書",
    "customer_visit": "客先同行",
}
TRACKER_KEYS_BY_NAME = {name: key for key, name in TRACKER_NAMES.items()}
```

Add `tracker: TrackerKey` and `tracker_name: str` to `Ticket`; remove the two legacy values from `TicketCustomFields`. Update `issue_to_ticket` to read `issue["tracker"]["name"]` and map it through `TRACKER_KEYS_BY_NAME`. Update `ticket_to_output` and Pydantic `TicketOutput` with the two tracker fields. Make `CreateTicketInput.tracker` required, remove deprecated `tracker_id` and both legacy booleans, and remove both booleans from `UpdateCustomFieldsInput`.

- [ ] **Step 5: Resolve tracker keys and build tracker-specific custom-field payloads**

In `backend/app.py`, import `TRACKER_NAMES` and add:

```python
async def _tracker_id(tracker: TrackerKey) -> int:
    async with httpx.AsyncClient(
        base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0
    ) as client:
        response = await client.get("/trackers.json")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="トラッカー設定を取得できませんでした")
    expected_name = TRACKER_NAMES[tracker]
    match = next(
        (item for item in response.json().get("trackers", [])
         if item.get("name") == expected_name),
        None,
    )
    if match is None:
        raise HTTPException(status_code=503, detail=f"トラッカーが設定されていません: {expected_name}")
    return int(match["id"])
```

Remove the `REDMINE_TRACKER_ID` environment requirement. In `create_ticket`, set `tracker_id = await _tracker_id(ticket_data.tracker)`, always send `customer_id`, and include only `report_delivered` for `report` or `schedule_assigned` for `customer_visit` when the current user is support. Delete priority auto-escalation imports, helper, constants, and branches.

For custom-field updates, fetch the current issue when either completion field is present, validate its tracker name against the field, and return HTTP 422 with a Japanese mismatch message before building the Redmine PUT. Preserve author reassignment and `対応済` behavior for a valid completion update.

- [ ] **Step 6: Delete obsolete policy/helper code and update audit expectations**

Remove `PRIORITY_ESCALATION_FIELDS`, `UnknownPriorityError`, `next_priority_id`, and `_next_priority_id`. Delete their tests. Update audit metadata tests so only `顧客ID`, `報告書渡し済み`, and `予定・担当者アサイン済み` are recognized, with support-only entries still hidden from sales users.

- [ ] **Step 7: Run the backend suite**

Run: `uv run --group test pytest tests/ --tb=short`

Expected: all backend tests PASS with no references to the removed request fields except explicit migration/bootstrap assertions.

- [ ] **Step 8: Commit the backend contract change**

```bash
git add backend tests/conftest.py tests/test_tickets.py tests/test_helpers.py tests/test_api_contract.py
git commit -m "feat: create tickets by tracker type"
```

---

### Task 3: Expose tracker selection and tracker-specific controls in React

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/TicketCreate.tsx`
- Create: `frontend/src/pages/TicketCreate.test.tsx`
- Modify: `frontend/src/pages/TicketDetail.tsx`
- Create: `frontend/src/pages/TicketDetail.test.tsx`
- Modify: `frontend/src/pages/TicketList.tsx`
- Modify: `frontend/src/pages/AnswerTicketList.tsx`
- Modify: `frontend/src/pages/TicketList.test.ts`

**Interfaces:**
- Produces: `export type TrackerKey = 'inquiry' | 'report' | 'customer_visit'`.
- Produces: `Ticket.tracker: TrackerKey` and `Ticket.tracker_name: string`.
- Consumes: required backend creation field `tracker` and tracker-specific optional completion fields.

- [ ] **Step 1: Write a failing ticket-creation component test**

Mock `createTicket` and `getTicketPriorityOptions`, render `TicketCreate` inside `MemoryRouter`, then select `報告書`, enter subject/body, submit, and assert:

```typescript
expect(createTicketMock).toHaveBeenCalledWith(expect.objectContaining({
  tracker: 'report',
  subject: '月次報告書',
  description: '作成してください',
}))
expect(screen.queryByLabelText('報告書が必要')).not.toBeInTheDocument()
expect(screen.queryByLabelText('客先同行が必要')).not.toBeInTheDocument()
```

Also assert the selector exposes exactly `問い合わせ`, `報告書`, and `客先同行`.

- [ ] **Step 2: Write failing detail tests for tracker-specific completion controls**

Mock the API calls used by `TicketDetail`. Render a support user with a report ticket and assert only `報告書を渡した` exists; repeat with a customer-visit ticket and assert only `予定・担当者をアサインした` exists; render an inquiry ticket and assert neither exists. In every case, assert the tracker Japanese name appears in the header.

- [ ] **Step 3: Run the focused frontend tests and verify they fail**

Run:

```bash
npm test --prefix frontend -- src/pages/TicketCreate.test.tsx src/pages/TicketDetail.test.tsx
```

Expected: FAIL because tracker fields and selector do not exist.

- [ ] **Step 4: Update the TypeScript API contract and creation form**

In `frontend/src/api/client.ts`:

```typescript
export type TrackerKey = 'inquiry' | 'report' | 'customer_visit'

export interface Ticket {
  id: number
  subject: string
  description: string
  status: string
  priority: number
  priority_name: string
  tracker: TrackerKey
  tracker_name: string
  assignee: { id: number; name: string } | null
  latest_support_responder?: { id: number; name: string } | null
  created_on?: string
  updated_on?: string
  notes?: Array<{ body: string; author: string; created_on: string }>
  audit_log?: AuditEntry[]
  customer_id: string
  report_delivered?: boolean
  schedule_assigned?: boolean
}
```

Remove the two legacy properties from `TicketCustomFields`. Make `createTicket` accept `{ tracker: TrackerKey; subject: string; description: string; priority?: number } & TicketCustomFields`.

In `TicketCreate.tsx`, replace both checkbox states and the escalation notice with a required select whose value is a `TrackerKey`, defaulting to `inquiry`. Submit `tracker`; only include `report_delivered` when `tracker === 'report'` and only include `schedule_assigned` when `tracker === 'customer_visit'`.

- [ ] **Step 5: Render tracker-specific detail controls and tracker labels**

Initialize `customFields` with `customer_id` plus only the completion value relevant to `t.tracker`. Add `トラッカー: {ticket.tracker_name}` to the detail metadata. Guard support-only controls with both role and tracker:

```tsx
{user.roles.includes('support') && ticket.tracker === 'report' && (
  <label>
    <input
      type="checkbox"
      checked={customFields.report_delivered ?? false}
      onChange={event => setCustomFields({
        ...customFields,
        report_delivered: event.target.checked,
      })}
    /> 報告書を渡した
  </label>
)}
{user.roles.includes('support') && ticket.tracker === 'customer_visit' && (
  <label>
    <input
      type="checkbox"
      checked={customFields.schedule_assigned ?? false}
      onChange={event => setCustomFields({
        ...customFields,
        schedule_assigned: event.target.checked,
      })}
    /> 予定・担当者をアサインした
  </label>
)}
```

Add a `トラッカー` column using `ticket.tracker_name` to both standard and responder tables. Update `TicketList.test.ts` fixture helper with tracker fields so type checking remains strict.

- [ ] **Step 6: Run all frontend unit tests and build**

Run:

```bash
npm test --prefix frontend
npm run build --prefix frontend
```

Expected: all Vitest tests PASS and Vite production build succeeds.

- [ ] **Step 7: Commit the frontend change**

```bash
git add frontend/src/api/client.ts frontend/src/pages/TicketCreate.tsx frontend/src/pages/TicketCreate.test.tsx frontend/src/pages/TicketDetail.tsx frontend/src/pages/TicketDetail.test.tsx frontend/src/pages/TicketList.tsx frontend/src/pages/AnswerTicketList.tsx frontend/src/pages/TicketList.test.ts
git commit -m "feat: select tracker when creating tickets"
```

---

### Task 4: Update end-to-end flows and operator documentation

**Files:**
- Modify: `frontend/e2e/workflow.ts`
- Modify: `frontend/e2e/ticket-creation.spec.ts`
- Modify: `frontend/e2e/requirements.spec.ts`
- Modify: `frontend/e2e/full-regression.spec.ts`
- Modify: `frontend/e2e/faq.spec.ts`
- Modify: `README.md`
- Modify: `docs/redmine.md`
- Modify: `docs/setup.md`
- Modify: `docs/architecture.md`
- Modify: `docs/scope.md`
- Modify: `docs/testing.md`
- Modify: `docs/changelog.md`

**Interfaces:**
- Consumes: creation-form selector labels `問い合わせ`, `報告書`, and `客先同行`.
- Removes: E2E helpers and prose based on `報告書が必要` or `客先同行が必要` checkboxes.

- [ ] **Step 1: Rewrite focused E2E expectations around tracker selection**

Replace `enableRequirement` with a helper that selects the `トラッカー` option before submission. Convert `requirements.spec.ts` into parameterized coverage for `報告書` and `客先同行` ticket creation, asserting the selected tracker is visible on detail and list screens. Update the full regression to create separate specialized tickets instead of toggling both flags on one issue. Update FAQ expected answers to mention creating the matching tracker ticket.

- [ ] **Step 2: Update documentation and configuration tables**

Remove every behavioral statement that describes requirement checkboxes or their priority escalation. Document:

- the three mutually exclusive trackers;
- separate tickets when both specialized workflows are required;
- report delivery and schedule assignment fields only on their matching trackers;
- the one-time deletion of existing project issues during legacy-field migration;
- removal of `REDMINE_TRACKER_ID` from configuration;
- the renamed/reworked focused E2E command coverage.

Do not rewrite unrelated historical changelog entries; add a new dated entry describing the migration and adjust only current-state tables that would otherwise be false.

- [ ] **Step 3: Scan for stale behavior references**

Run:

```bash
rg -n "報告書要否|客先同行要否|報告書が必要|客先同行が必要|REDMINE_TRACKER_ID|report_required|customer_visit_required" . -g '!docs/superpowers/**' -g '!frontend/package-lock.json' -g '!uv.lock'
```

Expected: matches remain only in the explicit legacy migration and any changelog history intentionally retained. Fix every current-code, test, seed, or current-state documentation match.

- [ ] **Step 4: Run complete verification**

Run:

```bash
uv run --group test pytest tests/ --tb=short
npm test --prefix frontend
npm run build --prefix frontend
./scripts/validate-helm.sh
```

If a local Redmine stack is available, additionally run the destructive migration integration check against disposable data:

```bash
docker compose up -d --build
runn run tests/init_test.yaml
```

Expected: all automated suites pass; the optional integration test finds all three trackers and no legacy runtime behavior.

- [ ] **Step 5: Commit E2E and documentation updates**

```bash
git add frontend/e2e README.md docs
git commit -m "docs: describe tracker-based request workflow"
```

---

### Task 5: Final consistency and completion review

**Files:**
- Review: all files changed in Tasks 1-4

**Interfaces:**
- Consumes: all tracker, API, UI, migration, and documentation behavior above.
- Produces: a verified branch ready for integration.

- [ ] **Step 1: Inspect the complete diff for accidental scope changes**

Run:

```bash
git status --short
git diff --stat HEAD~4..HEAD
git diff HEAD~4..HEAD
```

Confirm no dependencies, tracker-specific routes/pages, unrelated refactors, or user-owned changes were added.

- [ ] **Step 2: Re-run the mandatory verification commands from a clean shell**

Run:

```bash
uv run --group test pytest tests/ --tb=short
npm test --prefix frontend
npm run build --prefix frontend
./scripts/validate-helm.sh
```

Expected: every command exits 0 with current output captured for the handoff.

- [ ] **Step 3: Review commit history and working tree**

Run:

```bash
git log -5 --oneline
git status --short
```

Expected: the design and plan commits plus the implementation commits are present; the working tree is clean unless it contained unrelated user changes before implementation.
