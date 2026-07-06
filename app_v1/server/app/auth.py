from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.settings import get_settings


@dataclass(frozen=True)
class Principal:
    token: str
    user_id: str
    scopes: frozenset[str]

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def token_from_authorization(authorization: str) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    return authorization.split(" ", 1)[1].strip()


def authenticate_token(token: str) -> Principal:
    entry = get_settings().tokens.get(token)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return Principal(token=token, user_id=entry.user_id, scopes=frozenset(entry.scopes))


def authenticate_authorization(authorization: str) -> Principal:
    return authenticate_token(token_from_authorization(authorization))


async def require_client(authorization: str = Header(default="")) -> Principal:
    principal = authenticate_authorization(authorization)
    principal.require_scope("client")
    return principal
