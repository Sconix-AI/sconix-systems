from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sconixcore.contracts import (
    ActionSpec,
    ApprovalMode,
    Decision,
    DecisionOutcome,
    Principal,
    Risk,
    Verification,
)

_PLACEHOLDER = re.compile(r"^\{([a-z][a-z0-9_]*)\}$")


class ActionError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    action: ActionSpec
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


Runner = Callable[[tuple[str, ...], Path], subprocess.CompletedProcess[str]]


def _verification(value: Mapping[str, Any] | None) -> Verification:
    if not value:
        return Verification(("exit-zero",))
    return Verification(
        tuple(value["checks"]),
        within_seconds=value.get("withinSeconds", 30),
        attempts=value.get("attempts", 3),
        interval_seconds=value.get("intervalSeconds", 2),
    )


def resolve_action(
    manifest: Mapping[str, Any], name: str, arguments: Mapping[str, str] | None = None
) -> ActionSpec:
    commands = manifest.get("commands", {})
    if name not in commands:
        raise ActionError(f"undeclared action: {name}")
    command = commands[name]
    project = str(manifest["slug"])
    supplied = dict(arguments or {})
    declared = set(command.get("arguments", []))
    missing = declared - supplied.keys()
    extra = supplied.keys() - declared
    if missing:
        raise ActionError(f"missing action arguments: {', '.join(sorted(missing))}")
    if extra:
        raise ActionError(f"undeclared action arguments: {', '.join(sorted(extra))}")
    values = {"project": project, **supplied}
    argv: list[str] = []
    for token in command["run"]:
        match = _PLACEHOLDER.fullmatch(token)
        if match:
            key = match.group(1)
            if key not in values:
                raise ActionError(f"unbound argv placeholder: {key}")
            argv.append(values[key])
        elif "{" in token or "}" in token:
            raise ActionError(f"placeholders must occupy a complete argv token: {token}")
        else:
            argv.append(token)
    return ActionSpec(
        name=name,
        argv=tuple(argv),
        risk=Risk(command["risk"]),
        idempotent=bool(command.get("idempotent", False)),
        approval=ApprovalMode(command.get("approval", "policy")),
        verification=_verification(command.get("verify")),
        side_effects=tuple(command.get("sideEffects", [])),
        preconditions=tuple(command.get("preconditions", [])),
        rollback=command.get("rollback"),
        arguments=supplied,
    )


def authorize_action(
    project: str, action: ActionSpec, principal: Principal, decision: Decision | None
) -> None:
    if principal.scope and project not in principal.scope and "*" not in principal.scope:
        raise ActionError(f"principal {principal.id} is outside project scope: {project}")
    if action.approval is ApprovalMode.NEVER:
        return
    if decision is None:
        raise ActionError(f"action requires {action.approval.value} approval: {action.name}")
    if decision.outcome not in (DecisionOutcome.ALLOW, DecisionOutcome.ALLOW_ONCE):
        raise ActionError(f"action decision is {decision.outcome.value}: {action.name}")


def _run(argv: tuple[str, ...], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, shell=False)


def execute_action(
    *,
    manifest: Mapping[str, Any],
    root: Path,
    name: str,
    principal: Principal,
    arguments: Mapping[str, str] | None = None,
    decision: Decision | None = None,
    runner: Runner = _run,
) -> ExecutionResult:
    action = resolve_action(manifest, name, arguments)
    authorize_action(str(manifest["slug"]), action, principal, decision)
    completed = runner(action.argv, root)
    return ExecutionResult(action, completed.returncode, completed.stdout, completed.stderr)
