"""Async SQLAlchemy/SQLModel engine + session, wired for FastAPI DI.

    # app main.py
    from sconixapp.db import init_engine, dispose_engine, get_session

    @asynccontextmanager
    async def lifespan(app):
        init_engine(settings.database_url)
        yield
        await dispose_engine()

    # in a route
    async def handler(session: AsyncSession = Depends(get_session)):
        ...

Models subclass ``sqlmodel.SQLModel``; migrations are Alembic (see the template's
``api/alembic/``). Nothing here creates tables — that's migrations' job.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create the process-wide engine + sessionmaker. Call once at startup.

    Postgres (prod) gets a real pool. SQLite (``sqlite+aiosqlite://``, for
    zero-Docker local dev) skips pool args, which its dialect rejects.
    """
    global _engine, _sessionmaker
    url = str(database_url)
    kwargs: dict = {"echo": echo}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_pre_ping=True, pool_size=5, max_overflow=10)
    _engine = create_async_engine(url, **kwargs)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("engine not initialised — call init_engine() in lifespan")
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, rolled back on error."""
    if _sessionmaker is None:
        raise RuntimeError("engine not initialised — call init_engine() in lifespan")
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
