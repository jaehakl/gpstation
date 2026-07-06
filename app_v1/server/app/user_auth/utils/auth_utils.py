import base64
import hashlib
import os


def random_urlsafe(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(nbytes)).rstrip(b"=").decode("ascii")


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
