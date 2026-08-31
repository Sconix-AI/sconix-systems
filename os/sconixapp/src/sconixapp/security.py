"""Password hashing (argon2) + stateless JWT access/refresh tokens.

This is the token *model* from STACK.md, not a full auth system — ``fastapi-users``
(wired in the template) handles registration, OAuth, verification and reset and
can be pointed at these helpers, or you can use them directly for a minimal API.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


def needs_rehash(hashed: str) -> bool:
    return _hasher.verify_and_update(hashed, hashed)[1] is not None


def create_token(
    subject: str,
    *,
    secret: str,
    token_type: TokenType = "access",
    ttl_s: int,
    algorithm: str = "HS256",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_s),
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(
    token: str,
    *,
    secret: str,
    algorithms: list[str] | None = None,
    expected_type: TokenType | None = None,
) -> dict[str, Any]:
    """Decode + verify. Raises ``jwt.InvalidTokenError`` on anything wrong."""
    claims = jwt.decode(token, secret, algorithms=algorithms or ["HS256"])
    if expected_type is not None and claims.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token, got {claims.get('type')!r}")
    return claims
