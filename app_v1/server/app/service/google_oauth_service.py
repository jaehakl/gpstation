from __future__ import annotations

import asyncio

import requests
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import settings
from app.user_auth.db import Identity, OAuthProvider, User

TOKEN_URL = "https://oauth2.googleapis.com/token"
PROVIDER = OAuthProvider.google


async def exchange_google_code(*, code: str, redirect_uri: str, code_verifier: str | None) -> requests.Response:
    return await asyncio.to_thread(
        requests.post,
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        },
        timeout=10,
    )


async def verify_google_identity(id_token: str | None, nonce: str | None) -> dict:
    def verify() -> dict:
        identity = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.google_client_id,
            clock_skew_in_seconds=settings.google_id_token_clock_skew_seconds,
        )
        if nonce and identity.get("nonce") != nonce:
            raise ValueError("nonce mismatch")
        return identity

    return await asyncio.to_thread(verify)


async def resolve_oauth_user(db: AsyncSession, idinfo: dict) -> User:
    provider_user_id = str(idinfo["sub"])
    email = idinfo.get("email")
    email_verified = bool(idinfo.get("email_verified", False))
    display_name = idinfo.get("name")

    identity = await db.scalar(
        select(Identity).where(Identity.provider == PROVIDER, Identity.provider_user_id == provider_user_id)
    )
    if identity is not None:
        user = await db.get(User, identity.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="identity user not found")
    else:
        user = None
        if email and email_verified:
            user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if user is None:
            user = User(email=email, display_name=display_name, role="unauthorized", status="active")
            db.add(user)
            await db.flush()
        identity = Identity(
            user_id=user.id,
            provider=PROVIDER,
            provider_user_id=provider_user_id,
            email=email,
            email_verified=email_verified,
            raw_profile=idinfo,
        )
        db.add(identity)

    if not user.display_name and display_name:
        user.display_name = display_name
    identity.email = email
    identity.email_verified = email_verified
    identity.raw_profile = idinfo
    return user
