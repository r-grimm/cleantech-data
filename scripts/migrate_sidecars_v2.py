#!/usr/bin/env python3
"""Migrate all sidecars to Schema-D (Welle 1 U2).

Idempotent — second run produces byte-identical output. Hardcoded migration_date
keeps re-runs deterministic.

Behavior:
- Adds status (default "active"; "needs_review" for OCR or empty descriptions)
- Adds data_period derived from CSV's year column (best-effort, "irregular" fallback)
- Adds provenance block from existing source.import_type / created_at
- Normalizes columns to dict format (list -> dict, ensures `name` field)
- Backfills created_at from migration_date if missing
- Adds default description template for empty descriptions on OCR sidecars
- Creates sidecars for CSVs without one (status: needs_review)

Usage:
    python scripts/migrate_sidecars_v2.py            # apply
    python scripts/migrate_sidecars_v2.py --dry-run  # preview
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
MIGRATION_DATE = "2026-05-08"
MIGRATION_TS = f"{MIGRATION_DATE}T00:00:00+00:00"
MIN_DESCRIPTION_LENGTH = 50


def _import_type_to_extraction_method(import_type: str) -> str:
    return {"csv": "api", "ocr": "ocr", "api": "api", "manual": "manual"}.get(import_type, "manual")


def _read_year_range(csv_path: Path) -> tuple[str | None, str | None, str]:
    """Best-effort derivation of (start, end, granularity) from a CSV.

    Returns ('irregular' granularity if anything is uncertain).
    """
    if not csv_path.exists():
        return (None, None, "irregular")
    try:
        import csv as csv_lib

        with csv_path.open(encoding="utf-8") as fh:
            reader = csv_lib.reader(fh)
            header = next(reader, None)
            if not header:
                return (None, None, "irregular")
            year_col_idx = None
            granularity = "irregular"
            for idx, name in enumerate(header):
                lowered = name.strip().lower()
                if lowered in {"year", "jahr"}:
                    year_col_idx = idx
                    granularity = "annual"
                    break
                if lowered in {"date", "datum"}:
                    year_col_idx = idx
                    granularity = "daily"  # tighten later if needed
                    break
                if lowered in {"month", "monat"}:
                    year_col_idx = idx
                    granularity = "monthly"
                    break
            if year_col_idx is None:
                return (None, None, "irregular")

            values: list[str] = []
            for row in reader:
                if len(row) > year_col_idx:
                    val = row[year_col_idx].strip()
                    if val:
                        values.append(val)
            if not values:
                return (None, None, granularity)
            return (values[0], values[-1], granularity)
    except Exception:
        return (None, None, "irregular")


def _normalize_columns(columns: Any) -> Any:
    if columns is None:
        return None
    if isinstance(columns, list):
        return {col: {"name": col} for col in columns}
    if isinstance(columns, dict):
        normalized: dict[str, dict] = {}
        for key, value in columns.items():
            if isinstance(value, dict):
                if "name" not in value:
                    value = {"name": key, **value}
                normalized[key] = value
            else:
                normalized[key] = {"name": key}
        return normalized
    return columns


def _default_description(title: str, source_name: str, is_ocr: bool) -> str:
    if is_ocr:
        return (
            f"OCR-extrahierter Chart aus {source_name or 'unbekannter Quelle'} "
            f"({title}); manuelle Pruefung des Datensatzes erforderlich."
        )
    return (
        f"Datensatz '{title}' (Quelle: {source_name or 'unbekannt'}); "
        f"Migration_v2 Default-Beschreibung — bitte manuell ueberarbeiten."
    )


def _migrate_payload(payload: dict, csv_path: Path, *, was_missing: bool) -> dict:
    """Lift a single sidecar payload to Schema-D. Returns new dict (no mutation)."""
    out: dict = {}

    title = payload.get("title") or csv_path.stem.replace("-", " ").replace("_", " ").title()
    out["title"] = title

    source = payload.get("source") or {}
    if isinstance(source, str):
        source = {"name": source, "import_type": "csv"}
    source_name = source.get("name") or ""
    import_type = source.get("import_type") or (
        "ocr" if was_missing is False and "/charts/" in csv_path.as_posix() else "csv"
    )

    is_ocr = import_type == "ocr"
    raw_description = (payload.get("description") or "").strip()
    description = raw_description
    needs_review = bool(payload.get("needs_review")) or is_ocr or not raw_description

    if not raw_description or len(raw_description) < MIN_DESCRIPTION_LENGTH:
        description = _default_description(title, source_name, is_ocr)

    out["description"] = description
    out["tags"] = payload.get("tags") or []

    out_source: dict = {
        "name": source_name or "Unknown",
        "url": source.get("url"),
        "import_type": import_type,
    }
    out["source"] = out_source

    out["license"] = payload.get("license") or "CC-BY-4.0"
    out["created_at"] = payload.get("created_at") or MIGRATION_TS

    columns = _normalize_columns(payload.get("columns"))
    if columns is not None:
        out["columns"] = columns

    # Status — default needs_review for OCR or short descriptions, else active
    explicit_status = payload.get("status")
    if explicit_status in {"active", "needs_review", "superseded", "deprecated"}:
        out["status"] = explicit_status
    elif needs_review:
        out["status"] = "needs_review"
    else:
        out["status"] = "active"

    # data_period
    if "data_period" in payload and isinstance(payload["data_period"], dict):
        out["data_period"] = payload["data_period"]
    else:
        start, end, granularity = _read_year_range(csv_path)
        out["data_period"] = {"start": start, "end": end, "granularity": granularity}

    # provenance — preserve existing, fill gaps from migration defaults
    provenance = dict(payload.get("provenance") or {})
    provenance.setdefault("extraction_method", _import_type_to_extraction_method(import_type))
    provenance.setdefault("extracted_by", "telegram-bot" if is_ocr else "migration_v2")
    provenance.setdefault("extraction_date", out["created_at"] or MIGRATION_TS)
    provenance.setdefault("transformations_applied", [])
    out["provenance"] = provenance

    # freshness — preserve, ensure source_checked
    freshness = dict(payload.get("freshness") or {})
    freshness.setdefault("source_checked", out["created_at"] or MIGRATION_TS)
    out["freshness"] = freshness

    # quality — preserve if present
    quality = payload.get("quality")
    if isinstance(quality, dict):
        out["quality"] = quality

    # Versioning fields — preserve existing values
    for key in ("superseded_by", "derived_from"):
        if key in payload:
            out[key] = payload[key]
    if "replaces" in payload:
        out["replaces"] = payload["replaces"]
    if "keywords" in payload:
        out["keywords"] = payload["keywords"]

    # Legacy-but-preserved fields used by older readers
    for legacy_key in ("csv_file", "units", "needs_review"):
        if legacy_key in payload:
            out[legacy_key] = payload[legacy_key]

    return out


def _meta_path_for(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.name.replace(".csv", ".meta.json"))


def _csv_path_for(meta_path: Path) -> Path:
    return meta_path.with_name(meta_path.name.replace(".meta.json", ".csv"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate sidecars to Schema-D.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args(argv)

    updates: list[tuple[Path, dict]] = []
    creations: list[tuple[Path, dict]] = []

    # Pass 1: update existing sidecars
    for meta_path in sorted(DATA_DIR.rglob("*.meta.json")):
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"SKIP corrupted {meta_path}: {exc}", file=sys.stderr)
            continue
        csv_path = _csv_path_for(meta_path)
        new_payload = _migrate_payload(payload, csv_path, was_missing=False)
        if new_payload != payload:
            updates.append((meta_path, new_payload))

    # Pass 2: create sidecars for CSVs without one
    seen_csvs = {_csv_path_for(p) for p in DATA_DIR.rglob("*.meta.json")}
    for csv_path in sorted(DATA_DIR.rglob("*.csv")):
        if csv_path in seen_csvs:
            continue
        if csv_path.name == "catalog.json":
            continue
        meta_path = _meta_path_for(csv_path)
        new_payload = _migrate_payload({}, csv_path, was_missing=True)
        creations.append((meta_path, new_payload))

    print(f"Updates: {len(updates)} | Creations: {len(creations)}")
    if args.dry_run:
        for path, _ in updates[:5]:
            print(f"  - update {path.relative_to(REPO_ROOT)}")
        for path, _ in creations:
            print(f"  + create {path.relative_to(REPO_ROOT)}")
        return 0

    for path, payload in updates + creations:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(f"Wrote {len(updates) + len(creations)} sidecars.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
