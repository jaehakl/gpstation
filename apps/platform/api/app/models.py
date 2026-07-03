from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel as PydanticBaseModel
from pydantic import EmailStr, Field, field_serializer

from utils.datetime_utils import serialize_datetime_utc


class BaseModel(PydanticBaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetimes(self, value: Any) -> Any:
        return serialize_datetime_utc(value)


class UserData(BaseModel):
    id: str
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    roles: List[str] = Field(default_factory=list)
