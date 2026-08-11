from pydantic import BaseModel, Field

from backend.application.schemas.common import PaginationOutput


class FaqWriteInput(BaseModel):
    question: str = Field(description="質問。空文字・改行不可、正規化後200文字以内")
    answer: str = Field(description="回答。空文字不可")
    version: int | None = Field(default=None, description="更新時に必須の楽観ロック用バージョン")


class FaqOutput(BaseModel):
    id: str
    question: str
    answer: str
    version: int
    author: str
    created_on: str
    updated_on: str


class FaqListOutput(BaseModel):
    faqs: list[FaqOutput]
    pagination: PaginationOutput
