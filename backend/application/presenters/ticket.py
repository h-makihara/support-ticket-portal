from dataclasses import asdict
from typing import Any

from backend.domain.models.ticket import Ticket


def ticket_to_output(ticket: Ticket, *, include_support_only: bool) -> dict[str, Any]:
    """Apply field-level visibility while mapping a Ticket to the public contract."""
    fields = ticket.custom_fields
    result: dict[str, Any] = {
        "id": ticket.id,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "priority_name": ticket.priority_name,
        "assignee": asdict(ticket.assignee) if ticket.assignee else None,
        "created_on": ticket.created_on,
        "updated_on": ticket.updated_on,
        "customer_id": fields.customer_id,
        "report_required": fields.report_required,
        "customer_visit_required": fields.customer_visit_required,
    }
    if include_support_only:
        result.update(
            report_delivered=fields.report_delivered,
            schedule_assigned=fields.schedule_assigned,
        )
    return result
