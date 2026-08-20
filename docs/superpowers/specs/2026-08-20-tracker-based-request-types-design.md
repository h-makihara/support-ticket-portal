# Tracker-based Request Types Design

## Goal

Replace the `報告書要否` and `客先同行要否` issue custom fields with three mutually exclusive Redmine trackers: `問い合わせ`, `報告書`, and `客先同行`. A portal ticket belongs to exactly one of these trackers; users create separate tickets when both a report and a customer visit are required.

## Redmine Provisioning and One-time Migration

- Provision all three trackers idempotently from the existing Redmine bootstrap scripts and attach them to the support project.
- Give each tracker the existing `対応待ち` default status and the same role workflows currently used by `問い合わせ`.
- Attach `顧客ID` to all three trackers.
- Attach the support-only `報告書渡し済み` field only to `報告書`.
- Attach the support-only `予定・担当者アサイン済み` field only to `客先同行`.
- Stop creating `報告書要否` and `客先同行要否`.
- When either legacy field is still attached to the support project, run a one-time transaction that deletes every existing issue in that project and then deletes both legacy fields. The absence of those fields is the migration marker, so later bootstrap runs do not delete newly created issues.
- Keep the Compose bootstrap file and its Helm copy identical.

Existing tickets are intentionally discarded rather than converted because one legacy ticket could have both flags enabled while the new model permits only one tracker.

## API and Domain Model

- Replace the ignored numeric `tracker_id` creation input with a required tracker key limited to `inquiry`, `report`, or `customer_visit`.
- Resolve the selected key on the server against the corresponding Redmine tracker name. Never accept an arbitrary tracker ID from the browser.
- Return HTTP 503 with a clear configuration error if a required tracker cannot be found in Redmine; invalid tracker keys remain normal request-validation errors.
- Include both the stable tracker key and its Japanese display name in ticket responses so all portal screens can render the type without duplicating inference logic.
- Remove `report_required` and `customer_visit_required` from creation, update, domain, presentation, and audit custom-field definitions.
- Remove the priority escalation behavior that depended on those two flags.
- Keep `report_delivered` and `schedule_assigned` support-only. The portal exposes and updates `report_delivered` only for report tickets and `schedule_assigned` only for customer-visit tickets.

## Portal UI

- Add a required tracker selector to the existing ticket creation form with `問い合わせ`, `報告書`, and `客先同行` options.
- Remove the two requirement checkboxes and their priority-escalation notice.
- Show the ticket tracker in the standard ticket list, responder list, and ticket detail header.
- In the detail form, show `報告書を渡した` only for a report ticket and `予定・担当者をアサインした` only for a customer-visit ticket. Continue to show both fields only to support users.
- Keep the existing form, routes, status workflow, assignment behavior, and FAQ subsystem rather than introducing tracker-specific pages.

## Documentation

Update the README and relevant setup, Redmine, architecture, scope, testing, changelog, and FAQ seed text so they describe selecting a tracker instead of checking requirement fields. Environment-specific numeric IDs are not added because the server resolves the three allowed tracker names from Redmine.

## Verification

- Bootstrap assertions verify all three trackers, their workflow coverage, custom-field associations, and removal of the two legacy fields.
- Backend tests verify each accepted tracker key maps to the correct Redmine tracker, arbitrary or missing values are rejected, missing Redmine configuration returns an error, removed fields are absent, and completion fields remain role-restricted.
- Frontend tests verify tracker selection is submitted and tracker-specific completion controls are rendered correctly.
- Existing backend and frontend suites must pass after their fixtures and assertions are updated.
- Run the deployment bootstrap checks that cover both the Compose and Helm copies.

Success means a new ticket can be created under exactly one of the three allowed trackers, the chosen tracker is visible throughout the portal, and the two legacy requirement fields no longer exist or influence priority.
