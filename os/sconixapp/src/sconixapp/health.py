"""A drop-in ``/healthz`` + ``/readyz`` router.

    from sconixapp.health import health_router
    app.include_router(health_router)

``/healthz`` is liveness (process up). ``/readyz`` is readiness (DB + Redis
reachable) — point your load balancer / uptime check at ``/readyz``.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from sconixapp import __version__
from sconixapp.db import get_engine

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "sconixapp": __version__}


@health_router.get("/readyz")
async def readyz() -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("select 1"))
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
        checks["db"] = f"error: {exc.__class__.__name__}"

    try:
        import redis.asyncio as aioredis

        from sconixapp.config import get_settings

        client = aioredis.from_url(str(get_settings().redis_url))
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"

    ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
