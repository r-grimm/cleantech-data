#!/usr/bin/env python3
"""Pre-compute discovery indices from sidecars.

Welle 2 U9. Agent-side filters (`by_tag`, `by_source`, `by_period`, `by_topic`,
`active_index`) get expensive once the catalog grows past ~100 entries. These
indices give the chart-engine MCP server O(1) lookups instead of linear scans.

Outputs:
    catalog/by_tag.json       {tag: [csv_path, ...]}
    catalog/by_source.json    {source_name: [csv_path, ...]}
    catalog/by_period.json    {year: [csv_path, ...]}
    catalog/by_topic.json     {thematic_name: [csv_path, ...]}
    catalog/active_index.json [csv_path, ...]   # status == active only

Usage:
    python scripts/build_indices.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CATALOG_DIR = REPO_ROOT / "catalog"


def _csv_path_from_sidecar(sidecar_path: Path) -> str:
    """Derive the repo-relative csv path from a sidecar path."""
    csv_path = sidecar_path.with_name(sidecar_path.name.replace(".meta.json", ".csv"))
    return csv_path.relative_to(REPO_ROOT).as_posix()


def _extract_year_buckets(period: dict | None) -> list[str]:
    """A sidecar's data_period covers one or more years; return all buckets it spans."""
    if not isinstance(period, dict):
        return []
    start = (period.get("start") or "").strip()
    end = (period.get("end") or "").strip()
    years: list[str] = []
    for value in (start, end):
        if not value:
            continue
        if len(value) >= 4 and value[:4].isdigit():
            years.append(value[:4])
    if not years:
        return []
    if len(years) == 1:
        return years
    try:
        lo, hi = sorted({int(years[0]), int(years[-1])})
        return [str(y) for y in range(lo, hi + 1)]
    except ValueError:
        return list(set(years))


def _thematic_name(csv_path: str) -> str | None:
    """Reconstruct chart-engine's thematic-name extraction (parent folder of csv)."""
    parts = csv_path.split("/")
    if len(parts) < 4:
        return None
    parent = parts[-2]
    if parent.startswith("20") and len(parent) == 7:  # YYYY-MM bucket
        return None
    return parent


def main() -> int:
    by_tag: dict[str, list[str]] = defaultdict(list)
    by_source: dict[str, list[str]] = defaultdict(list)
    by_period: dict[str, list[str]] = defaultdict(list)
    by_topic: dict[str, list[str]] = defaultdict(list)
    active_index: list[str] = []

    for sidecar in sorted(DATA_DIR.rglob("*.meta.json")):
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        csv_path = _csv_path_from_sidecar(sidecar)

        for tag in payload.get("tags", []) or []:
            if tag:
                by_tag[tag].append(csv_path)

        source = payload.get("source") or {}
        source_name = source.get("name")
        if source_name:
            by_source[source_name].append(csv_path)

        for year in _extract_year_buckets(payload.get("data_period")):
            by_period[year].append(csv_path)

        topic = _thematic_name(csv_path)
        if topic:
            by_topic[topic].append(csv_path)

        if payload.get("status") == "active":
            active_index.append(csv_path)

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)

    def _write(name: str, data: object) -> None:
        path = CATALOG_DIR / name
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"  wrote {path.relative_to(REPO_ROOT)} ({len(data)} entries)")

    _write("by_tag.json", {k: sorted(v) for k, v in by_tag.items()})
    _write("by_source.json", {k: sorted(v) for k, v in by_source.items()})
    _write("by_period.json", {k: sorted(v) for k, v in by_period.items()})
    _write("by_topic.json", {k: sorted(v) for k, v in by_topic.items()})
    _write("active_index.json", sorted(active_index))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
