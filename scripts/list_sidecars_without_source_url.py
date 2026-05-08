#!/usr/bin/env python3
"""List sidecars whose `source.url` is missing or empty.

Welle 5 backfill helper. Walks `data/**/*.meta.json`, categorises every
sidecar by status + import_type, and prints a tabular listing of those
without a source URL. Read-only — no rewrites.

Use the `--status` filter to focus on the active+csv|api gaps that the new
conditional JSON-Schema rule starts rejecting (see
`chart_engine/cli/export_json_schema.py:_CONDITIONAL_RULES`).

Usage:
    python scripts/list_sidecars_without_source_url.py
    python scripts/list_sidecars_without_source_url.py --status active
    python scripts/list_sidecars_without_source_url.py --status needs_review
    python scripts/list_sidecars_without_source_url.py --status all
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

STATUS_FILTERS = ("active", "needs_review", "superseded", "deprecated", "all")


@dataclass(frozen=True)
class SidecarRow:
    path: Path
    status: str
    import_type: str
    created_at: str
    source_name: str
    hint: str

    @property
    def relpath(self) -> str:
        try:
            return str(self.path.relative_to(REPO_ROOT))
        except ValueError:
            return str(self.path)


def _has_source_url(payload: dict) -> bool:
    source = payload.get("source") or {}
    url = source.get("url")
    return isinstance(url, str) and url.strip() != ""


def _hint_for(payload: dict) -> str:
    """Best-effort hint to help the operator backfill — Telegram forward header,
    extraction notes, anything that looks like a source breadcrumb."""
    provenance = payload.get("provenance") or {}
    original = provenance.get("original_source") or {}
    if isinstance(original, dict):
        original_url = original.get("url")
        if isinstance(original_url, str) and original_url.strip():
            return f"provenance.original_source.url={original_url}"
        original_name = original.get("name")
        if isinstance(original_name, str) and original_name.strip():
            return f"provenance.original_source.name={original_name}"
    quality = payload.get("quality") or {}
    if isinstance(quality, dict):
        review_notes = quality.get("review_notes")
        if isinstance(review_notes, str) and review_notes.strip():
            return f"quality.review_notes={review_notes}"
    return "—"


def collect_rows(data_dir: Path) -> list[SidecarRow]:
    rows: list[SidecarRow] = []
    for path in sorted(data_dir.rglob("*.meta.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rows.append(
                SidecarRow(
                    path=path,
                    status="<invalid>",
                    import_type="<invalid>",
                    created_at="<invalid>",
                    source_name="<invalid>",
                    hint=f"json error: {exc}",
                )
            )
            continue
        if _has_source_url(payload):
            continue
        source = payload.get("source") or {}
        rows.append(
            SidecarRow(
                path=path,
                status=str(payload.get("status") or "unknown"),
                import_type=str(source.get("import_type") or "unknown"),
                created_at=str(payload.get("created_at") or "—"),
                source_name=str(source.get("name") or "—"),
                hint=_hint_for(payload),
            )
        )
    return rows


def filter_rows(rows: list[SidecarRow], status: str) -> list[SidecarRow]:
    if status == "all":
        return rows
    return [row for row in rows if row.status == status]


_STATUS_ORDER = {
    "active": 0,
    "needs_review": 1,
    "superseded": 2,
    "deprecated": 3,
}


def render(rows: list[SidecarRow]) -> str:
    if not rows:
        return "No sidecars without source.url found.\n"
    rows = sorted(rows, key=lambda r: (_STATUS_ORDER.get(r.status, 99), r.relpath))
    headers = ("path", "status", "import_type", "created_at", "source.name", "hint")
    cells = [
        (row.relpath, row.status, row.import_type, row.created_at, row.source_name, row.hint)
        for row in rows
    ]
    widths = [max(len(headers[i]), max(len(c[i]) for c in cells)) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*("-" * w for w in widths))]
    lines.extend(fmt.format(*row) for row in cells)
    summary = f"\nTotal: {len(rows)} sidecar(s) without source.url\n"
    return "\n".join(lines) + summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List sidecars whose source.url is missing.")
    parser.add_argument(
        "--status",
        default="all",
        choices=STATUS_FILTERS,
        help="Filter by lifecycle status (default: all)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Data directory to scan (default: {DATA_DIR.relative_to(REPO_ROOT)}/)",
    )
    args = parser.parse_args(argv)

    if not args.data_dir.exists():
        sys.stderr.write(f"data directory not found: {args.data_dir}\n")
        return 1

    rows = collect_rows(args.data_dir)
    filtered = filter_rows(rows, args.status)
    sys.stdout.write(render(filtered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
