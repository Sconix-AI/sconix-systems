from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sconixcore import ApprovalMode, Principal, PrincipalKind, Risk, Verification


class DeployRecordError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _state_root() -> Path:
    configured = os.environ.get("SCONIX_STATE_DIR")
    return Path(configured) if configured else Path.home() / ".local/state/sconix"


def _write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise DeployRecordError(f"record already exists: {path}") from exc
    with os.fdopen(descriptor, "w") as stream:
        stream.write(payload)


def _git_sha(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_plan(
    *,
    project: str,
    project_root: Path,
    host: str,
    domain: str,
    principal: Principal,
    action: str = "deploy",
    release: str | None = None,
    source_plan: str | None = None,
) -> dict[str, Any]:
    sha = _git_sha(project_root)
    argv = ["sx", "deploy", project, "--approve", "<plan-id>"]
    if action == "rollback":
        argv = ["sx", "rollback", project, release or "<release>", "--approve", "<plan-id>"]
    elif action == "canary":
        argv = ["sx", "canary", project, "--approve", "<plan-id>"]
    elif action == "promote":
        argv = [
            "sx", "promote", project, source_plan or "<canary-plan-id>", "--approve", "<plan-id>"
        ]
    elif action == "teardown":
        argv = [
            "sx", "teardown", project, source_plan or "<canary-plan-id>", "--approve", "<plan-id>"
        ]
    body = {
        "schema": "sconix.dev/deploy/plan/v1",
        "project": project,
        "gitSha": sha,
        "host": host,
        "domain": domain,
        "principal": principal.as_dict(),
        "action": {
            "name": action,
            "argv": argv,
            "risk": Risk.EXTERNAL_WRITE.value,
            "approval": ApprovalMode.ALWAYS.value,
            "verification": Verification(
                checks=("healthz", "readyz"),
                within_seconds=60,
                attempts=6,
                interval_seconds=5,
            ).as_dict(),
        },
        "createdAt": _now(),
    }
    if release:
        body["release"] = release
    if source_plan:
        body["sourcePlan"] = source_plan
    digest_payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    plan_id = hashlib.sha256(digest_payload).hexdigest()[:20]
    body["id"] = plan_id
    _write_once(_state_root() / "deploy/plans" / f"{plan_id}.json", body)
    return body


def load_record(kind: str, record_id: str) -> dict[str, Any]:
    path = _state_root() / "deploy" / kind / f"{record_id}.json"
    if not path.is_file():
        raise DeployRecordError(f"no {kind[:-1]} record: {record_id}")
    return json.loads(path.read_text())


def approve_plan(plan_id: str, principal: Principal, reason: str) -> dict[str, Any]:
    load_record("plans", plan_id)
    approval = {
        "schema": "sconix.dev/deploy/approval/v1",
        "planId": plan_id,
        "outcome": "allow-once",
        "principal": principal.as_dict(),
        "reason": reason,
        "approvedAt": _now(),
    }
    _write_once(_state_root() / "deploy/approvals" / f"{plan_id}.json", approval)
    return approval


def verify_plan(
    plan_id: str,
    project_root: Path,
    host: str,
    domain: str,
    *,
    action: str = "deploy",
    release: str | None = None,
    source_plan: str | None = None,
) -> dict[str, Any]:
    plan = load_record("plans", plan_id)
    approval = load_record("approvals", plan_id)
    expected = {
        "gitSha": _git_sha(project_root),
        "host": host,
        "domain": domain,
        "action": action,
        "release": release,
        "sourcePlan": source_plan,
    }
    actual = {**plan, "action": plan["action"]["name"]}
    mismatches = [key for key, value in expected.items() if actual.get(key) != value]
    if mismatches:
        raise DeployRecordError(f"stale or mismatched plan fields: {', '.join(mismatches)}")
    if approval.get("outcome") != "allow-once":
        raise DeployRecordError("plan is not approved for one execution")
    execution = _state_root() / "deploy/executions" / f"{plan_id}.json"
    if execution.exists():
        raise DeployRecordError("approved plan has already been consumed")
    _write_once(
        execution,
        {
            "schema": "sconix.dev/deploy/execution/v1",
            "planId": plan_id,
            "status": "executing",
            "startedAt": _now(),
        },
    )
    return plan


def complete_plan(plan_id: str, *, status: str, evidence: str = "") -> dict[str, Any]:
    load_record("plans", plan_id)
    record = {
        "schema": "sconix.dev/deploy/completion/v1",
        "planId": plan_id,
        "status": status,
        "evidence": evidence,
        "completedAt": _now(),
    }
    _write_once(_state_root() / "deploy/completions" / f"{plan_id}.json", record)
    return record


def _principal(value: str, *, role: str, intent: str) -> Principal:
    return Principal(PrincipalKind.HUMAN, value, role=role, intent=intent)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sconix-deploy")
    commands = parser.add_subparsers(dest="command", required=True)
    actions = ("deploy", "rollback", "canary", "promote", "teardown")
    plan = commands.add_parser("plan")
    plan.add_argument("project")
    plan.add_argument("--root", required=True, type=Path)
    plan.add_argument("--host", required=True)
    plan.add_argument("--domain", required=True)
    plan.add_argument("--by", required=True)
    plan.add_argument(
        "--action", choices=actions, default="deploy"
    )
    plan.add_argument("--release")
    plan.add_argument("--source-plan")
    approve = commands.add_parser("approve")
    approve.add_argument("plan_id")
    approve.add_argument("--by", required=True)
    approve.add_argument("--reason", default="operator approved deployment")
    verify = commands.add_parser("verify")
    verify.add_argument("plan_id")
    verify.add_argument("--root", required=True, type=Path)
    verify.add_argument("--host", required=True)
    verify.add_argument("--domain", required=True)
    verify.add_argument(
        "--action", choices=actions, default="deploy"
    )
    verify.add_argument("--release")
    verify.add_argument("--source-plan")
    complete = commands.add_parser("complete")
    complete.add_argument("plan_id")
    complete.add_argument("--status", choices=("verified", "failed"), required=True)
    complete.add_argument("--evidence", default="")
    show = commands.add_parser("show")
    show.add_argument("kind", choices=("plans", "approvals", "executions", "completions"))
    show.add_argument("record_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            value = create_plan(
                project=args.project,
                project_root=args.root,
                host=args.host,
                domain=args.domain,
                principal=_principal(args.by, role="operator", intent="plan deployment"),
                action=args.action,
                release=args.release,
                source_plan=args.source_plan,
            )
        elif args.command == "approve":
            value = approve_plan(
                args.plan_id,
                _principal(args.by, role="approver", intent="approve deployment"),
                args.reason,
            )
        elif args.command == "verify":
            value = verify_plan(
                args.plan_id,
                args.root,
                args.host,
                args.domain,
                action=args.action,
                release=args.release,
                source_plan=args.source_plan,
            )
        elif args.command == "complete":
            value = complete_plan(args.plan_id, status=args.status, evidence=args.evidence)
        else:
            value = load_record(args.kind, args.record_id)
    except (DeployRecordError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps({"ok": True, **value}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
