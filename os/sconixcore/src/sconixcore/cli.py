from __future__ import annotations

import argparse
import json
from pathlib import Path

from sconixcore.manifest import ManifestError, inspect_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sconix-inspect")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = inspect_project(Path(args.path), strict=args.strict)
    except ManifestError as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"error: {exc}")
        return 2
    if args.as_json:
        print(json.dumps({"ok": not result.warnings, **result.as_dict()}, indent=2))
    else:
        manifest = result.manifest
        print(f"{manifest['name']} ({manifest['kind']})")
        print(f"  root:      {result.root}")
        print(f"  manifest:  {result.source.name}{' (legacy)' if result.legacy else ''}")
        print(f"  lifecycle: {manifest['lifecycle']['status']}")
        if result.warnings:
            print("  warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")
    return 1 if result.warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
