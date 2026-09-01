from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from sconixcore import (
    ActionSpec,
    ApprovalMode,
    Decision,
    DecisionOutcome,
    Principal,
    PrincipalKind,
    Risk,
    Verification,
)
from sconixcore.manifest import _schema_text


def test_principal_uses_general_kind_and_specific_role() -> None:
    principal = Principal(
        kind=PrincipalKind.AGENT,
        id="pilot",
        role="ops",
        intent="recover unhealthy apps",
        scope=("relnotes", "skillforge"),
    )
    assert principal.as_dict()["kind"] == "agent"
    assert principal.as_dict()["role"] == "ops"


def test_restart_action_contract() -> None:
    action = ActionSpec(
        name="restart_app",
        argv=("sx", "restart", "relnotes"),
        risk=Risk.EXTERNAL_WRITE,
        idempotent=True,
        approval=ApprovalMode.POLICY,
        verification=Verification(
            checks=("healthz", "readyz"), within_seconds=60, attempts=6, interval_seconds=5
        ),
        side_effects=("restart app containers in place",),
        preconditions=("target unhealthy this run", "cooldown clear"),
    )
    value = action.as_dict()
    assert value["argv"] == ["sx", "restart", "relnotes"]
    assert value["risk"] == "external-write"
    assert value["verification"]["attempts"] == 6


def test_decision_records_accountable_principal() -> None:
    operator = Principal(PrincipalKind.HUMAN, "yusuf")
    decision = Decision(
        DecisionOutcome.ALLOW_ONCE,
        operator,
        datetime.now(UTC).isoformat(),
        reason="approved for this incident",
    )
    assert decision.as_dict()["decidedBy"]["id"] == "yusuf"


def test_contracts_reject_missing_identity_or_checks() -> None:
    with pytest.raises(ValueError, match="principal id"):
        Principal(PrincipalKind.SERVICE, " ")
    with pytest.raises(ValueError, match="verification check"):
        Verification(())


def test_project_schema_accepts_argv_and_retry_verification() -> None:
    import json

    schema = json.loads(_schema_text())
    manifest = {
        "schema": "sconix.dev/project/v1",
        "kind": "application",
        "name": "Demo",
        "slug": "demo",
        "lifecycle": {"status": "active"},
        "commands": {
            "restart": {
                "run": ["sx", "restart", "demo"],
                "risk": "external-write",
                "approval": "policy",
                "verify": {"checks": ["healthz"], "withinSeconds": 30, "attempts": 3},
            }
        },
    }
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(manifest))
    assert errors == []
