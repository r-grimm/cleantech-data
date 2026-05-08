#!/usr/bin/env python3
"""Build catalog/charts_index.json from charts/**/chart.meta.json (Welle 3 U14a).

Mirrors scripts/build_indices.py but for chart bundles. The agent reads this
index via chart-engine MCP resources to answer "which charts have we built from
this dataset?" or "what did we publish recently?".

Output:
    catalog/charts_index.json    {
        "schema_version": "1.0",
        "generated_at": "...",
        "total_charts": N,
        "charts": [
            {chart_id, chart_type, title, bundle_path, source_dataset_paths,
             status, render_timestamp, used_in_count}
        ],
        "by_dataset": {csv_path: [chart_id, ...]},
        "recent": [chart_id, ...]   # last 20 by render_timestamp
    }

Usage:
    python scripts/build_charts_index.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHARTS_DIR = REPO_ROOT / "charts"
CATALOG_DIR = REPO_ROOT / "catalog"
RECENT_LIMIT = 20


def _load_chart_meta(meta_path: Path) -> dict | None:
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _bundle_path(meta_path: Path) -> str:
    """Return the bundle directory relative to the repo root (e.g. charts/2026-05/foo)."""
    return meta_path.parent.relative_to(REPO_ROOT).as_posix()


def main() -> int:
    charts: list[dict] = []
    by_dataset: dict[str, list[str]] = defaultdict(list)

    if CHARTS_DIR.exists():
        for meta_path in sorted(CHARTS_DIR.rglob("chart.meta.json")):
            meta = _load_chart_meta(meta_path)
            if not meta:
                continue
            chart_id = meta.get("id")
            if not chart_id:
                continue
            entry = {
                "chart_id": chart_id,
                "chart_type": meta.get("chart_type"),
                "title": meta.get("title"),
                "bundle_path": _bundle_path(meta_path),
                "source_dataset_paths": meta.get("source_dataset_paths") or [],
                "status": meta.get("status", "active"),
                "render_timestamp": meta.get("render_timestamp"),
                "used_in_count": len(meta.get("used_in") or []),
            }
            charts.append(entry)
            for csv_path in entry["source_dataset_paths"]:
                by_dataset[csv_path].append(chart_id)

    # Recent: status:active charts ordered by render_timestamp descending
    active_charts = [c for c in charts if c.get("status") == "active"]
    active_charts.sort(key=lambda c: c.get("render_timestamp") or "", reverse=True)
    recent = [c["chart_id"] for c in active_charts[:RECENT_LIMIT]]

    index = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_charts": len(charts),
        "charts": sorted(charts, key=lambda c: c["chart_id"]),
        "by_dataset": {k: sorted(v) for k, v in by_dataset.items()},
        "recent": recent,
    }
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    (CATALOG_DIR / "charts_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not charts:
        print("OK: charts/ directory empty — wrote stub charts_index.json.")
    else:
        print(f"OK: indexed {len(charts)} charts ({len(by_dataset)} dataset cross-refs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
