"""No-network tests for sconixapp.billing (pure helpers + wiring shape)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sconixapp.billing import (
    BillingCustomer,
    Subscription,
    build_billing_router,
    plan_of,
    require_plan,
)
from sconixapp.db import get_session


class _Settings:
    stripe_secret_key = "sk_test_dummy"
    stripe_webhook_secret = "whsec_dummy"


def test_tables_registered() -> None:
    from sqlmodel import SQLModel

    assert "billing_customers" in SQLModel.metadata.tables
    assert "billing_subscriptions" in SQLModel.metadata.tables
    assert BillingCustomer.__tablename__ == "billing_customers"


def test_subscription_is_live() -> None:
    future = datetime.now(UTC) + timedelta(days=5)
    past = datetime.now(UTC) - timedelta(days=1)
    assert Subscription(
        user_id="u",
        stripe_subscription_id="s1",
        status="active",
        plan="pro",
        current_period_end=future,
    ).is_live
    assert not Subscription(
        user_id="u",
        stripe_subscription_id="s2",
        status="active",
        plan="pro",
        current_period_end=past,
    ).is_live
    assert not Subscription(
        user_id="u",
        stripe_subscription_id="s3",
        status="canceled",
        plan="pro",
        current_period_end=future,
    ).is_live


def test_plan_of_prefers_lookup_key_then_metadata_then_default() -> None:
    assert plan_of({"items": {"data": [{"price": {"lookup_key": "team"}}]}}) == "team"
    assert plan_of({"items": {"data": [{"price": {"metadata": {"plan": "starter"}}}]}}) == "starter"
    assert plan_of({"items": {"data": [{"price": {}}]}}) == "pro"
    assert plan_of({}) == "pro"


def test_require_plan_returns_dependency_callable() -> None:
    dep = require_plan("pro", get_user_id=lambda: "u")
    assert callable(dep)


def test_router_builds_and_exposes_routes() -> None:
    router = build_billing_router(
        get_user_id=lambda: "user-1", settings=_Settings(), default_price_id="price_x"
    )
    paths = {r.path for r in router.routes}
    assert {"/api/billing/checkout", "/api/billing/portal", "/api/billing/webhook"} <= paths

    # webhook with a bogus signature must 400 (not 500) — signature check runs
    # before the session is touched, so a stub get_session is enough
    app = FastAPI()
    app.include_router(router)

    async def _fake_session():
        yield None

    app.dependency_overrides[get_session] = _fake_session
    resp = TestClient(app).post(
        "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=bad"}
    )
    assert resp.status_code == 400


def test_missing_secret_key_raises() -> None:
    class NoKey:
        stripe_secret_key = None

    with pytest.raises(RuntimeError):
        build_billing_router(get_user_id=lambda: "u", settings=NoKey())
