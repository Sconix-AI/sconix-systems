"""Sconix project contracts and inspection."""

from sconixcore.contracts import (
    ActionSpec,
    ApprovalMode,
    Decision,
    DecisionOutcome,
    Principal,
    PrincipalKind,
    Risk,
    Verification,
)
from sconixcore.executor import ActionError, ExecutionResult, execute_action, resolve_action
from sconixcore.manifest import Inspection, ManifestError, inspect_project

__all__ = [
    "ActionSpec",
    "ActionError",
    "ApprovalMode",
    "Decision",
    "DecisionOutcome",
    "Inspection",
    "ExecutionResult",
    "ManifestError",
    "Principal",
    "PrincipalKind",
    "Risk",
    "Verification",
    "execute_action",
    "inspect_project",
    "resolve_action",
]
__version__ = "0.1.0"
