from __future__ import annotations

import re
import subprocess
import time
from asyncio import create_subprocess_exec
from collections.abc import Awaitable, Callable, Mapping
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
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def argv(self) -> tuple[str, ...]:
        return self.action.argv

    @property
    def output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()[-8000:]


Runner = Callable[[tuple[str, ...], Path], subprocess.CompletedProcess[str]]
DecisionProvider = Callable[
    [str, str, ActionSpec, Principal], Decision | Awaitable[Decision]
]


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


def lookup_action(manifest: Mapping[str, Any], name: str) -> ActionSpec | None:
    command = manifest.get("commands", {}).get(name)
    if command is None:
        return None
    return ActionSpec(
        name=name,
        argv=tuple(command["run"]),
        risk=Risk(command["risk"]),
        idempotent=bool(command.get("idempotent", False)),
        approval=ApprovalMode(command.get("approval", "policy")),
        verification=_verification(command.get("verify")),
        side_effects=tuple(command.get("sideEffects", [])),
        preconditions=tuple(command.get("preconditions", [])),
        rollback=command.get("rollback"),
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
    scope: str | None = None,
    runner: Runner = _run,
) -> ExecutionResult:
    action = resolve_action(manifest, name, arguments)
    authorize_action(scope or str(manifest["slug"]), action, principal, decision)
    started = time.monotonic()
    completed = runner(action.argv, root)
    duration_ms = int((time.monotonic() - started) * 1000)
    return ExecutionResult(
        action, completed.returncode, completed.stdout, completed.stderr, duration_ms
    )


class ManifestExecutor:
    """Manifest-backed async adapter for coding and operational agents.

    Authority can be supplied per call or through constructor defaults. Mutating
    actions fail closed when no principal or allow decision is available.
    """

    def __init__(
        self,
        project_dir: str | Path,
        *,
        principal: Principal | None = None,
        decision_provider: DecisionProvider | None = None,
        runner: Runner = _run,
    ) -> None:
        self.projects_dir = Path(project_dir).resolve()
        self.principal = principal
        self.decision_provider = decision_provider
        self.runner = runner
        self._projects: dict[str, tuple[Path, dict[str, Any]]] = {}

    def _project(self, target: str) -> tuple[Path, dict[str, Any]]:
        from sconixcore.manifest import ManifestError, inspect_project

        if target in self._projects:
            return self._projects[target]
        candidates = (self.projects_dir / target, self.projects_dir)
        for candidate in candidates:
            try:
                inspection = inspect_project(candidate, strict=True)
            except ManifestError:
                continue
            if inspection.manifest["slug"] == target:
                value = (inspection.root, inspection.manifest)
                self._projects[target] = value
                return value
        raise KeyError(f"no manifest for target {target!r}")

    def lookup(self, target: str, name: str | None = None) -> ActionSpec | None:
        if name is None:
            root, manifest = self._project(self.projects_dir.name)
            return lookup_action(manifest, target)
        _, manifest = self._project(target)
        return lookup_action(manifest, name)

    async def execute(
        self,
        target: str,
        name: str | None = None,
        *,
        principal: Principal | None = None,
        decision: Decision | None = None,
        arguments: Mapping[str, str] | None = None,
        **legacy_arguments: str,
    ) -> ExecutionResult:
        if name is None:
            legacy_target = legacy_arguments.pop("target", None)
            if legacy_target is None:
                raise ActionError("target required for manifest execution")
            name, target = target, legacy_target
        root, manifest = self._project(target)
        spec = lookup_action(manifest, name)
        if spec is None:
            raise KeyError(f"undeclared action {name!r}")
        actor = principal or self.principal
        if actor is None:
            raise ActionError(f"principal required for action: {name}")
        bound = dict(arguments or {})
        bound.update(legacy_arguments)
        if "target" in manifest["commands"][name].get("arguments", []):
            bound = {"target": target, **bound}
        if decision is None and self.decision_provider is not None:
            value = self.decision_provider(name, target, spec, actor)
            decision = await value if isinstance(value, Awaitable) else value
        action = resolve_action(manifest, name, bound)
        authorize_action(target, action, actor, decision)
        if self.runner is not _run:
            started = time.monotonic()
            completed = self.runner(action.argv, root)
            return ExecutionResult(
                action,
                completed.returncode,
                completed.stdout,
                completed.stderr,
                int((time.monotonic() - started) * 1000),
            )
        started = time.monotonic()
        process = await create_subprocess_exec(
            *action.argv,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return ExecutionResult(
            action,
            process.returncode,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
            int((time.monotonic() - started) * 1000),
        )
