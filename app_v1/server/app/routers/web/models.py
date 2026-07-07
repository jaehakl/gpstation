from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import AccessKeyScope


class CrudListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset: int = Field(default=0, ge=0)
    limit: int | None = Field(default=100, ge=1, le=1000)
    selected_ids: list[str] = Field(default_factory=list)
    search_text: str | None = None
    text_filter: dict[str, list[str]] = Field(default_factory=dict)
    filter: dict[str, list[Any]] = Field(default_factory=dict)
    sort: list[str] | None = None


class CrudListResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


class CrudUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, Any]]


class CrudUpsertResponse(BaseModel):
    id: str


class CrudDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str]


class CrudDeleteResponse(BaseModel):
    deleted: int


class AccessKeyData(BaseModel):
    id: str
    user_id: str
    key_type: str
    name: str
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class AccessKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scopes: list[AccessKeyScope] = Field(default_factory=lambda: ["client", "launcher"])
    expires_at: Optional[datetime] = None


class AccessKeyCreateResult(BaseModel):
    access_key: AccessKeyData
    secret: str
