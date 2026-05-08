# cleantech-data

Agent-first dataset backend for the [cleantech.ing](https://cleantech.ing) newsroom. The
canonical consumer is **chart-engine** (an MCP server in [r-grimm/newsroom](https://github.com/r-grimm/newsroom));
a human almost never reads the files directly.

For the agent contract, schema reference, and write workflow, read [CLAUDE.md](CLAUDE.md).

## Layout

```
data/
  YYYY-MM/
    [thematic_name/]
      <slug>.csv
      <slug>.meta.json    # Schema-D sidecar, validates against schemas/dataset_meta.schema.json
catalog/
  source_patterns.md      # durable memory for ingest pipelines
  by_tag.json, by_source.json, by_period.json, by_topic.json, active_index.json
                          # pre-computed discovery indices, refreshed by build-indices CI
  catalog.json            # auto-generated full index, refreshed by update-catalog CI
charts/                   # Welle-3 chart bundles (PNG + SVG + render-config + meta)
  YYYY-MM/<slug>/
schemas/
  dataset_meta.schema.json  # exported from chart-engine's Pydantic via chart-engine-export-schema
  chart_meta.schema.json    # bundle sidecar contract
scripts/
  validate_metadata.py    # local + CI gate for sidecars
  migrate_sidecars_v2.py  # idempotent Schema-D migration
  build_indices.py        # rebuilds catalog/by_*.json
  rebuild_catalog.py      # legacy stand-in for chart-engine's CatalogGenerator (slated for replacement in a follow-up)
.github/workflows/
  validate-metadata.yml   # required check on every push
  build-indices.yml       # rebuilds discovery indices on meta.json change
  update-catalog.yml      # rebuilds data/catalog.json
```

## Adding a dataset

The agent path uses chart-engine MCP `ingest_url_to_dataset`, which writes both the CSV
and a Schema-D-conformant sidecar. The Telegram-Bot writes OCR sidecars with
`status: needs_review` by default.

Manual path:

1. Place CSV at `data/YYYY-MM/<slug>.csv`.
2. Run `python scripts/migrate_sidecars_v2.py` — it creates a Schema-D sidecar with
   `status: needs_review` and a default description. Edit the sidecar to set the real
   description, source URL, etc.
3. Re-run `python scripts/validate_metadata.py` to confirm.
4. Commit. The pre-commit hook + CI rejects schema violations.

Local setup:

```bash
pip install -r requirements.txt
pre-commit install
```

## Schema (Schema-D)

Every sidecar matches `schemas/dataset_meta.schema.json` (exported from chart-engine's
Pydantic model). Required fields: `title`, `description`, `tags` (kebab-case),
`source` (with valid `import_type`), `created_at`, `status`.

Conditional rule: `status: active` requires `description.minLength: 50`. Quarantine
sidecars (`status: needs_review`) lift this.

Lifecycle: `status` (active | needs_review | superseded | deprecated), `data_period`
(start/end/granularity), `superseded_by`, `derived_from`, `replaces`, `keywords`.
Provenance and freshness blocks are required.

## Data sources

Major recurring sources include SMARD/Bundesnetzagentur, Energy-Charts.info (Fraunhofer
ISE), Fachagentur Wind und Solar, Battery-Charts.de, Volker Quaschning, IRENA, IEA,
Ember, Wikipedia, ICCT, BloombergNEF. See `catalog/by_source.json` for the live index.

## License

MIT for the code in this repo. Each dataset carries its own license in
`source.license`; consult the sidecar before reuse.
