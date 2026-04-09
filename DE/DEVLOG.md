# Entwicklungsprotokoll — DE Sozialwesen Visualisierung

Dieses Dokument protokolliert die Entstehungsgeschichte des DE-Projekts
als Claude-Code-Session-Log (2026-04-09).

---

## Ausgangspunkt

Bestehendes Projekt `karpathy/jobs` (geforkt als `profmanagement/employment_visualizer`):
Canvas-basierte Treemap des US-amerikanischen Arbeitsmarkts auf Basis der BLS
Occupational Outlook Handbook-Daten mit LLM-generiertem KI-Expositionsscore.

Ziel: Analoge Visualisierung für den deutschen Arbeitsmarkt, beginnend mit
sozialen Dienstleistungsberufen, auf Basis der BA-Beschäftigungsstatistik.

---

## Session-Verlauf

### 1 — Planungsdokument lesen und Fragen klären

Gelesen: `sozialwesen_plan.md` (im Stammverzeichnis) sowie ein bereits
existierender detaillierterer Plan unter `DE/sozialwesen_plan.md`.

**Offene Fragen, die per Chat geklärt wurden:**

| Frage | Entscheidung |
|---|---|
| Scraper-Strategie | Playwright (kein manueller Download) |
| KI-Exposition | BLS-Scores via Berufs-Mapping übernehmen |
| Visualisierungsinhalt | Beschäftigungszahlen + KI-Exposition |

---

### 2 — Implementierung: 4 Kerndateien

#### `DE/scrape_ba.py`
Playwright-Scraper (async). Navigiert `statistik.arbeitsagentur.de`,
akzeptiert Cookie-Banner (mehrere Selektoren als Fallback), harvested
alle `.xlsx`-Links via `eval_on_selector_all`, filtert auf die Kategorien
`sozbe-kldb-blk`, `sozbe-kldb-kreis`, `sozbe-wz-blk`, `sozbe-wz-kreis`
und lädt die Dateien nach `DE/data/raw/{kategorie}/`.

Direkter Fallback-Hinweis für manuellen Download dokumentiert.

#### `DE/parse_ba.py`
Liest BA-Excel-Tabellen (pandas + openpyxl). Probiert automatisch
verschiedene `header=`-Werte (4–7), da BA-Dateien je nach Jahrgang
unterschiedlich viele Metadaten-Kopfzeilen haben. Normalisiert Spaltennamen
via Kandidatenlisten (Fuzzy-Suche). Filtert auf KldB- und WZ-Präfixe.
Ersetzt BA-Datenschutz-Suppression (`*`) durch `NaN`.

**Fix nach erstem Testlauf:** `pandas` und `openpyxl` fehlten in
`pyproject.toml` → ergänzt und `uv sync` ausgeführt.

#### `DE/build_site_data.py`
Berechnet aus den CSVs:
- Frauenanteil, Teilzeitquote, Geringfügigenanteil
- Gesamtwachstum (%) und CAGR p.a.
- Zeitreihen pro Berufsgruppe (für Sparklines)

Mappt KldB-/WZ-Codes auf BLS-Slugs und zieht Expositionsscores aus
`../scores.json`. Schreibt `DE/site/data.json` mit `nodes`- und
`timeseries`-Arrays.

**Fix nach erstem Testlauf:** Leere DataFrames (keine CSVs vorhanden)
führten zu `KeyError: 'code'` in `build_nodes`, `growth_pct` und `cagr` →
Guard-Checks `if df.empty or "code" not in df.columns` ergänzt.

#### `DE/site/index.html`
Canvas-basierte Squarified-Treemap, analog zur BLS-Seite, vollständig
in Vanilla-JS ohne Frameworks. Angepasst für DE-Metriken:

| Farbmodus | Bedeutung |
|---|---|
| Wachstum 2013–heute | Prozentuale SVB-Veränderung (grün = wachsend) |
| Frauenanteil | Anteil weiblicher SVB |
| Teilzeitquote | Anteil Teilzeitbeschäftigter |
| KI-Exposition | 0–10-Score aus BLS-Mapping |

Tooltip mit Sparkline (SVG-Linienkurve per Canvas), Stat-Grid.
Demo-Modus mit synthetischen Zeitreihen (aus CAGR rückgerechnet),
wenn noch keine echten BA-Daten vorliegen.

---

### 3 — Erweiterung: Bildung und Gesundheit

Auf Nutzerwunsch wurden weitere KldB-Berufshauptgruppen und WZ-Abteilungen
einbezogen:

**KldB-Erweiterung:**

| Code | Bereich |
|---|---|
| 82 | Lehrende und Ausbildende (Schulen, Hochschulen) |
| 84 | Therapie und Heilpraktik (Physio, Ergo, Logo) |
| 85 | Human- und Zahnmedizin, Tiermedizin |
| 86 | Psychologie, nichtärztliche Psychotherapie |
| 87 | Pharmazie |
| 88 | Medizintechnik, Orthoptik, Audiologie |

**WZ-Erweiterung:**

| Code | Bereich |
|---|---|
| 85 | Erziehung und Unterricht |
| 86 | Gesundheitswesen (Krankenhäuser, Praxen) |

Alle neuen Codes erhielten BLS-Mappings (Scores aus `scores.json`),
deutsche Rationale-Texte und Demo-Daten.

Neue UI-Elemente:
- Sektor-Filter-Leiste: Alle / Soziales / Bildung / Pflege / Therapie / Medizin
- `sectorFilter`-Variable + `SECTOR_PREFIXES`-Map in JS

---

### 4 — Zeitreihen-Visualisierung

**Sparkline im Tooltip:**
- Canvas-basiert, zeichnet SVB-Verlauf pro Berufsgruppe
- Füllfläche + Linie + Endpunkt-Dot in Kachel-Farbe
- Jahresbeschriftung, Delta-Anzeige (`+123T`)
- Fallback-Text wenn keine Zeitreihendaten vorhanden

**Trend-Panel unterhalb der Treemap:**
- Erscheint nur im Modus „Wachstum 2013–heute"
- Mehrlinien-Chart mit bis zu 8 Serien gleichzeitig
- Gemeinsame Y-Achse, Rasterlinien, Jahresbeschriftung, Farbpalette
- Labels am Ende jeder Linie
- `drawTrendPanel(seriesList)` nutzt `dpr`-skaliertes Canvas

**Top-Wachstum-Rangliste** in block5 (Wachstum-Modus).

Demo-Zeitreihen werden aus CAGR + SVB-Endstand synthetisch generiert
(`makeDemoTimeseries`), inklusive leichtem Rauschen für natürlichere Kurven.

---

### 5 — Schlüsselentwicklungen Sozialwesen

5 Karten unterhalb der Treemap mit Kennzahl, Erklärtext und SVG-Minidiagramm:

| # | Kennzahl | Diagramm |
|---|---|---|
| 1 | +35 % Wachstum 2013–2023 | Linienkurve mit Füllfläche |
| 2 | ~80 % Frauenanteil | Vergleichsbalken vs. Gesamtwirtschaft |
| 3 | ~50 % Teilzeitquote | Segmentbalken TZ/VZ |
| 4 | >150.000 offene Stellen | Balkendiagramm nach Berufsfeld |
| 5 | −15 % Entgeltlücke | Index-Vergleich mit Abwärtspfeil |

---

### 6 — About & Methodik

Statischer Abschnitt unterhalb der Schlüsselentwicklungen:

**Methodik** (4 Schritte mit Code-Referenzen):
1. `scrape_ba.py` — Playwright-Download, Cookie-Wall-Problematik
2. `parse_ba.py` — Excel-Parsing, Header-Variabilität, Normalisierung
3. `build_site_data.py` — Kennzahlberechnung, BLS-Score-Mapping
4. `index.html` — Canvas-Treemap, Sparklines, Demo-Modus

Codetabellen KldB 81–88 und WZ 85–88, Caveat-Box zu KI-Scores.

**About:**
> Erstellt von **Maik Arnold** (profmanagement).
> Geforkt von karpathy/jobs von **Andrej Karpathy**.
> Adaptiert mit BA-Daten und Claude Code.
> Credits & Dank: Andrej Karpathy für originales Projekt, Treemap-Layout
> und LLM-Scoring-Konzept.

---

### 7 — GitHub Pages

```bash
# Branch gh-pages mit DE/site/ als Wurzel anlegen:
git subtree push --prefix DE/site origin gh-pages

# Auf GitHub: Settings → Pages → Branch: gh-pages / root
# URL: https://profmanagement.github.io/employment_visualizer/
```

Für spätere Updates:
```bash
git add DE/site/data.json DE/site/index.html
git commit -m "DE: Aktualisierte BA-Daten"
git push origin master
git subtree push --prefix DE/site origin gh-pages
```

---

## Commits dieser Session

| Hash | Beschreibung |
|---|---|
| `29c382b` | DE: Treemap-Visualisierung Soziales/Bildung/Gesundheit mit Zeitreihen |
| `5c48828` | DE: Schlüsselentwicklungen Sozialwesen als Info-Abschnitt |
| `942e2e7` | DE: About-Sektion und Methodik-Dokumentation auf index.html |

---

## Bekannte Offene Punkte

- **Scraper verifizieren:** `scrape_ba.py` wurde noch nicht gegen das
  Live-Portal getestet (BA kann URL-Struktur ändern). Fallback: manueller
  Download in `DE/data/raw/{kategorie}/`.
- **parse_ba.py anpassen:** `HEADER_ROW` und Spaltennamen nach erstem
  echten Download gegen tatsächliche Dateistruktur prüfen.
- **Kreisdaten:** Verfügbarkeit für kleine Berufsgruppen unklar
  (Datenschutz-Suppression möglich).
- **KI-Scores DE-spezifisch:** Aktuell BLS-Mapping; alternative DE-Quelle
  (z. B. IAB-Studien zu Automatisierungsrisiken) wäre präziser.
