from pydantic import BaseModel, Field


class DetailOutput(BaseModel):
    detail: str = Field(description="処理結果またはエラーの説明")


class HealthOutput(BaseModel):
    status: str = Field(description="サービスの稼働状態", examples=["healthy"])


class PaginationOutput(BaseModel):
    limit: int = Field(ge=1, description="1ページの最大件数")
    offset: int = Field(ge=0, description="先頭からの取得開始位置")
    total_count: int = Field(ge=0, description="条件に一致する総件数")
    has_more: bool = Field(description="後続ページが存在するか")


class OptionOutput(BaseModel):
    id: int
    label: str


class PriorityOptionOutput(OptionOutput):
    is_default: bool
