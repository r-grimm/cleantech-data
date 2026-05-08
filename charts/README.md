# charts/ — Persisted chart bundles (Welle 3)

Each persisted chart lives in its own folder so the bundle is self-contained and
re-renderable in years to come:

```
charts/
  YYYY-MM/
    <slug>/
      <slug>.png            # publication-ready raster
      <slug>.svg            # editable vector source (optional)
      render-config.json    # exact render-time config (chart-engine input)
      chart.meta.json       # Welle-3 sidecar — see schemas/chart_meta.schema.json
```

The agent path uses `chart-engine` MCP `create_chart_from_intent` with persistence
enabled. The render pipeline writes all four files atomically and stamps the
`chart.meta.json` with the dataset references and render-config hash.

## Lookup paths

- By slug: `charts/<YYYY-MM>/<slug>/chart.meta.json`
- By dataset: filter by `source_dataset_paths` (chart-engine MCP resources expose this lookup)
- By usage context (newsletter / tagesbriefing / telegram): filter on `used_in[].context`

## Lifecycle

- `status: active` (default) — current chart, eligible for re-use
- `status: deprecated` — operator decided this chart should not be re-used; keep for
  reproducibility but exclude from search

When a chart is rendered with the same `render_config_hash` as an existing one, the
pipeline is idempotent: no new commit, no duplicated bundle.

## used_in trail

Each consumer (Newsletter Assistant, Tagesbriefing, Telegram bot) appends to
`used_in[]` when it embeds the chart in a published artifact. The agent uses the
trail for "have we shown this chart before?" lookups.
