"""Fast, no-IO tests for the batteries. `cd ~/systems/os/sconixapp && task test`."""

from __future__ import annotations

import jwt
import pytest

from sconixapp import Settings, __version__, configure_logging, get_logger
from sconixapp.security import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-at-least-32-bytes-long-for-hs256"


def test_version() -> None:
    assert __version__


def test_settings_defaults_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings()
    assert s.environment == "dev"
    assert s.is_prod is False

    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("APP_NAME", "billing-thing")
    s2 = Settings()
    assert s2.environment == "prod"
    assert s2.is_prod is True
    assert s2.app_name == "billing-thing"


def test_password_roundtrip() -> None:
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip_and_type_guard() -> None:
    tok = create_token("user-123", secret=SECRET, token_type="access", ttl_s=60)
    claims = decode_token(tok, secret=SECRET, expected_type="access")
    assert claims["sub"] == "user-123"
    assert claims["type"] == "access"
    assert "jti" in claims

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tok, secret=SECRET, expected_type="refresh")

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tok, secret="other-secret")


def test_expired_token_rejected() -> None:
    tok = create_token("u", secret=SECRET, ttl_s=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(tok, secret=SECRET)


def test_logging_configures() -> None:
    configure_logging(json=True, level="INFO")
    get_logger("test").info("hello", k="v")


def test_health_router_importable() -> None:
    from sconixapp.health import health_router

    routes = {r.path for r in health_router.routes}
    assert {"/healthz", "/readyz"} <= routes
