import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sconixcore import (
    ActionError,
    Decision,
    DecisionOutcome,
    ManifestExecutor,
    Principal,
    PrincipalKind,
    execute_action,
    resolve_action,
)


def manifest(run: list[str] | None = None) -> dict:
    return {
        "schema": "sconix.dev/project/v1",
        "kind": "application",
        "name": "Demo",
        "slug": "demo",
        "lifecycle": {"status": "live"},
        "commands": {
            "restart": {
                "run": run or ["sx", "restart", "{project}", "{target}"],
                "arguments": ["target"],
                "risk": "external-write",
                "approval": "policy",
                "idempotent": True,
                "verify": {"checks": ["healthz"], "attempts": 3},
            }
        },
    }


def principal(scope: tuple[str, ...] = ("demo",)) -> Principal:
    return Principal(PrincipalKind.AGENT, "pilot", role="ops", scope=scope)


def allow() -> Decision:
    return Decision(
        DecisionOutcome.ALLOW,
        Principal(PrincipalKind.HUMAN, "yusuf"),
        datetime.now(UTC).isoformat(),
    )


def test_resolve_action_binds_only_declared_complete_tokens() -> None:
    action = resolve_action(manifest(), "restart", {"target": "api"})
    assert action.argv == ("sx", "restart", "demo", "api")
    with pytest.raises(ActionError, match="missing action arguments"):
        resolve_action(manifest(), "restart")
    with pytest.raises(ActionError, match="undeclared action arguments"):
        resolve_action(manifest(), "restart", {"target": "api", "extra": "no"})
    with pytest.raises(ActionError, match="complete argv token"):
        resolve_action(
            manifest(["sx", "restart", "--target={target}"]),
            "restart",
            {"target": "api"},
        )


def test_execution_is_shell_free_and_preserves_untrusted_value(tmp_path: Path) -> None:
    seen: list[tuple[str, ...]] = []

    def runner(argv: tuple[str, ...], cwd: Path) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    value = "api; touch /tmp/should-not-run"
    result = execute_action(
        manifest=manifest(),
        root=tmp_path,
        name="restart",
        principal=principal(),
        arguments={"target": value},
        decision=allow(),
        runner=runner,
    )
    assert result.ok
    assert seen == [("sx", "restart", "demo", value)]


def test_scope_and_decision_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ActionError, match="outside project scope"):
        execute_action(
            manifest=manifest(),
            root=tmp_path,
            name="restart",
            principal=principal(("other",)),
            arguments={"target": "api"},
            decision=allow(),
        )
    with pytest.raises(ActionError, match="requires policy approval"):
        execute_action(
            manifest=manifest(),
            root=tmp_path,
            name="restart",
            principal=principal(),
            arguments={"target": "api"},
        )


def test_undeclared_action_is_denied() -> None:
    with pytest.raises(ActionError, match="undeclared action"):
        resolve_action(manifest(), "delete_everything")


def write_agent_manifest(root: Path) -> None:
    root.joinpath("sconix.yaml").write_text(
        "schema: sconix.dev/project/v1\n"
        "kind: application\nname: Drill\nslug: drill\n"
        "lifecycle: {status: active}\n"
        "commands:\n"
        "  restart:\n"
        "    run: [sx, restart, '{project}']\n"
        "    risk: external-write\n"
        "    approval: policy\n"
        "    idempotent: true\n"
        "    verify: {checks: [healthz], attempts: 3, intervalSeconds: 2}\n"
    )


def test_manifest_executor_matches_agent_seam_with_explicit_authority(
    tmp_path: Path,
) -> None:
    project = tmp_path / "drill"
    project.mkdir()
    write_agent_manifest(project)
    seen: list[tuple[str, ...]] = []

    def runner(argv: tuple[str, ...], cwd: Path) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "restarted drill", "warning")

    async def decide(name, target, spec, actor):
        assert (name, target, spec.risk.value, actor.id) == (
            "restart",
            "drill",
            "external-write",
            "pilot",
        )
        return allow()

    executor = ManifestExecutor(
        tmp_path,
        principal=principal(("drill",)),
        decision_provider=decide,
        runner=runner,
    )
    assert executor.lookup("drill", "restart") is not None
    assert executor.lookup("drill", "delete_env") is None
    result = asyncio.run(executor.execute("drill", "restart"))
    assert result.ok and result.argv == ("sx", "restart", "drill")
    assert "restarted drill" in result.output and "warning" in result.output
    assert result.duration_ms >= 0
    assert seen == [("sx", "restart", "drill")]


def test_manifest_executor_fails_closed_without_authority(tmp_path: Path) -> None:
    project = tmp_path / "drill"
    project.mkdir()
    write_agent_manifest(project)
    executor = ManifestExecutor(tmp_path)
    with pytest.raises(ActionError, match="principal required"):
        asyncio.run(executor.execute("drill", "restart"))
    with pytest.raises(KeyError, match="undeclared action"):
        asyncio.run(executor.execute("drill", "delete_env", principal=principal()))
