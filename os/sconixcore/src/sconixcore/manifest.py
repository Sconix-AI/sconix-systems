from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_ID = "sconix.dev/project/v1"
MANIFEST_NAMES = ("sconix.yaml", "app.yaml", "project.yaml")
SYSTEM_STATUS = {"scaffold": "draft", "building": "active"}
RESEARCH_STATUS = {"done": "completed"}


class ManifestError(ValueError):
    """A project manifest cannot be discovered, converted, or validated."""


@dataclass(frozen=True)
class Inspection:
    root: Path
    source: Path
    legacy: bool
    manifest: dict[str, Any]
    inferred: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "source": str(self.source),
            "legacy": self.legacy,
            "manifest": self.manifest,
            "inferred": list(self.inferred),
            "warnings": list(self.warnings),
        }


def _schema_text() -> str:
    packaged = files("sconixcore").joinpath("schemas/sconix.project.v1.schema.json")
    try:
        return packaged.read_text()
    except FileNotFoundError:
        path = Path(__file__).resolve().parents[4] / "schemas" / "sconix.project.v1.schema.json"
        return path.read_text()


def _find_root(start: Path) -> tuple[Path, Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        for name in MANIFEST_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return directory, candidate
    raise ManifestError(f"no Sconix manifest found from {start}")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ManifestError(f"manifest must be a mapping: {path}")
    return _json_value(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _production_endpoint(domain: Any) -> str | None:
    if not isinstance(domain, str) or not domain.strip():
        return None
    value = domain.strip()
    parsed = urlparse(value)
    return value if parsed.scheme else f"https://{value}"


def _legacy_manifest(source: Path, raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    kind = "application" if source.name == "app.yaml" else "research"
    status = str(raw.get("status", "draft"))
    status = (SYSTEM_STATUS if kind == "application" else RESEARCH_STATUS).get(status, status)
    manifest: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "kind": kind,
        "name": raw.get("name"),
        "slug": raw.get("slug"),
        "lifecycle": {"status": status},
    }
    inferred = ["schema", "kind", "lifecycle.status"]
    if raw.get("created") is not None:
        manifest["created"] = str(raw["created"])
    summary = raw.get("pitch")
    if summary:
        manifest["summary"] = summary
    if raw.get("question"):
        manifest["question"] = raw["question"]
    if raw.get("tags") is not None:
        manifest["tags"] = raw["tags"]
    endpoint = _production_endpoint(raw.get("domain"))
    if endpoint:
        manifest["endpoints"] = {"production": endpoint}
        inferred.append("endpoints.production")
    return manifest, inferred


def _validate(manifest: dict[str, Any]) -> list[str]:
    schema = json.loads(_schema_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
    ]


def inspect_project(start: str | Path = ".", *, strict: bool = False) -> Inspection:
    root, source = _find_root(Path(start))
    raw = _load_yaml(source)
    legacy = source.name != "sconix.yaml"
    if legacy:
        manifest, inferred = _legacy_manifest(source, raw)
    else:
        manifest, inferred = raw, []
    warnings = _validate(manifest)
    if strict and warnings:
        raise ManifestError("invalid manifest: " + "; ".join(warnings))
    return Inspection(root, source, legacy, manifest, tuple(inferred), tuple(warnings))
