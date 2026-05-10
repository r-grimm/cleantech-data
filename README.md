# cleantech-data

`cleantech-data` ist eine kuratierte Sammlung von Clean-Tech- und Energiewende-Datensaetzen. Das Repository speichert CSV-Dateien zusammen mit maschinenlesbaren Metadaten, damit Datenquellen, Zeitraum, Lizenz, Qualitaet und Aktualitaet nachvollziehbar bleiben.

Die Daten eignen sich fuer Recherche, Visualisierungen, Analysen und wiederholbare Auswertungen. Jede Datei soll auch spaeter noch erklaeren, woher die Werte stammen und wie sie verwendet werden duerfen.

## Inhalt

- CSV-Datensaetze zu Energie, Industrie, Investitionen, Speicher, Solar, Wind und angrenzenden Clean-Tech-Themen
- JSON-Sidecars mit Titel, Beschreibung, Quelle, Lizenz, Zeitraum, Tags, Provenienz und Freshness-Informationen
- Vorberechnete Kataloge und Indizes fuer Suche nach Tags, Quellen, Themen und Zeitraeumen
- Persistierte Chart-Bundles mit PNG/SVG, Render-Konfiguration und Chart-Metadaten
- Pruefskripte fuer Metadaten, CSV-Inhalte und Kataloge

## Schnellstart

Voraussetzung: Python 3.11 oder neuer.

```bash
python -m pip install -r requirements.txt
python scripts/validate_metadata.py
python scripts/validate_data.py
```

Optional, wenn du lokale Git-Hooks nutzen willst:

```bash
python -m pip install pre-commit
pre-commit install
```

## Daten finden

Die Rohdaten liegen unter `data/`. Die Ordner sind nach dem Monat strukturiert, in dem ein Datensatz aufgenommen wurde:

```text
data/
  YYYY-MM/
    [thema/]
      beispiel.csv
      beispiel.meta.json
```

Zum Einstieg sind diese Dateien hilfreich:

- `data/catalog.json`: vollstaendiger Katalog aller bekannten CSV-Dateien
- `catalog/active_index.json`: aktuell nutzbare Datensaetze mit `status: active`
- `catalog/by_tag.json`: Datensaetze nach Tags
- `catalog/by_source.json`: Datensaetze nach Quellenname
- `catalog/by_period.json`: Datensaetze nach Datenzeitraum
- `catalog/by_topic.json`: Datensaetze nach thematischem Unterordner

Ein typischer Zugriff ist:

1. Im Katalog oder in einem Index einen passenden Datensatz finden.
2. Die zugehoerige `.meta.json` lesen.
3. Lizenz, Quelle, Zeitraum und Status pruefen.
4. Die CSV-Datei fuer Analyse oder Visualisierung laden.

## Metadaten

Zu jeder CSV-Datei gehoert nach Moeglichkeit ein Sidecar mit gleichem Namen und der Endung `.meta.json`.

Beispiel:

```text
data/2025-12/photovoltaik-zubau-deutschland-2020-2024.csv
data/2025-12/photovoltaik-zubau-deutschland-2020-2024.meta.json
```

Wichtige Felder:

- `title`: lesbarer Titel des Datensatzes
- `description`: Beschreibung des Inhalts
- `source`: Quellenname, Quellen-URL und Importtyp
- `license`: Lizenz oder Nutzungsbedingung
- `tags`: kleingeschriebene kebab-case Tags, zum Beispiel `solar-energy`
- `created_at`: Zeitpunkt der Aufnahme
- `status`: `active`, `needs_review`, `superseded` oder `deprecated`
- `data_period`: Zeitraum, den die Daten abdecken
- `provenance`: Hinweise zur Extraktion und Verarbeitung
- `freshness`: letzter Quellencheck und Aktualitaetsinformationen

Die verbindliche Struktur steht in `schemas/dataset_meta.schema.json`.

## Statuswerte

- `active`: Datensatz ist geprueft und kann normal verwendet werden.
- `needs_review`: Datensatz ist vorhanden, braucht aber noch manuelle Pruefung.
- `superseded`: Datensatz wurde durch eine neuere Datei ersetzt.
- `deprecated`: Datensatz bleibt aus Nachvollziehbarkeitsgruenden erhalten, sollte aber nicht mehr neu verwendet werden.

Pruefe vor jeder Wiederverwendung immer den Status und die Lizenz im Sidecar.

## Neuen Datensatz hinzufuegen

1. Lege die CSV-Datei unter `data/YYYY-MM/` ab. Nutze optional einen thematischen Unterordner.
2. Erzeuge oder aktualisiere das Sidecar:

   ```bash
   python scripts/migrate_sidecars_v2.py
   ```

3. Bearbeite die `.meta.json` manuell: Beschreibung, Quelle, Lizenz, Tags, Zeitraum, Provenienz und Freshness muessen stimmen.
4. Validieren:

   ```bash
   python scripts/validate_metadata.py
   python scripts/validate_data.py
   ```

5. Kataloge lokal aktualisieren, wenn du die generierten Dateien mitpruefen willst:

   ```bash
   python scripts/build_indices.py
   python scripts/rebuild_catalog.py
   ```

## Datenqualitaet

Die lokalen Checks decken zwei Ebenen ab:

- `scripts/validate_metadata.py` prueft alle `.meta.json` Dateien gegen das JSON-Schema.
- `scripts/validate_data.py` sucht nach offensichtlichen CSV-Problemen wie leeren Daten, Platzhalter-Sequenzen, identischen Zahlenkolonnen oder bitgleichen Duplikaten.

GitHub Actions fuehren die Metadatenvalidierung aus und aktualisieren Katalogdateien, wenn sich Daten oder Sidecars aendern.

## Charts

Gerenderte Charts koennen unter `charts/` abgelegt werden:

```text
charts/
  YYYY-MM/
    slug/
      slug.png
      slug.svg
      render-config.json
      chart.meta.json
```

`chart.meta.json` dokumentiert unter anderem Chart-Typ, Titel, verwendete Datensaetze, Render-Zeitpunkt, Status und Nutzungskontext. Die Struktur ist in `schemas/chart_meta.schema.json` beschrieben.

## Lizenz

Der Code in diesem Repository steht unter MIT-Lizenz. Fuer Datensaetze gilt jeweils die im Sidecar angegebene Lizenz oder Quellenbedingung. Pruefe vor Weiterverwendung immer `source`, `source.url` und `license`.
