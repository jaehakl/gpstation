from __future__ import annotations

import time
import uuid
from typing import Any

import jwt

from app.settings import settings
from app.user_auth.db import User


def _now() -> int:
    return int(time.time())


def make_token(sub: str, ttl_sec: int, extra: dict[str, Any] | None = None) -> str:
    now = _now()
    payload = {
        "sub": sub,
        "iat": now,
        "nbf": now - 5,
        "exp": now + ttl_sec,
        "jti": str(uuid.uuid4()),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def make_access(user: User) -> str:
    role = user.role or "unauthorized"
    return make_token(
        str(user.id),
        settings.access_ttl_sec,
        {
            "role": role,
            "roles": [role],
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status,
            "is_active": user.status == "active",
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        },
    )


def make_refresh(user_id: str, session_id: str) -> str:
    return make_token(user_id, settings.refresh_ttl_sec, {"typ": "refresh", "sid": session_id})


def verify_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_alg],
        options={"require": ["exp", "iat", "nbf", "sub"]},
        leeway=30,
    )
