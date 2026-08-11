from typing import Literal

from pydantic import BaseModel, Field


class LoginInput(BaseModel):
    username: str = Field(description="Redmineログイン名")
    password: str = Field(description="Redmineパスワード", json_schema_extra={"writeOnly": True})


class AuthUserOutput(BaseModel):
    id: int = Field(description="RedmineユーザーID")
    username: str
    name: str
    roles: list[str] = Field(description="ポータル内のロール")


class AuthSessionOutput(BaseModel):
    authenticated: Literal[True]
    user: AuthUserOutput
