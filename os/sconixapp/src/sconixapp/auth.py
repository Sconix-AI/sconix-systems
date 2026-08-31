"""Minimal email + password auth: signup, login (httpOnly cookie), logout, me.

    from sconixapp.auth import build_auth_router, make_current_user_id, User

    app.include_router(build_auth_router(settings=settings))
    CurrentUser = Annotated[str, Depends(make_current_user_id(settings))]

    @router.get("/things")
    async def mine(uid: CurrentUser, session: Session): ...   # 401 if signed out

    # app models.py — expose the table to Alembic autogenerate
    from sconixapp.auth import User  # noqa: F401

No email verification in v1 — add magic-link later. Uses ``sconixapp.security``
for argon2 hashing + JWT, and ``settings.jwt_secret`` / ``jwt_algorithm`` /
``refresh_token_ttl_s`` (all on the base ``Settings``).
"""

# No `from __future__ import annotations`: FastAPI resolves route annotations via
# get_type_hints against module globals, and the per-router `Uid = Annotated[...]`
# alias is function-local — under PEP 563 it degrades to an unresolved string and
# the dependency is misread as a query param. Same reason as billing.py.

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel, select

from sconixapp.db import get_session
from sconixapp.security import create_token, decode_token, hash_password, verify_password

COOKIE = "session"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Credentials(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _issue_cookie(response: Response, user_id: str, settings: Any) -> None:
    token = create_token(
        user_id,
        secret=settings.jwt_secret,
        token_type="access",
        ttl_s=settings.refresh_token_ttl_s,
        algorithm=settings.jwt_algorithm,
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.refresh_token_ttl_s,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )


def make_current_user_id(settings: Any):
    """Dependency factory → returns the signed-in user's id, else 401."""

    def _dep(request: Request) -> str:
        token = request.cookies.get(COOKIE)
        if not token:
            raise HTTPException(401, "not signed in")
        try:
            claims = decode_token(
                token,
                secret=settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                expected_type="access",
            )
        except jwt.InvalidTokenError as exc:
            raise HTTPException(401, "invalid session") from exc
        return str(claims["sub"])

    return _dep


async def _get_user(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "account no longer exists")
    return user


def build_auth_router(*, settings: Any, prefix: str = "/api/auth") -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["auth"])
    current_user_id = make_current_user_id(settings)
    Uid = Annotated[str, Depends(current_user_id)]

    @router.post("/signup", response_model=UserOut, status_code=201)
    async def signup(body: Credentials, response: Response, session: SessionDep) -> User:
        email = body.email.lower()
        exists = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if exists is not None:
            raise HTTPException(409, "an account with that email already exists")
        if len(body.password) < 8:
            raise HTTPException(422, "password must be at least 8 characters")
        user = User(email=email, hashed_password=hash_password(body.password))
        session.add(user)
        await session.flush()
        _issue_cookie(response, user.id, settings)
        return user

    @router.post("/login", response_model=UserOut)
    async def login(body: Credentials, response: Response, session: SessionDep) -> User:
        user = (
            await session.execute(
                select(User).where(User.email == body.email.lower())
            )
        ).scalar_one_or_none()
        if user is None or not verify_password(body.password, user.hashed_password):
            raise HTTPException(401, "wrong email or password")
        _issue_cookie(response, user.id, settings)
        return user

    @router.post("/logout", status_code=204)
    async def logout(response: Response) -> None:
        response.delete_cookie(COOKIE, path="/")

    @router.get("/me", response_model=UserOut)
    async def me(uid: Uid, session: SessionDep) -> User:
        return await _get_user(session, uid)

    @router.delete("/me", status_code=204)
    async def delete_me(uid: Uid, response: Response, session: SessionDep) -> None:
        user = await _get_user(session, uid)
        await session.delete(user)
        await session.flush()
        response.delete_cookie(COOKIE, path="/")

    return router
