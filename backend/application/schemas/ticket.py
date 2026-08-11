from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.application.schemas.common import PaginationOutput


class CreateTicketInput(BaseModel):
    subject: str = Field(description="件名。空白除去後に必須")
    description: str = Field(description="問い合わせ内容。空白除去後に必須")
    priority: int | None = Field(default=None, description="Redmine優先度ID")
    tracker_id: int | None = Field(default=None, deprecated=True, description="互換入力。サーバー設定値を使用するため無視される")
    customer_id: str = ""
    report_required: bool = False
    report_delivered: bool = Field(default=False, description="サポートロールのみ反映")
    customer_visit_required: bool = False
    schedule_assigned: bool = Field(default=False, description="サポートロールのみ反映")


class UpdateCustomFieldsInput(BaseModel):
    customer_id: str | None = None
    report_required: bool | None = None
    report_delivered: bool | None = None
    customer_visit_required: bool | None = None
    schedule_assigned: bool | None = None


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
    report_required: bool
    report_delivered: bool | None = None
    customer_visit_required: bool
    schedule_assigned: bool | None = None


class TicketListOutput(BaseModel):
    tickets: list[TicketOutput]
    pagination: PaginationOutput
