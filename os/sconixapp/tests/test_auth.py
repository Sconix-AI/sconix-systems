"""Auth router: signup / login / me / logout against a real in-memory session."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel

from sconixapp.auth import User, build_auth_router, make_current_user_id
from sconixapp.db import dispose_engine, get_engine, init_engine


class _Settings:
    jwt_secret = "test-secret-at-least-32-bytes-long-xxxxx"
    jwt_algorithm = "HS256"
    refresh_token_ttl_s = 3600
    environment = "test"

    @property
    def is_prod(self) -> bool:
        return False


def test_table_registered() -> None:
    assert "users" in SQLModel.metadata.tables
    assert User.__tablename__ == "users"


@pytest.fixture()
async def client():
    init_engine("sqlite+aiosqlite:///:memory:")
    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    app = FastAPI()
    app.include_router(build_auth_router(settings=_Settings()))
    uid_dep = make_current_user_id(_Settings())

    @app.get("/whoami")
    async def whoami(uid: str = Depends(uid_dep)) -> dict:
        return {"uid": uid}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as c:
        yield c
    await dispose_engine()


async def test_signup_login_me_logout(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/signup", json={"email": "A@x.com", "password": "hunter2!!"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "a@x.com"  # lower-cased

    assert (await client.get("/api/auth/me")).json()["email"] == "a@x.com"
    assert (await client.get("/whoami")).json()["uid"]

    dup = await client.post(
        "/api/auth/signup", json={"email": "a@x.com", "password": "hunter2!!"}
    )
    assert dup.status_code == 409

    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401

    bad = await client.post(
        "/api/auth/login", json={"email": "a@x.com", "password": "wrong"}
    )
    assert bad.status_code == 401
    good = await client.post(
        "/api/auth/login", json={"email": "a@x.com", "password": "hunter2!!"}
    )
    assert good.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_short_password_rejected(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/signup", json={"email": "b@x.com", "password": "short"}
    )
    assert r.status_code == 422
