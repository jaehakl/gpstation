from __future__ import annotations

from fastapi import Response

from app.settings import settings

OAUTH_STATE_COOKIE = "oauth_state"
RETURN_TO_COOKIE = "rt"


def auth_cookie_kwargs() -> dict:
    kwargs = {"httponly": True, "secure": settings.secure_cookies, "samesite": "lax"}
    cookie_domain = settings.cookie_domain.strip()
    if cookie_domain and cookie_domain.lower() not in {"localhost", "127.0.0.1"}:
        kwargs["domain"] = cookie_domain
    return kwargs


def set_auth_cookies(response: Response, access: str, refresh_token: str) -> None:
    set_access_cookie(response, access)
    kwargs = auth_cookie_kwargs()
    response.set_cookie("refresh_token", refresh_token, max_age=settings.refresh_ttl_sec, path="/", **kwargs)


def set_access_cookie(response: Response, access: str) -> None:
    response.set_cookie("access_token", access, max_age=settings.access_ttl_sec, path="/", **auth_cookie_kwargs())


def delete_auth_cookies(response: Response) -> None:
    kwargs = auth_cookie_kwargs()
    response.delete_cookie("access_token", path="/", **kwargs)
    response.delete_cookie("refresh_token", path="/", **kwargs)


def set_oauth_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=settings.oauth_state_ttl_seconds, path="/", **auth_cookie_kwargs())


def set_return_to_cookie(response: Response, return_to: str) -> None:
    response.set_cookie(RETURN_TO_COOKIE, return_to, max_age=settings.oauth_state_ttl_seconds, path="/", **auth_cookie_kwargs())


def clear_oauth_temp_cookies(response: Response) -> None:
    kwargs = auth_cookie_kwargs()
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/", **kwargs)
    response.delete_cookie(RETURN_TO_COOKIE, path="/", **kwargs)


def clear_auth_cookies(response: Response) -> None:
    delete_auth_cookies(response)
