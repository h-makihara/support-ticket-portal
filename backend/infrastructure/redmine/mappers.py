"""Anti-corruption mapping from Redmine issue JSON to the ticket domain."""

from typing import Any

from backend.domain.models.ticket import Assignee, Ticket, TicketCustomFields


def redmine_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def issue_custom_fields(
    issue: dict[str, Any], definitions: dict[str, dict[str, Any]], *, include_support_only: bool
) -> dict[str, Any]:
    values_by_name = {
        field.get("name"): field.get("value")
        for field in issue.get("custom_fields", [])
        if isinstance(field, dict)
    }
    result: dict[str, Any] = {}
    for key, definition in definitions.items():
        if definition["support_only"] and not include_support_only:
            continue
        value = values_by_name.get(definition["name"], "0" if definition["boolean"] else "")
        result[key] = redmine_bool(value) if definition["boolean"] else str(value or "")
    return result


def issue_to_ticket(issue: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> Ticket:
    assigned = issue.get("assigned_to")
    fields = issue_custom_fields(issue, definitions, include_support_only=True)
    return Ticket(
        id=int(issue["id"]), subject=issue.get("subject", ""), description=issue.get("description", ""),
        status=issue["status"]["name"], priority=int(issue["priority"]["id"]),
        priority_name=issue["priority"].get("name", ""),
        assignee=Assignee(id=int(assigned["id"]), name=assigned.get("name", "")) if assigned else None,
        created_on=issue.get("created_on", ""), updated_on=issue.get("updated_on", ""),
        custom_fields=TicketCustomFields(**fields),
    )
