from __future__ import annotations

from app.models import UserData
from app.user_auth.db import User


def user_to_data(user: User) -> UserData:
    role = user.role or "unauthorized"
    return UserData(
        id=str(user.id),
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        role=role,
        status=user.status,
        is_active=user.status == "active",
        roles=[role],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
