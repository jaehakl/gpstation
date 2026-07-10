from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import OkResponse, UserData
from app.service.auth_audit_service import add_auth_audit
from app.service.auth_session_service import (
    can_authenticate_user,
    cleanup_expired_oauth_states,
    create_auth_session,
    get_active_auth_session,
    rotate_refresh_jti,
    validate_refresh_rotation,
)
from app.service.google_oauth_service import exchange_google_code, resolve_oauth_user, verify_google_identity
from app.routers.web.auth_cookies import (
    OAUTH_STATE_COOKIE,
    RETURN_TO_COOKIE,
    clear_auth_cookies,
    clear_oauth_temp_cookies,
    delete_auth_cookies,
    set_access_cookie,
    set_auth_cookies,
    set_oauth_state_cookie,
    set_return_to_cookie,
)
from app.service.user_service import user_to_data
from app.settings import google_redirect_uri_for, settings
from app.user_auth.db import OAuthProvider, OAuthState, User
from app.user_auth.utils.auth_utils import hash_token, pkce_challenge, random_urlsafe
from app.user_auth.utils.jwt import make_access, make_refresh, verify_token

router = APIRouter(prefix="/auth", tags=["web-auth"])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPES = "openid email profile"
PROVIDER = OAuthProvider.google
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_TOKEN_TTL_SECONDS = 3600


@router.get("/google/start")
async def google_start(return_to: str | None = None, db: AsyncSession = Depends(get_db)):
    ensure_google_configured()
    await cleanup_expired_oauth_states(db, ttl_seconds=settings.oauth_state_ttl_seconds)
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
    set_oauth_state_cookie(resp, state)
    set_return_to_cookie(resp, sanitize_return_to(return_to))
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
    if oauth_state is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or used state")
    validate_oauth_state_values(state, request.cookies.get(OAUTH_STATE_COOKIE), oauth_state)

    token_response = await exchange_google_code(
        code=code,
        redirect_uri=oauth_state.redirect_uri or google_redirect_uri(),
        code_verifier=oauth_state.code_verifier,
    )
    if token_response.status_code != status.HTTP_200_OK:
        add_auth_audit(
            db,
            "login_failure",
            request,
            provider=PROVIDER,
            details={"reason": "token_exchange_failed", "status": token_response.status_code},
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"token exchange failed: {token_response.text}")

    try:
        idinfo = await verify_google_identity(token_response.json().get("id_token"), oauth_state.nonce)
    except Exception as exc:
        add_auth_audit(db, "login_failure", request, provider=PROVIDER, details={"reason": "id_token_invalid"})
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"id_token verification failed: {exc}") from exc

    user = await resolve_oauth_user(db, idinfo)
    oauth_state.consumed_at = datetime.now(timezone.utc)
    if not can_authenticate_user(user):
        add_auth_audit(
            db,
            "login_failure",
            request,
            user_id=str(user.id),
            provider=PROVIDER,
            details={"reason": "approval_required"},
        )
        await db.commit()
        resp = RedirectResponse(approval_required_url())
        clear_auth_cookies(resp)
        clear_oauth_temp_cookies(resp)
        return resp

    refresh_jti = str(uuid.uuid4())
    session_id = create_auth_session(db, user, request, refresh_jti)
    await db.flush()
    await db.refresh(user)

    access = make_access(user)
    refresh = make_refresh(str(user.id), session_id, refresh_jti)
    add_auth_audit(db, "login_success", request, user_id=str(user.id), provider=PROVIDER)
    await db.commit()

    return_to = sanitize_return_to(request.cookies.get(RETURN_TO_COOKIE))
    resp = RedirectResponse(return_to)
    set_auth_cookies(resp, access, refresh)
    clear_oauth_temp_cookies(resp)
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
    if user is None or not can_authenticate_user(user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user_to_data(user)


@router.get("/csrf")
async def csrf_token(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    claims = verify_refresh_claims(refresh_token)
    session_id = claims["sid"]
    auth_session = await get_active_auth_session(db, session_id)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked")
    await validate_refresh_rotation(db, auth_session, claims)

    user = await db.get(User, claims["sub"])
    if user is None or not can_authenticate_user(user):
        auth_session.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    return {"csrf_token": make_csrf_token(session_id)}


@router.post("/refresh", response_model=OkResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> OkResponse:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    claims = verify_refresh_claims(refresh_token)
    session_id = claims["sid"]
    auth_session = await get_active_auth_session(db, session_id, for_update=True)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked")
    rotation_source = await validate_refresh_rotation(db, auth_session, claims)

    user = await db.get(User, claims["sub"])
    if user is None or not can_authenticate_user(user):
        auth_session.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    auth_session.last_seen_at = datetime.now(timezone.utc)
    access = make_access(user)
    if rotation_source == "current":
        next_refresh_jti = str(uuid.uuid4())
        rotate_refresh_jti(auth_session, next_refresh_jti)
        set_auth_cookies(response, access, make_refresh(str(user.id), session_id, next_refresh_jti))
    else:
        # A near-simultaneous request may carry the just-rotated token. It can
        # refresh access briefly, but must not overwrite the browser's newer
        # refresh cookie or advance the rotation family again.
        set_access_cookie(response, access)
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
                add_auth_audit(db, "logout", request, user_id=str(auth_session.user_id))
                await db.commit()
        except HTTPException:
            pass

    delete_auth_cookies(response)
    return OkResponse()


def verify_refresh_claims(refresh_token: str) -> dict:
    try:
        claims = verify_token(refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid refresh: {exc}") from exc
    if claims.get("typ") != "refresh" or not claims.get("sid"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")
    return claims


def validate_csrf_request(request: Request) -> None:
    refresh_token = request.cookies.get("refresh_token")
    csrf_token_value = request.headers.get(CSRF_HEADER_NAME)
    if not refresh_token or not csrf_token_value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token required")

    try:
        claims = verify_refresh_claims(refresh_token)
        token_session_hash = csrf_token_session_hash(csrf_token_value)
    except HTTPException as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token") from exc

    expected_session_hash = csrf_session_hash(claims["sid"])
    if not secrets.compare_digest(token_session_hash, expected_session_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def make_csrf_token(session_id: str, expires_at: int | None = None) -> str:
    expires = str(expires_at if expires_at is not None else int(time.time()) + CSRF_TOKEN_TTL_SECONDS)
    unsigned = f"{csrf_session_hash(session_id)}.{expires}.{random_urlsafe(16)}"
    return f"{unsigned}.{csrf_signature(unsigned)}"


def csrf_token_session_hash(token: str) -> str:
    parts = token.split(".")
    if len(parts) != 4:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    session_hash, expires, nonce, signature = parts
    unsigned = f"{session_hash}.{expires}.{nonce}"
    if not secrets.compare_digest(signature, csrf_signature(unsigned)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    try:
        expires_at = int(expires)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token") from exc
    if expires_at <= int(time.time()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Expired CSRF token")
    return session_hash


def csrf_session_hash(session_id: str) -> str:
    return base64.urlsafe_b64encode(hash_token(session_id)).rstrip(b"=").decode("ascii")


def csrf_signature(unsigned: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), unsigned.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def ensure_google_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Google OAuth is not configured")


def google_redirect_uri() -> str:
    return google_redirect_uri_for(settings)


def validate_oauth_state_values(query_state: str, cookie_state: str | None, oauth_state: OAuthState) -> None:
    if not query_state or not cookie_state or not secrets.compare_digest(query_state, cookie_state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state cookie mismatch")
    if oauth_state.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or used state")
    if normalize_utc(oauth_state.created_at) + timedelta(seconds=settings.oauth_state_ttl_seconds) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expired state")


def sanitize_return_to(return_to: str | None) -> str:
    app_base = settings.app_base_url.rstrip("/")
    if not return_to:
        return app_base
    candidate = return_to.strip()
    if candidate.startswith("/") and not candidate.startswith("//"):
        return f"{app_base}{candidate}"

    parsed_candidate = urlparse(candidate)
    parsed_app = urlparse(app_base)
    if (
        parsed_candidate.scheme == parsed_app.scheme
        and parsed_candidate.netloc == parsed_app.netloc
        and candidate.startswith(app_base)
    ):
        return candidate
    return app_base


def approval_required_url() -> str:
    return f"{settings.app_base_url.rstrip('/')}/login?approval_required=1"


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
