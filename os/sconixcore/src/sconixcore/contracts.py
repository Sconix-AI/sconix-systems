from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class PrincipalKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"
    CI = "ci"


class Risk(StrEnum):
    READ_ONLY = "read-only"
    LOCAL_WRITE = "local-write"
    EXTERNAL_WRITE = "external-write"
    DESTRUCTIVE = "destructive"


class ApprovalMode(StrEnum):
    NEVER = "never"
    POLICY = "policy"
    ALWAYS = "always"


class DecisionOutcome(StrEnum):
    ALLOW = "allow"
    ALLOW_ONCE = "allow-once"
    DENY = "deny"
    DEFER = "defer"


@dataclass(frozen=True)
class Principal:
    kind: PrincipalKind
    id: str
    role: str | None = None
    intent: str | None = None
    scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("principal id is required")

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        value["scope"] = list(self.scope)
        return {key: item for key, item in value.items() if item is not None}


@dataclass(frozen=True)
class Verification:
    checks: tuple[str, ...]
    within_seconds: int = 30
    attempts: int = 3
    interval_seconds: float = 2

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValueError("at least one verification check is required")
        if self.within_seconds < 1 or self.attempts < 1 or self.interval_seconds < 0:
            raise ValueError("invalid verification timing")

    def as_dict(self) -> dict[str, Any]:
        return {
            "checks": list(self.checks),
            "withinSeconds": self.within_seconds,
            "attempts": self.attempts,
            "intervalSeconds": self.interval_seconds,
        }


@dataclass(frozen=True)
class ActionSpec:
    name: str
    argv: tuple[str, ...]
    risk: Risk
    idempotent: bool
    approval: ApprovalMode
    verification: Verification
    side_effects: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    rollback: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.argv:
            raise ValueError("action name and argv are required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "arguments": self.arguments,
            "risk": self.risk.value,
            "sideEffects": list(self.side_effects),
            "preconditions": list(self.preconditions),
            "idempotent": self.idempotent,
            "approval": self.approval.value,
            "verification": self.verification.as_dict(),
            "rollback": self.rollback,
        }


@dataclass(frozen=True)
class Decision:
    outcome: DecisionOutcome
    decided_by: Principal
    decided_at: str
    reason: str | None = None
    expires_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value = {
            "outcome": self.outcome.value,
            "decidedBy": self.decided_by.as_dict(),
            "decidedAt": self.decided_at,
            "reason": self.reason,
            "expiresAt": self.expires_at,
        }
        return {key: item for key, item in value.items() if item is not None}
