#!/usr/bin/env python3
"""Detect obviously-fake or duplicate CSVs (Welle 4 U15).

Heuristics:
- All-zero or all-null CSVs (empty data file)
- Sequential placeholders like 100/200/300/...
- All-identical numeric values (single repeated number)
- Bit-identical content to another tracked CSV (sha256 dedup)

Pre-commit + CI gate. Exits non-zero on any heuristic match.

Usage:
    python scripts/validate_data.py                   # all CSVs in data/
    python scripts/validate_data.py data/foo.csv ...  # specific files
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _numeric_columns(rows: list[list[str]]) -> list[list[float]]:
    """Pull the numeric columns from a CSV (excluding the header row)."""
    if len(rows) < 2:
        return []
    body = rows[1:]
    columns: list[list[float]] = []
    for col_idx in range(len(rows[0])):
        try:
            values = [
                float(row[col_idx].strip())
                for row in body
                if col_idx < len(row) and row[col_idx].strip()
            ]
        except ValueError:
            continue
        if values:
            columns.append(values)
    return columns


def _looks_like_sequential_placeholder(values: list[float]) -> bool:
    """Detect 100, 200, 300, ... fake-data patterns.

    NOT a placeholder:
    - year columns (values in 1900-2100 with step 1)
    - step-1 sequences in general — they show up legitimately in indexed data
    Only flag round-step (10/100/1000) sequences whose first value is a round
    multiple of the step. This is the pattern that previously polluted the repo
    (commit c6f0c2f removed test data with values 100,200,300).
    """
    if len(values) < 3:
        return False
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    if not diffs or diffs[0] == 0:
        return False
    if not all(abs(d - diffs[0]) < 1e-9 for d in diffs):
        return False
    step = abs(diffs[0])
    # Step 1 includes year ranges, indexes, line counts — too noisy to flag.
    if step < 10.0:
        return False
    return step in (10.0, 100.0, 1000.0) and abs(values[0] % step) < 1e-9


def validate_csv(path: Path) -> list[str]:
    """Return error messages for the CSV, empty list if clean."""
    errors: list[str] = []
    try:
        with path.open(encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
    except Exception as exc:
        return [f"{path.relative_to(REPO_ROOT)}: failed to parse: {exc}"]

    if not rows or len(rows) < 2:
        errors.append(f"{path.relative_to(REPO_ROOT)}: empty data (no rows beyond header)")
        return errors

    columns = _numeric_columns(rows)
    for col in columns:
        if all(v == 0 for v in col):
            errors.append(f"{path.relative_to(REPO_ROOT)}: numeric column is all zero — looks fake")
            break
        if len(set(col)) == 1 and len(col) > 2:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: numeric column is all identical "
                f"({col[0]}) — looks fake"
            )
            break
        if _looks_like_sequential_placeholder(col):
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: numeric column matches a placeholder "
                f"sequence ({col[:3]}...) — looks fake"
            )
            break

    return errors


def collect_targets(args_paths: list[str]) -> list[Path]:
    if not args_paths:
        return sorted(DATA_DIR.rglob("*.csv"))
    targets: list[Path] = []
    for raw in args_paths:
        path = Path(raw)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.is_dir():
            targets.extend(sorted(path.rglob("*.csv")))
        elif path.suffix == ".csv":
            targets.append(path)
    return targets


def find_duplicates(targets: list[Path]) -> list[str]:
    """Detect bit-identical CSVs across the dataset."""
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for path in targets:
        try:
            by_hash[_sha256(path)].append(path)
        except Exception:
            continue
    errors: list[str] = []
    for digest, paths in by_hash.items():
        if len(paths) > 1:
            relpaths = [str(p.relative_to(REPO_ROOT)) for p in paths]
            errors.append(f"duplicate content (sha256 {digest[:12]}): {', '.join(relpaths)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate dataset CSV bodies.")
    parser.add_argument("paths", nargs="*", help="CSV files (default: data/**/*.csv)")
    args = parser.parse_args(argv)

    targets = collect_targets(args.paths)
    if not targets:
        print("WARN: no CSVs to validate.")
        return 0

    errors: list[str] = []
    for path in targets:
        errors.extend(validate_csv(path))
    errors.extend(find_duplicates(targets))

    if errors:
        print(f"FAILED: {len(errors)} CSV issue(s):", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"OK: {len(targets)} CSVs clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
