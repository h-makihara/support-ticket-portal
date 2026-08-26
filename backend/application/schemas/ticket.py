from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from backend.application.schemas.common import PaginationOutput
from backend.domain.models.ticket import TrackerKey, VisitMode


def validate_preferred_datetime(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("日時はYYYY-MM-DD hh:mm形式で入力してください")
    value = value.strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("日時はYYYY-MM-DD hh:mm形式で入力してください") from None
    if parsed.strftime("%Y-%m-%d %H:%M") != value:
        raise ValueError("日時はYYYY-MM-DD hh:mm形式で入力してください")
    return value


PreferredDatetime = Annotated[str | None, BeforeValidator(validate_preferred_datetime)]
MeetingDurationMinutes = Annotated[int, Field(strict=True, gt=0)]


class CreateTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracker: TrackerKey
    subject: str = Field(description="件名。空白除去後に必須")
    description: str = Field(description="問い合わせ内容。空白除去後に必須")
    priority: int | None = Field(default=None, description="Redmine優先度ID")
    customer_id: str = ""
    report_delivered: bool = Field(default=False, description="サポートロールのみ反映")
    schedule_assigned: bool = Field(default=False, description="サポートロールのみ反映")
    visit_mode: VisitMode | None = Field(default=None, description="客先同行で必須")
    preferred_start_at_1: PreferredDatetime = None
    preferred_start_at_2: PreferredDatetime = None
    meeting_duration_minutes: MeetingDurationMinutes | None = None


class UpdateCustomFieldsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    report_delivered: bool | None = None
    schedule_assigned: bool | None = None
    visit_mode: VisitMode | None = None
    preferred_start_at_1: PreferredDatetime = None
    preferred_start_at_2: PreferredDatetime = None
    meeting_duration_minutes: MeetingDurationMinutes | None = None


class AddCommentInput(BaseModel):
    body: str = Field(description="コメント本文。空白除去後に必須")


class UpdateStatusInput(BaseModel):
    status_id: int = Field(description="RedmineステータスID")


class UpdatePriorityInput(BaseModel):
    priority_id: int = Field(description="Redmine優先度ID")


class PersonOutput(BaseModel):
    id: int
    name: str


class NoteOutput(BaseModel):
    body: str
    author: str
    created_on: str


class AuditChangeOutput(BaseModel):
    field: str
    display_field: str
    old_value: Any = None
    new_value: Any = None


class AuditEntryOutput(BaseModel):
    type: Literal["comment", "change", "both"]
    author: str
    created_on: str
    comment: str | None = None
    changes: list[AuditChangeOutput]


class TicketOutput(BaseModel):
    id: int
    tracker: TrackerKey
    tracker_name: str
    subject: str
    description: str
    status: str
    priority: int
    priority_name: str
    assignee: PersonOutput | None
    latest_support_responder: PersonOutput | None = None
    created_on: str = ""
    updated_on: str = ""
    notes: list[NoteOutput] | None = None
    audit_log: list[AuditEntryOutput] | None = None
    customer_id: str
    report_delivered: bool | None = None
    schedule_assigned: bool | None = None
    visit_mode: VisitMode | None = None
    preferred_start_at_1: str | None = None
    preferred_start_at_2: str | None = None
    meeting_duration_minutes: int | None = None


class TicketListOutput(BaseModel):
    tickets: list[TicketOutput]
    pagination: PaginationOutput
