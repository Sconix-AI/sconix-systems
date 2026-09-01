from pathlib import Path

import pytest
import yaml

from sconixcore import ManifestError, inspect_project


def write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False))


def test_application_legacy_manifest_is_normalized(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "app.yaml",
        {
            "name": "Demo",
            "slug": "demo",
            "pitch": "A demo",
            "status": "building",
            "created": "2026-08-31",
            "domain": "demo.example.com",
        },
    )
    result = inspect_project(tmp_path, strict=True)
    assert result.legacy is True
    assert result.manifest["kind"] == "application"
    assert result.manifest["lifecycle"]["status"] == "active"
    assert result.manifest["endpoints"]["production"] == "https://demo.example.com"


def test_research_manifest_is_found_from_child(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "project.yaml",
        {
            "name": "Study",
            "slug": "study",
            "question": "Does it work?",
            "status": "done",
            "created": "2026-08-31",
            "tags": [],
        },
    )
    child = tmp_path / "experiments" / "one"
    child.mkdir(parents=True)
    result = inspect_project(child, strict=True)
    assert result.root == tmp_path
    assert result.manifest["kind"] == "research"
    assert result.manifest["lifecycle"]["status"] == "completed"


def test_native_manifest_takes_precedence(tmp_path: Path) -> None:
    write_yaml(tmp_path / "app.yaml", {"name": "Old", "slug": "old", "status": "scaffold"})
    write_yaml(
        tmp_path / "sconix.yaml",
        {
            "schema": "sconix.dev/project/v1",
            "kind": "application",
            "name": "New",
            "slug": "new",
            "lifecycle": {"status": "draft"},
        },
    )
    result = inspect_project(tmp_path, strict=True)
    assert result.legacy is False
    assert result.manifest["name"] == "New"


def test_strict_mode_rejects_invalid_manifest(tmp_path: Path) -> None:
    write_yaml(tmp_path / "app.yaml", {"name": "Broken", "slug": "Not Portable"})
    with pytest.raises(ManifestError, match="invalid manifest"):
        inspect_project(tmp_path, strict=True)
