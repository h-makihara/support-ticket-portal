"""Ticket aggregate values independent of FastAPI and Redmine."""

from dataclasses import dataclass
from typing import Literal


TrackerKey = Literal["inquiry", "report", "customer_visit"]
VisitMode = Literal["オンライン", "オフライン"]
TRACKER_NAMES: dict[TrackerKey, str] = {
    "inquiry": "問い合わせ",
    "report": "報告書",
    "customer_visit": "客先同行",
}
TRACKER_KEYS_BY_NAME = {name: key for key, name in TRACKER_NAMES.items()}


@dataclass(frozen=True)
class Assignee:
    id: int
    name: str


@dataclass(frozen=True)
class TicketCustomFields:
    customer_id: str = ""
    report_delivered: bool = False
    schedule_assigned: bool = False
    visit_mode: str = ""


@dataclass(frozen=True)
class Ticket:
    id: int
    tracker: TrackerKey
    tracker_name: str
    subject: str
    description: str
    status: str
    priority: int
    priority_name: str
    assignee: Assignee | None
    created_on: str
    updated_on: str
    custom_fields: TicketCustomFields
