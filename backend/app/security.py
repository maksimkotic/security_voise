from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import hashlib
import hmac
import secrets
import time
from .config import settings

hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def issue_token(user_id: int, role: str) -> str:
    expires = int(time.time()) + 3600
    payload = f"{user_id}:{role}:{expires}:{secrets.token_urlsafe(12)}"
    signature = hmac.new(settings().secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def read_token(token: str) -> tuple[int, str] | None:
    try:
        payload, signature = token.rsplit(":", 1)
        expected = hmac.new(settings().secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        user_id, role, expires, _ = payload.split(":", 3)
        if not hmac.compare_digest(signature, expected) or int(expires) < time.time():
            return None
        return int(user_id), role
    except (ValueError, TypeError):
        return None
