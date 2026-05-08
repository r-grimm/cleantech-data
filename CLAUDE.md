# CLAUDE.md — cleantech-data

This repo is the **agent-first dataset backend** for the cleantech.ing newsroom. The
canonical consumer is `chart-engine` (an MCP server in the `r-grimm/newsroom`
monorepo); a human almost never reads the files directly.

## Purpose

- Persist every dataset that has ever fed a chart, with sidecar metadata and provenance.
- Serve `chart-engine` MCP tools (`search_datasets`, `list_datasets`, `get_dataset_info`,
  `ingest_url_to_dataset`) over the GitHub API.
- Stay validated against `schemas/dataset_meta.schema.json` so the agent can rely on a
  stable contract — no defensive parsing.

## Layout

```
data/
  YYYY-MM/
    [thematic_name/]
      <slug>.csv
      <slug>.meta.json    # Schema-D sidecar
catalog/
  datasets.yaml           # legacy, slated for cleanup in Welle 4
  source_patterns.md      # durable memory for ingest pipelines (chart-engine remember_source_pattern)
schemas/
  dataset_meta.schema.json   # exported from chart-engine's Pydantic via chart-engine-export-schema
scripts/
  validate_metadata.py    # local + CI gate
  migrate_sidecars_v2.py  # idempotent Schema-D migration
  rebuild_catalog.py      # legacy, replaced by chart-engine CatalogGenerator in Welle 4
.github/workflows/
  validate-metadata.yml   # required check on every push
  update-catalog.yml      # rebuilds data/catalog.json
```

## Schema (Schema-D, Welle 1)

Every sidecar is a JSON file matching `schemas/dataset_meta.schema.json`. Required:

- `title`, `description`, `tags` (kebab-case lowercase), `source` (with valid `import_type`),
  `created_at` (ISO-8601), `status` (default `active`).

Conditional rule: `status: active` requires `description.minLength: 50`. Quarantine sidecars
(`status: needs_review`) lift this so OCR-extracted drafts can land before review.

Lifecycle fields:

- `status`: `active` | `needs_review` | `superseded` | `deprecated`
- `data_period`: `{start, end, granularity}` — granularity in `daily | weekly | monthly | quarterly | annual | single_value | irregular`
- `superseded_by`, `derived_from`: csv_path strings
- `replaces`: list of csv_paths (reverse direction)
- `keywords`: optional search aliases (e.g. DE/EN synonyms)

Provenance + freshness blocks are required:

- `provenance.extraction_method`, `extracted_by`, `extraction_date`, `transformations_applied`
- `freshness.source_checked`

## Adding a dataset

The agent path uses `chart-engine` MCP `ingest_url_to_dataset`, which writes both the CSV
and a Schema-D-conformant sidecar. The Telegram-Bot (`services/news_pipeline` in newsroom)
writes OCR sidecars with `status: needs_review` by default.

Manual path:

1. Place CSV at `data/YYYY-MM/<slug>.csv`.
2. Run `python scripts/migrate_sidecars_v2.py` — it creates a Schema-D sidecar with
   `status: needs_review` and a default description. Edit the sidecar to set the real
   description, source URL, etc.
3. Re-run `python scripts/validate_metadata.py` to confirm.
4. Commit. The pre-commit hook + CI will reject schema violations.

## Tag policy

All tags MUST match `^[a-z0-9]+(-[a-z0-9]+)*$` — kebab-case lowercase, no spaces, no
underscores, no special characters. The schema enforces this. To reuse logic across the
agent stack, see `chart_engine.services.tag_normalizer.normalize_tag` in newsroom.

## Searches and filters

`chart-engine` MCP tools default to `status: active`. To include quarantined or superseded
records pass `include_status` explicitly.

## Versioning chain

When a dataset is replaced:

1. Old sidecar: set `status: superseded` and `superseded_by: <new csv_path>`.
2. New sidecar: set `replaces: [<old csv_paths>]` (reverse pointer).

When a dataset is derived (transformation of another):

1. New sidecar: `derived_from: <source csv_path>` and
   `provenance.transformations_applied: [<pipeline_name>, ...]`.

The migration script (`scripts/migrate_sidecars_v2.py`) does not create chains
automatically — they encode editorial decisions. Set them manually after analyzing
overlapping datasets.

## Source patterns memory

`catalog/source_patterns.md` is durable, agent-readable memory for ingestion patterns
(landing pages, file-naming conventions, refresh cadence). chart-engine MCP
`remember_source_pattern` appends to it; agents read it before scraping a new source to
avoid relearning. Keep entries concise.

## What this repo does NOT do

- No Datasette / browse UI. The agent is the read interface.
- No SQL database. The repo IS the source of truth — git history serves as audit trail.
- No deploy. Consumer (`chart-engine`) and producer (`telegram-bot`) deploy separately.
