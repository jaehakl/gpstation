import time
import uuid
from typing import Any, Dict

import jwt

from settings import settings
from user_auth.db import User


def _now() -> int:
    return int(time.time())


def make_token(sub: str, ttl_sec: int, extra: Dict[str, Any] | None = None) -> str:
    now = _now()
    payload = {
        "sub": sub,
        "iat": now,
        "nbf": now - 5,
        "exp": now + ttl_sec,
        "jti": str(uuid.uuid4()),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def make_access(user: User) -> str:
    role = user.role or "unauthorized"
    extra = {
        "role": role,
        "roles": [role],
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "status": user.status,
        "is_active": user.status == "active",
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }
    return make_token(str(user.id), settings.ACCESS_TTL_SEC, extra=extra)


def make_refresh(user_id: str) -> str:
    return make_token(user_id, settings.REFRESH_TTL_SEC, {"typ": "refresh"})


def verify_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALG],
        options={"require": ["exp", "iat", "nbf", "sub"]},
        leeway=30,
    )
