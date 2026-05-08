# Source Patterns Memory

Durable memory for the cleantech-data ingestion pipeline. chart-engine MCP
`remember_source_pattern` appends to this file; agents read it before scraping a new
source to avoid relearning landing-page layouts, file-naming conventions, and refresh
cadences.

Format per entry:

```
## <Source Name>

- **Domain:** example.com
- **Topic:** germany-solar-capacity
- **Access strategy:** direct_csv | direct_excel | landing_page_downloads | html_table | ocr_image | api
- **Reliability:** high | medium | low
- **Refresh cadence:** daily | weekly | monthly | quarterly | annual | irregular
- **Canonical URL:** https://example.com/data
- **Notes:**
  - Anything that helps the next ingest run.
```

Keep entries concise. Secrets are auto-redacted by the chart-engine writer; never paste
tokens or session cookies here.

---

<!-- New entries appended below this marker by remember_source_pattern. -->
