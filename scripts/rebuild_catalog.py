#!/usr/bin/env python3
"""Rebuild catalog.json from metadata sidecars.

Self-contained script using only Python stdlib (no external dependencies).
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _to_posix_path(path: Path) -> str:
    """Convert Path to POSIX-style string (forward slashes)."""
    return path.as_posix()


def _extract_path_components(csv_path: str) -> tuple[str | None, str | None, str]:
    """Extract thematic_name, year_month, and filename from path.

    Example: data/2026-01/charts/foo.csv
    Returns: ("charts", "2026-01", "foo.csv")
    """
    parts = csv_path.split("/")
    filename = parts[-1]

    # Extract year_month (YYYY-MM pattern)
    year_month = None
    for part in parts:
        if re.match(r"^\d{4}-\d{2}$", part):
            year_month = part
            break

    # thematic_name is parent folder of the file (if not year_month folder)
    thematic_name = None
    if len(parts) >= 2:
        parent = parts[-2]
        if not re.match(r"^\d{4}-\d{2}$", parent) and parent != "data":
            thematic_name = parent

    return thematic_name, year_month, filename


def rebuild_catalog(data_dir: Path = Path("data")) -> dict:
    """Scan all .meta.json files and build catalog."""
    datasets = []

    for meta_file in data_dir.rglob("*.meta.json"):
        # foo.meta.json → foo.csv (remove .meta.json suffix)
        csv_file = meta_file.with_name(meta_file.name.replace(".meta.json", ".csv"))
        if not csv_file.exists():
            continue

        try:
            with open(meta_file) as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Skipping {meta_file}: {e}", file=sys.stderr)
            continue

        # Use POSIX paths (forward slashes) for cross-platform consistency
        csv_path = _to_posix_path(csv_file)
        meta_path = _to_posix_path(meta_file)
        thematic_name, year_month, filename = _extract_path_components(csv_path)

        # Ensure source has import_type for schema compatibility (copy to avoid mutation)
        raw_source = meta.get("source", {"name": "Unknown", "url": None})
        source = dict(raw_source) if isinstance(raw_source, dict) else {"name": "Unknown", "url": None}
        if "import_type" not in source:
            source["import_type"] = "csv"

        # Build catalog entry (compatible with chart-engine CatalogGenerator schema)
        entry = {
            "csv_path": csv_path,
            "metadata_path": meta_path,
            "title": meta.get("title", csv_file.stem.replace("-", " ").replace("_", " ").title()),
            "description": meta.get("description", ""),
            "source": source,
            "tags": meta.get("tags", []),
            "license": meta.get("license", "Unknown"),
            "created_at": meta.get("created_at"),
            "thematic_name": thematic_name,
            "year_month": year_month,
            "filename": filename,
            "has_metadata": True,
            # Freshness fields (null when not in sidecar - computed at query time)
            "freshness_score": None,
            "freshness_status": None,
            "freshness_indicator": None,
            "data_as_of": None,
            "source_reliability": None,
            "days_since_check": None,
            "warning": None,
        }
        datasets.append(entry)

    # Also add CSVs without metadata (fallback entries)
    for csv_file in data_dir.rglob("*.csv"):
        # Check for metadata sidecar (foo.csv → foo.meta.json pattern)
        meta_file = csv_file.with_name(csv_file.name.replace(".csv", ".meta.json"))
        if meta_file.exists():
            continue  # Already processed above

        csv_path = _to_posix_path(csv_file)
        thematic_name, year_month, filename = _extract_path_components(csv_path)
        title = csv_file.stem.replace("-", " ").replace("_", " ").title()

        entry = {
            "csv_path": csv_path,
            "metadata_path": None,
            "title": title,
            "description": f"Dataset: {title}",
            "source": {"name": "Unknown", "url": None, "import_type": "csv"},
            "tags": [thematic_name] if thematic_name else [],
            "license": "Unknown",
            "created_at": None,
            "thematic_name": thematic_name,
            "year_month": year_month,
            "filename": filename,
            "has_metadata": False,
            "freshness_score": None,
            "freshness_status": None,
            "freshness_indicator": None,
            "data_as_of": None,
            "source_reliability": None,
            "days_since_check": None,
            "warning": None,
        }
        datasets.append(entry)

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_datasets": len(datasets),
        "datasets": sorted(datasets, key=lambda x: x["csv_path"]),
    }


if __name__ == "__main__":
    try:
        catalog = rebuild_catalog()
        output_path = Path("data/catalog.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        print(f"Catalog rebuilt: {catalog['total_datasets']} datasets")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
