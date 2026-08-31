"""Stripe subscription billing: checkout, customer portal, webhook, entitlement gate.

Stripe is the source of truth. The webhook writes local rows; every other path
reads them, so the request hot path never calls Stripe.

    # app: wire the router (get_user_id is your auth dependency -> str)
    from sconixapp.billing import build_billing_router, require_plan

    app.include_router(build_billing_router(
        get_user_id=get_current_user_id,
        settings=settings,
        default_price_id="price_123",       # your Stripe price
    ))

    @router.post("/reports")
    async def make_report(sub=Depends(require_plan("pro", get_user_id=get_current_user_id))):
        ...

    # app: expose the tables to Alembic autogenerate
    from sconixapp.billing import BillingCustomer, Subscription  # noqa: F401

``settings`` must carry ``stripe_secret_key`` and ``stripe_webhook_secret`` (both
on the base :class:`sconixapp.Settings`).
"""

# NOTE: no `from __future__ import annotations` here. FastAPI resolves route
# annotations via get_type_hints against the module globals; the per-router
# `UserId = Annotated[str, Depends(get_user_id)]` alias is function-local, so
# under PEP 563 it becomes an unresolvable ForwardRef and OpenAPI generation
# blows up. Keeping annotations eager avoids that.

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel, select
from starlette.concurrency import run_in_threadpool

from sconixapp.db import get_session
from sconixapp.logging import get_logger

try:  # stripe >= 11 exposes it at the top level; older keeps it under .error
    from stripe import SignatureVerificationError
except ImportError:  # pragma: no cover
    from stripe.error import SignatureVerificationError  # type: ignore

log = get_logger("sconixapp.billing")

UserIdDep = Callable[..., Awaitable[str]] | Callable[..., str]
_LIVE_STATUSES = {"active", "trialing"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ts() -> Column:
    """A fresh tz-aware TIMESTAMP column (Postgres rejects naive datetimes)."""
    return Column(DateTime(timezone=True), nullable=False)


# --- tables -----------------------------------------------------------------


class BillingCustomer(SQLModel, table=True):
    __tablename__ = "billing_customers"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, unique=True)
    stripe_customer_id: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_ts())


class Subscription(SQLModel, table=True):
    __tablename__ = "billing_subscriptions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    stripe_subscription_id: str = Field(index=True, unique=True)
    status: str  # active | trialing | past_due | canceled | incomplete | ...
    plan: str  # internal plan key (price lookup_key or price.metadata.plan)
    current_period_end: datetime = Field(sa_column=_ts())
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_ts())
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=_ts())

    @property
    def is_live(self) -> bool:
        cpe = self.current_period_end
        # SQLite hands back naive datetimes even for timezone=True columns;
        # Postgres hands back aware. Normalise before comparing.
        if cpe.tzinfo is None:
            cpe = cpe.replace(tzinfo=UTC)
        return self.status in _LIVE_STATUSES and cpe > _utcnow()


# --- service --------------------------------------------------------------


def configure_stripe(secret_key: str | None) -> None:
    if not secret_key:
        raise RuntimeError("stripe_secret_key is not set")
    stripe.api_key = secret_key


async def _call(fn: Callable[..., Any], /, **kwargs: Any) -> Any:
    """Run a blocking stripe SDK call off the event loop."""
    return await run_in_threadpool(lambda: fn(**kwargs))


def _plain(obj: Any) -> dict[str, Any]:
    """A nested plain dict from a Stripe resource. stripe-python >= 8 raises on
    ``dict(obj)`` / ``obj.get(...)``; ``str(obj)`` is its JSON form."""
    if isinstance(obj, dict):
        return obj
    return json.loads(str(obj))


async def _customer_id(session: AsyncSession, user_id: str, email: str | None) -> str:
    row = (
        await session.execute(select(BillingCustomer).where(BillingCustomer.user_id == user_id))
    ).scalar_one_or_none()
    if row is not None:
        return row.stripe_customer_id
    cust = await _call(stripe.Customer.create, email=email, metadata={"user_id": user_id})
    session.add(BillingCustomer(user_id=user_id, stripe_customer_id=cust["id"]))
    await session.flush()
    return cust["id"]


async def create_checkout_session(
    *,
    session: AsyncSession,
    user_id: str,
    email: str | None,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    customer_id = await _customer_id(session, user_id, email)
    cs = await _call(
        stripe.checkout.Session.create,
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,
        allow_promotion_codes=True,
    )
    return cs["url"]


async def create_portal_session(*, session: AsyncSession, user_id: str, return_url: str) -> str:
    row = (
        await session.execute(select(BillingCustomer).where(BillingCustomer.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "no billing customer for this user")
    ps = await _call(
        stripe.billing_portal.Session.create,
        customer=row.stripe_customer_id,
        return_url=return_url,
    )
    return ps["url"]


async def active_subscription(session: AsyncSession, user_id: str) -> Subscription | None:
    rows = (
        (await session.execute(select(Subscription).where(Subscription.user_id == user_id)))
        .scalars()
        .all()
    )
    return next((s for s in rows if s.is_live), None)


def plan_of(stripe_subscription: dict[str, Any]) -> str:
    """Internal plan key for a Stripe subscription: price lookup_key, then
    ``price.metadata.plan``, then ``"pro"``."""
    items = (stripe_subscription.get("items") or {}).get("data") or []
    if items:
        price = items[0].get("price") or {}
        return price.get("lookup_key") or (price.get("metadata") or {}).get("plan") or "pro"
    return "pro"


def _period_end(sub: Any) -> datetime:
    """``current_period_end`` moved from the Subscription onto its items in the
    2025+ API versions; fall back to the top-level field for older ones."""
    items = (sub.get("items") or {}).get("data") or []
    ts = None
    if items:
        ts = items[0].get("current_period_end")
    if ts is None:
        ts = sub.get("current_period_end")
    return datetime.fromtimestamp(int(ts), tz=UTC) if ts else _utcnow()


async def _upsert_subscription(session: AsyncSession, sub: Any) -> None:
    """``sub`` is a Stripe ``Subscription`` object or an equivalent mapping."""
    customer_id = sub["customer"]
    cust = (
        await session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == customer_id)
        )
    ).scalar_one_or_none()
    if cust is not None:
        user_id = cust.user_id
    else:  # customer created out-of-band — fall back to its metadata
        c = await _call(stripe.Customer.retrieve, id=customer_id)
        user_id = (c.get("metadata") or {}).get("user_id")
        if user_id:
            session.add(BillingCustomer(user_id=user_id, stripe_customer_id=customer_id))
    if not user_id:
        log.warning("billing.webhook.no_user", customer=customer_id)
        return

    values = {
        "user_id": user_id,
        "stripe_subscription_id": sub["id"],
        "status": sub["status"],
        "plan": plan_of(sub),
        "current_period_end": _period_end(sub),
        "updated_at": _utcnow(),
    }
    existing = (
        await session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub["id"])
        )
    ).scalar_one_or_none()
    if existing is not None:
        for key, val in values.items():
            setattr(existing, key, val)
    else:
        session.add(Subscription(**values))
    await session.flush()


async def handle_webhook(
    *, payload: bytes, sig_header: str, webhook_secret: str, session: AsyncSession
) -> str:
    """Verify + apply one Stripe webhook event. Returns the event type."""
    try:
        stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, SignatureVerificationError) as exc:
        raise HTTPException(400, f"invalid webhook: {exc.__class__.__name__}") from exc

    event = json.loads(payload)  # verified above; use plain dicts, not StripeObjects
    etype = event["type"]
    obj = event["data"]["object"]

    if etype.startswith("customer.subscription."):
        await _upsert_subscription(session, obj)
    elif etype == "checkout.session.completed" and obj.get("subscription"):
        full = await _call(stripe.Subscription.retrieve, id=obj["subscription"])
        await _upsert_subscription(session, _plain(full))
    else:
        log.debug("billing.webhook.ignored", type=etype)
    return etype


# --- FastAPI wiring -----------------------------------------------------------

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class CheckoutIn(BaseModel):
    success_url: str
    cancel_url: str
    email: str | None = None
    price_id: str | None = None


class PortalIn(BaseModel):
    return_url: str


def build_billing_router(
    *,
    get_user_id: UserIdDep,
    settings: Any,
    default_price_id: str | None = None,
    prefix: str = "/api/billing",
) -> APIRouter:
    """Router with ``POST {prefix}/checkout|portal|webhook``. The webhook route
    is unauthenticated (Stripe signs it); the other two use ``get_user_id``."""
    configure_stripe(getattr(settings, "stripe_secret_key", None))
    router = APIRouter(prefix=prefix, tags=["billing"])
    UserId = Annotated[str, Depends(get_user_id)]

    @router.post("/checkout")
    async def checkout(  # noqa: D401
        body: CheckoutIn,
        session: SessionDep,
        user_id: UserId,
    ) -> dict[str, str]:
        price_id = body.price_id or default_price_id
        if not price_id:
            raise HTTPException(400, "no price_id (pass one or set default_price_id)")
        url = await create_checkout_session(
            session=session,
            user_id=user_id,
            email=body.email,
            price_id=price_id,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
        return {"url": url}

    @router.post("/portal")
    async def portal(body: PortalIn, session: SessionDep, user_id: UserId) -> dict[str, str]:
        url = await create_portal_session(
            session=session, user_id=user_id, return_url=body.return_url
        )
        return {"url": url}

    @router.post("/webhook")
    async def webhook(request: Request, session: SessionDep) -> dict[str, str]:
        etype = await handle_webhook(
            payload=await request.body(),
            sig_header=request.headers.get("stripe-signature", ""),
            webhook_secret=getattr(settings, "stripe_webhook_secret", "") or "",
            session=session,
        )
        return {"received": etype}

    return router


def require_plan(plan: str, *, get_user_id: UserIdDep):
    """FastAPI dependency: 402 unless the caller has a live subscription on
    ``plan`` (use ``plan="any"`` for "any live subscription"). Returns the
    :class:`Subscription`."""

    UserId = Annotated[str, Depends(get_user_id)]

    async def _dep(session: SessionDep, user_id: UserId) -> Subscription:
        sub = await active_subscription(session, user_id)
        if sub is None or (plan != "any" and sub.plan != plan):
            raise HTTPException(402, f"requires the '{plan}' plan")
        return sub

    return _dep
