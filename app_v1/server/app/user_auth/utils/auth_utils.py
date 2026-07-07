import base64
import hashlib
import os

from fastapi import Response


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def random_urlsafe(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(nbytes)).rstrip(b"=").decode("ascii")


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def set_return_to_cookie(resp: Response, url: str | None) -> None:
    if not url:
        return
    resp.set_cookie(
        key="rt",
        value=url,
        max_age=600,
        httponly=False,
        secure=False,
        samesite="lax",
        path="/",
    )


def pop_return_to_cookie(resp: Response) -> None:
    resp.delete_cookie(key="rt", path="/")
