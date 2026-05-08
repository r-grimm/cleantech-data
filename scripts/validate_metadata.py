#!/usr/bin/env python3
"""Validate sidecar `.meta.json` files against the canonical JSON-Schema.

Welle 1 U1. The canonical schema (`schemas/dataset_meta.schema.json`) is exported
from chart-engine's Pydantic model via `chart-engine-export-schema`. This script
is the local + CI gate that confirms every sidecar matches.

Usage:
    python scripts/validate_metadata.py                         # all sidecars
    python scripts/validate_metadata.py data/2026-05/foo.meta.json   # one file
    python scripts/validate_metadata.py --check                 # exit non-zero on error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "dataset_meta.schema.json"
DATA_DIR = REPO_ROOT / "data"


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SCHEMA_PATH}. Generate it via:\n"
            f"  python -m chart_engine.cli.export_json_schema "
            f"--output {SCHEMA_PATH.relative_to(REPO_ROOT)}"
        )
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_file(path: Path, schema: dict) -> list[str]:
    """Return list of error messages, empty list if valid."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.relative_to(REPO_ROOT)}: invalid JSON: {exc}"]

    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        # Build a user-friendly path indicator from the JSON-pointer
        location = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        return [f"{path.relative_to(REPO_ROOT)}: {location}: {exc.message}"]
    return []


def collect_targets(args_paths: list[str]) -> list[Path]:
    if not args_paths:
        return sorted(DATA_DIR.rglob("*.meta.json"))
    targets: list[Path] = []
    for raw in args_paths:
        path = Path(raw)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.is_dir():
            targets.extend(sorted(path.rglob("*.meta.json")))
        else:
            targets.append(path)
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate sidecar metadata.")
    parser.add_argument(
        "paths", nargs="*", help="Specific .meta.json files or dirs (default: data/)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero on any error (CI mode). Default already exits non-zero.",
    )
    args = parser.parse_args(argv)

    try:
        schema = load_schema()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    targets = collect_targets(args.paths)
    if not targets:
        print("WARN: no sidecars to validate.")
        return 0

    errors: list[str] = []
    for path in targets:
        errors.extend(validate_file(path, schema))

    if errors:
        print(f"FAILED: {len(errors)} sidecar(s) violate schema:", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"OK: {len(targets)} sidecars valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
