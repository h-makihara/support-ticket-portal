from dataclasses import asdict
from typing import Any

from backend.domain.models.ticket import Ticket


def ticket_to_output(ticket: Ticket, *, include_support_only: bool) -> dict[str, Any]:
    """Apply field-level visibility while mapping a Ticket to the public contract."""
    fields = ticket.custom_fields
    result: dict[str, Any] = {
        "id": ticket.id,
        "tracker": ticket.tracker,
        "tracker_name": ticket.tracker_name,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "priority_name": ticket.priority_name,
        "assignee": asdict(ticket.assignee) if ticket.assignee else None,
        "created_on": ticket.created_on,
        "updated_on": ticket.updated_on,
        "customer_id": fields.customer_id,
    }
    if ticket.tracker == "customer_visit":
        result["visit_mode"] = fields.visit_mode or None
        result["preferred_start_at_1"] = fields.preferred_start_at_1 or None
        result["preferred_start_at_2"] = fields.preferred_start_at_2 or None
        result["meeting_duration_minutes"] = fields.meeting_duration_minutes
    if include_support_only:
        if ticket.tracker == "report":
            result["report_delivered"] = fields.report_delivered
        elif ticket.tracker == "customer_visit":
            result["schedule_assigned"] = fields.schedule_assigned
    return result
