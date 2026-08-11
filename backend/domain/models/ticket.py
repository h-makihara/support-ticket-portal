"""Ticket aggregate values independent of FastAPI and Redmine."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Assignee:
    id: int
    name: str


@dataclass(frozen=True)
class TicketCustomFields:
    customer_id: str = ""
    report_required: bool = False
    report_delivered: bool = False
    customer_visit_required: bool = False
    schedule_assigned: bool = False


@dataclass(frozen=True)
class Ticket:
    id: int
    subject: str
    description: str
    status: str
    priority: int
    priority_name: str
    assignee: Assignee | None
    created_on: str
    updated_on: str
    custom_fields: TicketCustomFields
