from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import requests

from db import SessionLocal
from models import UserData
from settings import settings
from user_auth.db import Identity, OAuthProvider, OAuthState, User
from user_auth.utils.auth_utils import pop_return_to_cookie, pkce_challenge, random_urlsafe, set_return_to_cookie
from user_auth.utils.jwt import make_access, make_refresh, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"
PROVIDER = OAuthProvider.google


async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


@router.get("/google/start")
async def google_start(request: Request, return_to: str | None = None, db: AsyncSession = Depends(get_db)):
    state = random_urlsafe(32)
    nonce = random_urlsafe(32)
    code_verifier = random_urlsafe(64)
    challenge = pkce_challenge(code_verifier)

    db.add(
        OAuthState(
            provider=PROVIDER,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=settings.google_redirect_uri,
        )
    )
    await db.commit()

    resp = RedirectResponse(url="/")
    set_return_to_cookie(resp, return_to)

    from urllib.parse import urlencode

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    resp.headers["Location"] = f"{AUTH_URL}?{urlencode(params)}"
    resp.status_code = 307
    return resp


@router.get("/google/callback")
async def google_callback(request: Request, state: str = "", code: str = "", db: AsyncSession = Depends(get_db)):
    if not state or not code:
        raise HTTPException(400, "missing state or code")

    st = await db.scalar(select(OAuthState).where(OAuthState.state == state))
    if not st or st.consumed_at is not None:
        raise HTTPException(400, "invalid or used state")

    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": st.redirect_uri or settings.google_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": st.code_verifier,
    }
    tok = requests.post(TOKEN_URL, data=data, timeout=10)
    if tok.status_code != 200:
        raise HTTPException(400, f"token exchange failed: {tok.text}")

    try:
        req = google_requests.Request()
        idinfo = google_id_token.verify_oauth2_token(tok.json().get("id_token"), req, settings.google_client_id)
        if st.nonce and idinfo.get("nonce") != st.nonce:
            raise ValueError("nonce mismatch")
    except Exception as exc:
        raise HTTPException(400, f"id_token verification failed: {exc}") from exc

    sub = idinfo["sub"]
    email = idinfo.get("email")
    email_verified = bool(idinfo.get("email_verified", False))
    name = idinfo.get("name")

    ident = await db.scalar(select(Identity).where(Identity.provider == PROVIDER, Identity.provider_user_id == sub))
    if ident:
        user = await db.get(User, ident.user_id)
        if user is None:
            raise HTTPException(400, "identity user not found")
    else:
        user = None
        if email and email_verified:
            user = await db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if user is None:
            user = User(
                email=email,
                display_name=name,
                role="user",
                status="active",
            )
            db.add(user)
            await db.flush()

        ident = Identity(
            user_id=user.id,
            provider=PROVIDER,
            provider_user_id=sub,
            email=email,
            email_verified=email_verified,
            raw_profile=idinfo,
        )
        db.add(ident)

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    if not user.display_name and name:
        user.display_name = name
    user.last_login_at = datetime.now(timezone.utc)
    ident.email = email
    ident.email_verified = email_verified
    ident.raw_profile = idinfo
    st.consumed_at = func.now()
    await db.flush()
    await db.refresh(user)

    access = make_access(user)
    refresh = make_refresh(str(user.id))
    await db.commit()

    return_to = request.cookies.get("rt") or settings.app_base_url
    resp = RedirectResponse(return_to)
    set_auth_cookies(resp, access, refresh)
    pop_return_to_cookie(resp)
    return resp


@router.get("/me", response_model=UserData)
async def check_user(request: Request) -> UserData:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

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
        raise HTTPException(status_code=401, detail="Token missing sub")

    status_value = claims.get("status") or ("active" if claims.get("is_active", True) else "inactive")
    if status_value != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    role = claims.get("role")
    roles = claims.get("roles") or ([role] if role else [])
    return UserData(
        id=str(user_id),
        email=claims.get("email"),
        username=claims.get("username"),
        display_name=claims.get("display_name"),
        role=role,
        status=status_value,
        is_active=status_value == "active",
        created_at=claims.get("created_at"),
        updated_at=claims.get("updated_at"),
        last_login_at=claims.get("last_login_at"),
        roles=roles,
    )


@router.get("/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    rtoken = request.cookies.get("refresh_token")
    if not rtoken:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        claims = verify_token(rtoken)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid refresh: {exc}") from exc

    if claims.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    user_id = claims["sub"]
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="User inactive")
    await db.refresh(user)

    access = make_access(user)
    refresh_new = make_refresh(user_id)

    kwargs = auth_cookie_kwargs()
    response.set_cookie("access_token", access, max_age=settings.ACCESS_TTL_SEC, path="/", **kwargs)
    response.set_cookie("refresh_token", refresh_new, max_age=settings.REFRESH_TTL_SEC, path="/", **kwargs)
    return {"ok": True}


@router.post("/logout")
async def logout(resp: Response):
    kwargs = auth_cookie_kwargs()
    resp.delete_cookie("access_token", path="/", **kwargs)
    resp.delete_cookie("refresh_token", path="/", **kwargs)
    return {"ok": True}


def auth_cookie_kwargs():
    kwargs = {"httponly": True, "secure": settings.SECURE_COOKIES, "samesite": "lax"}
    cookie_domain = settings.COOKIE_DOMAIN.strip()
    if cookie_domain and cookie_domain.lower() not in {"localhost", "127.0.0.1"}:
        kwargs["domain"] = cookie_domain
    return kwargs


def set_auth_cookies(resp: Response, access: str, refresh: str):
    kwargs = auth_cookie_kwargs()
    resp.set_cookie("access_token", access, max_age=settings.ACCESS_TTL_SEC, path="/", **kwargs)
    resp.set_cookie("refresh_token", refresh, max_age=settings.REFRESH_TTL_SEC, path="/", **kwargs)
