from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import OkResponse, UserData
from app.service.user_service import ALLOWED_USER_ROLES, user_to_data
from app.settings import settings
from app.user_auth.db import Identity, OAuthProvider, OAuthState, Session as AuthSession, User
from app.user_auth.utils.auth_utils import hash_token, pkce_challenge, pop_return_to_cookie, random_urlsafe, set_return_to_cookie
from app.user_auth.utils.jwt import make_access, make_refresh, verify_token

router = APIRouter(prefix="/auth", tags=["web-auth"])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"
PROVIDER = OAuthProvider.google


@router.get("/google/start")
async def google_start(return_to: str | None = None, db: AsyncSession = Depends(get_db)):
    ensure_google_configured()
    state = random_urlsafe(32)
    nonce = random_urlsafe(32)
    code_verifier = random_urlsafe(64)
    challenge = pkce_challenge(code_verifier)
    redirect_uri = google_redirect_uri()

    db.add(
        OAuthState(
            provider=PROVIDER,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )
    )
    await db.commit()

    resp = RedirectResponse(url="/")
    set_return_to_cookie(resp, return_to)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    resp.headers["Location"] = f"{AUTH_URL}?{urlencode(params)}"
    resp.status_code = status.HTTP_307_TEMPORARY_REDIRECT
    return resp


@router.get("/google/callback")
async def google_callback(
    request: Request,
    state: str = "",
    code: str = "",
    db: AsyncSession = Depends(get_db),
):
    ensure_google_configured()
    if not state or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing state or code")

    oauth_state = await db.scalar(select(OAuthState).where(OAuthState.state == state))
    if oauth_state is None or oauth_state.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or used state")

    token_response = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": oauth_state.redirect_uri or google_redirect_uri(),
            "grant_type": "authorization_code",
            "code_verifier": oauth_state.code_verifier,
        },
        timeout=10,
    )
    if token_response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"token exchange failed: {token_response.text}")

    try:
        request_adapter = google_requests.Request()
        idinfo = google_id_token.verify_oauth2_token(
            token_response.json().get("id_token"),
            request_adapter,
            settings.google_client_id,
            clock_skew_in_seconds=settings.google_id_token_clock_skew_seconds,
        )
        if oauth_state.nonce and idinfo.get("nonce") != oauth_state.nonce:
            raise ValueError("nonce mismatch")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"id_token verification failed: {exc}") from exc

    user = await resolve_oauth_user(db, idinfo)
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    oauth_state.consumed_at = datetime.now(timezone.utc)
    session_id = create_auth_session(db, user, request)
    await db.flush()
    await db.refresh(user)

    access = make_access(user)
    refresh = make_refresh(str(user.id), session_id)
    await db.commit()

    return_to = request.cookies.get("rt") or settings.app_base_url
    resp = RedirectResponse(return_to)
    set_auth_cookies(resp, access, refresh)
    pop_return_to_cookie(resp)
    return resp


@router.get("/me", response_model=UserData)
async def check_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserData:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        claims = verify_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc
    if claims.get("typ") == "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is not an access token")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing sub")
    user = await db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    if user.role not in ALLOWED_USER_ROLES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user role")
    return user_to_data(user)


@router.get("/refresh", response_model=OkResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> OkResponse:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    claims = verify_refresh_claims(refresh_token)
    session_id = claims["sid"]
    auth_session = await get_active_auth_session(db, session_id)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked")

    user = await db.get(User, claims["sub"])
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    auth_session.last_seen_at = datetime.now(timezone.utc)

    set_auth_cookies(response, make_access(user), make_refresh(str(user.id), session_id))
    await db.commit()
    return OkResponse()


@router.post("/logout", response_model=OkResponse)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> OkResponse:
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            claims = verify_refresh_claims(refresh_token)
            auth_session = await get_active_auth_session(db, claims["sid"])
            if auth_session is not None:
                auth_session.revoked_at = datetime.now(timezone.utc)
                await db.commit()
        except HTTPException:
            pass

    kwargs = auth_cookie_kwargs()
    response.delete_cookie("access_token", path="/", **kwargs)
    response.delete_cookie("refresh_token", path="/", **kwargs)
    return OkResponse()


async def resolve_oauth_user(db: AsyncSession, idinfo: dict) -> User:
    provider_user_id = str(idinfo["sub"])
    email = idinfo.get("email")
    email_verified = bool(idinfo.get("email_verified", False))
    display_name = idinfo.get("name")

    identity = await db.scalar(select(Identity).where(Identity.provider == PROVIDER, Identity.provider_user_id == provider_user_id))
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


def create_auth_session(db: AsyncSession, user: User, request: Request) -> str:
    session_id = random_urlsafe(32)
    client = request.client
    db.add(
        AuthSession(
            user_id=user.id,
            session_id_hash=hash_token(session_id),
            ip=client.host if client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    return session_id


async def get_active_auth_session(db: AsyncSession, session_id: str) -> AuthSession | None:
    session_hash = hash_token(session_id)
    auth_session = await db.scalar(select(AuthSession).where(AuthSession.session_id_hash == session_hash))
    if auth_session is None or auth_session.revoked_at is not None:
        return None
    return auth_session


def verify_refresh_claims(refresh_token: str) -> dict:
    try:
        claims = verify_token(refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid refresh: {exc}") from exc
    if claims.get("typ") != "refresh" or not claims.get("sid"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")
    return claims


def ensure_google_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Google OAuth is not configured")


def google_redirect_uri() -> str:
    return settings.google_redirect_uri or f"{settings.public_base_url}/web/auth/google/callback"


def auth_cookie_kwargs() -> dict:
    kwargs = {"httponly": True, "secure": settings.secure_cookies, "samesite": "lax"}
    cookie_domain = settings.cookie_domain.strip()
    if cookie_domain and cookie_domain.lower() not in {"localhost", "127.0.0.1"}:
        kwargs["domain"] = cookie_domain
    return kwargs


def set_auth_cookies(resp: Response, access: str, refresh_token: str) -> None:
    kwargs = auth_cookie_kwargs()
    resp.set_cookie("access_token", access, max_age=settings.access_ttl_sec, path="/", **kwargs)
    resp.set_cookie("refresh_token", refresh_token, max_age=settings.refresh_ttl_sec, path="/", **kwargs)
