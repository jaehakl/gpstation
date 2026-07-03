from datetime import datetime
from decimal import Decimal
from typing import Any, List, Literal, Optional

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, field_serializer

from utils.datetime_utils import serialize_datetime_utc

UserRole = Literal["admin", "user", "unauthorized"]


class BaseModel(PydanticBaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetimes(self, value: Any) -> Any:
        return serialize_datetime_utc(value)


class UserData(BaseModel):
    id: str
    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    password_hash: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    credit_balance: Optional[Decimal] = None
    credit_pending: Optional[Decimal] = None
    credit_withdrawable: Optional[Decimal] = None
    trust_score: Optional[Decimal] = None
    trust_tier: Optional[str] = None
    success_job_count: Optional[int] = None
    failed_job_count: Optional[int] = None
    disputed_job_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    roles: List[str] = Field(default_factory=list)


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    password_hash: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[str] = None
    credit_balance: Optional[Decimal] = None
    credit_pending: Optional[Decimal] = None
    credit_withdrawable: Optional[Decimal] = None
    trust_score: Optional[Decimal] = None
    trust_tier: Optional[str] = None
    success_job_count: Optional[int] = None
    failed_job_count: Optional[int] = None
    disputed_job_count: Optional[int] = None
    last_login_at: Optional[datetime] = None
    metadata_json: Optional[dict[str, Any]] = None
