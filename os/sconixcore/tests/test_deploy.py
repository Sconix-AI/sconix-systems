from pathlib import Path

import pytest

from sconixcore import DeployRecordError, Principal, PrincipalKind, load_record
from sconixcore.deploy import (
    approve_plan,
    complete_plan,
    create_plan,
    verify_plan,
)


def git(project: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@sconix.dev")
    git(root, "config", "user.name", "Sconix Test")
    (root / "README.md").write_text("demo")
    git(root, "add", "README.md")
    git(root, "commit", "-qm", "initial")
    monkeypatch.setenv("SCONIX_STATE_DIR", str(tmp_path / "state"))
    return root


def operator() -> Principal:
    return Principal(PrincipalKind.HUMAN, "yusuf", role="operator")


def test_plan_requires_separate_approval_and_is_consumed_once(project: Path) -> None:
    plan = create_plan(
        project="demo",
        project_root=project,
        host="deploy@example",
        domain="demo.example",
        principal=operator(),
    )
    with pytest.raises(DeployRecordError, match="approval"):
        verify_plan(plan["id"], project, "deploy@example", "demo.example")
    approve_plan(plan["id"], operator(), "ship it")
    assert verify_plan(plan["id"], project, "deploy@example", "demo.example")["id"] == plan["id"]
    with pytest.raises(DeployRecordError, match="consumed"):
        verify_plan(plan["id"], project, "deploy@example", "demo.example")
    complete_plan(plan["id"], status="verified", evidence="healthz ok")


def test_plan_records_are_readable_from_public_api(project: Path) -> None:
    plan = create_plan(
        project="demo",
        project_root=project,
        host="deploy@example",
        domain="demo.example",
        principal=operator(),
    )
    assert load_record("plans", plan["id"])["id"] == plan["id"]


def test_plan_rejects_changed_git_head(project: Path) -> None:
    plan = create_plan(
        project="demo",
        project_root=project,
        host="deploy@example",
        domain="demo.example",
        principal=operator(),
    )
    approve_plan(plan["id"], operator(), "ship it")
    (project / "README.md").write_text("changed")
    git(project, "add", "README.md")
    git(project, "commit", "-qm", "change")
    with pytest.raises(DeployRecordError, match="gitSha"):
        verify_plan(plan["id"], project, "deploy@example", "demo.example")


def test_rollback_plan_is_bound_to_release(project: Path) -> None:
    plan = create_plan(
        project="demo",
        project_root=project,
        host="deploy@example",
        domain="demo.example",
        principal=operator(),
        action="rollback",
        release="abc123-plan",
    )
    approve_plan(plan["id"], operator(), "restore known release")
    assert plan["action"]["argv"][3] == "abc123-plan"
    with pytest.raises(DeployRecordError, match="release"):
        verify_plan(
            plan["id"],
            project,
            "deploy@example",
            "demo.example",
            action="rollback",
            release="different-release",
        )


def test_canary_plan_is_bound_to_canary_domain(project: Path) -> None:
    plan = create_plan(
        project="demo",
        project_root=project,
        host="deploy@example",
        domain="canary.demo.example",
        principal=operator(),
        action="canary",
    )
    approve_plan(plan["id"], operator(), "run isolated canary")
    assert plan["action"]["argv"][:3] == ["sx", "canary", "demo"]
    with pytest.raises(DeployRecordError, match="domain"):
        verify_plan(
            plan["id"],
            project,
            "deploy@example",
            "other.demo.example",
            action="canary",
        )
