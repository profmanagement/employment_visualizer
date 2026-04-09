# DE – Beschäftigungsanalyse Soziale Dienstleistungen (BA-Daten)

Interaktive Treemap-Visualisierung der Beschäftigungsdaten der Bundesagentur für Arbeit (BA)
für soziale Dienstleistungsberufe und Sozialwirtschaft.

Analoges Gegenstück zur [US-Visualisierung](../site/index.html) (BLS-Daten).

---

## Inhalt

```
DE/
  README.md                  ← diese Datei
  sozialwesen_plan.md        ← ursprünglicher Planungsdokument
  scrape_ba.py               ← Schritt 1: Playwright-Download der BA-Excel-Dateien
  parse_ba.py                ← Schritt 2: Excel → bereinigte CSVs
  build_site_data.py         ← Schritt 3: CSVs + AI-Scores → site/data.json
  site/
    index.html               ← Schritt 4: Treemap-Visualisierung (Browser öffnen)
    data.json                ← generiert (nicht im Git)
  data/
    raw/                     ← Original-Downloads (nicht im Git)
      sozbe-kldb-blk/        ← SVB nach KldB 2010, Bund + Länder
      sozbe-kldb-kreis/      ← SVB nach KldB 2010, Kreise
      sozbe-wz-blk/          ← SVB nach WZ 2008, Bund + Länder
      sozbe-wz-kreis/        ← SVB nach WZ 2008, Kreise
    processed/               ← generiert (nicht im Git)
      kldb_blk.csv           ← BHG 81, 83 — Bund + Länder, alle Jahre
      kldb_kreis.csv         ← BHG 81, 83 — Kreise, alle Jahre
      wz_blk.csv             ← WZ 87, 88 — Bund + Länder, alle Jahre
      wz_kreis.csv           ← WZ 87, 88 — Kreise, alle Jahre
```

---

## Reihenfolge zum Ausführen

### Voraussetzungen

```bash
# Im Wurzelverzeichnis des Projekts:
uv sync                          # Python-Abhängigkeiten (pandas, httpx, playwright …)
playwright install chromium      # Browser für Schritt 1
```

### Schritt 1 – Raw-Daten herunterladen

```bash
uv run python DE/scrape_ba.py
```

Navigiert `statistik.arbeitsagentur.de` mit Playwright, akzeptiert den Cookie-Banner
und lädt alle `.xlsx`-Dateien für die vier Kategorien in `DE/data/raw/` herunter.

**Fallback (manueller Download):** Falls der Scraper keine Links findet
(die BA ändert gelegentlich ihre URL-Struktur), die Dateien manuell von
`statistik.arbeitsagentur.de > Statistiken > Beschäftigung > Tabellen > Excel`
herunterladen und in die entsprechenden `DE/data/raw/{kategorie}/`-Verzeichnisse legen:

| Verzeichnis | Inhalt |
|---|---|
| `sozbe-kldb-blk/` | Beschäftigte nach KldB 2010, Bund + Länder |
| `sozbe-kldb-kreis/` | Beschäftigte nach KldB 2010, Kreise |
| `sozbe-wz-blk/` | Beschäftigte nach WZ 2008, Bund + Länder |
| `sozbe-wz-kreis/` | Beschäftigte nach WZ 2008, Kreise |

### Schritt 2 – Excel parsen

```bash
uv run python DE/parse_ba.py
```

Liest alle `.xlsx`-Dateien aus `DE/data/raw/`, filtert auf die relevanten Codes
(KldB 81/83, WZ 87/88) und schreibt normalisierte CSVs nach `DE/data/processed/`.

**Häufiges Problem:** BA-Excel-Dateien variieren im Tabellenaufbau je nach Jahrgang.
Falls die Ausgabe „Keine passenden Zeilen gefunden" zeigt, in `parse_ba.py`
den Wert `HEADER_ROW` (Zeile 35) anpassen — typisch sind 4, 5, 6 oder 7.

### Schritt 3 – Visualisierungsdaten bauen

```bash
uv run python DE/build_site_data.py
```

Liest die CSVs aus `DE/data/processed/`, berechnet Kennzahlen (Wachstum, Anteile),
mappt die KI-Expositionsscores aus `../scores.json` auf die deutschen Berufsgruppen
und schreibt `DE/site/data.json`.

### Schritt 4 – Visualisierung öffnen

```bash
open DE/site/index.html      # macOS
# oder im Browser: DE/site/index.html
```

---

## Datenquellen

| Quelle | Inhalt |
|---|---|
| [Bundesagentur für Arbeit – Beschäftigungsstatistik](https://statistik.arbeitsagentur.de/) | SVB, GB, Teilzeit nach KldB und WZ; Stichtag 30. Juni; ab 2013 |
| [BLS Occupational Outlook Handbook](https://www.bls.gov/ooh/) | Basis für KI-Expositionsscores (via LLM-Scoring, adaptiert für DE) |

### Gefilterte Codes

**KldB 2010 – Berufshauptgruppen:**

| Code | Bezeichnung |
|---|---|
| 81 | Erziehung, soziale Arbeit, Heilerziehungspflege |
| 811 | Kinderbetreuung und -erziehung |
| 812 | Sozialarbeit, Sozialpädagogik |
| 813 | Heilerziehungspflege, Sonderpädagogik |
| 83 | Gesundheits- u. Krankenpflege, Rettungsdienst, Geburtshilfe |
| 831 | Gesundheits- und Krankenpflege |
| 832 | Rettungsdienst |
| 833 | Geburtshilfe (Hebammen) |

**WZ 2008 – Wirtschaftsabteilungen:**

| Code | Bezeichnung |
|---|---|
| 87 | Heime (ohne Erholungs- und Ferienheime) |
| 88 | Sozialwesen ohne Unterkunft |
| 88.1 | Soziale Betreuung älterer Menschen und Behinderter |
| 88.9 | Sonstiges Sozialwesen |

---

## Visualisierung

### Ansichtsmodi

| Modus | Beschreibung |
|---|---|
| **KldB (Berufe)** | Zeigt nur KldB-Berufshauptgruppen 81 und 83 |
| **WZ (Branchen)** | Zeigt nur WZ-Wirtschaftsabteilungen 87 und 88 |
| **Gesamt** | KldB und WZ gemeinsam |

### Farbmodi

| Modus | Beschreibung | Grün = | Rot = |
|---|---|---|---|
| **Wachstum 2013–heute** | Prozentuale SVB-Veränderung vom frühesten zum neuesten Jahr | Starkes Wachstum | Schrumpfend |
| **Frauenanteil** | Anteil weiblicher SVB | Hoher Frauenanteil | Niedriger Frauenanteil |
| **Teilzeitquote** | Anteil Teilzeitbeschäftigter an SVB | Niedrige TZ-Quote | Hohe TZ-Quote |
| **KI-Exposition** | Geschätzte Exposition gegenüber KI-Automatisierung (0–10) | Geringe Exposition | Hohe Exposition |

### Rechteckgröße

Die Fläche jedes Rechtecks ist proportional zur Anzahl der sozialversicherungspflichtig
Beschäftigten (SVB) zum letzten verfügbaren Stichtag.

### Tooltip

Hover über ein Rechteck zeigt:
- SVB-Bestand und Jahr
- Frauenanteil, Teilzeitquote, Geringfügigenanteil
- Wachstum gesamt und CAGR p.a.
- KI-Expositionsscore mit Begründung

---

## KI-Expositionsscores

Die Scores stammen aus dem BLS-Teil des Projekts (`../scores.json`) und wurden
via LLM auf deutsche Berufsgruppen übertragen. Skala 0–10:

| Score | Bedeutung |
|---|---|
| 0–2 | Kaum KI-Exposition — körperliche Präsenz, manuelle Fürsorge |
| 3–4 | Geringe Exposition — Beziehungsarbeit mit digitalem Anteil |
| 5–6 | Mittlere Exposition — Facharbeit mit KI-unterstützbarer Dokumentation |
| 7–10 | Hohe Exposition — überwiegend digital, starke KI-Substituierbarkeit |

**Mapping KldB → BLS:**

| KldB | BLS-Occupation | Score |
|---|---|---|
| 811 Kinderbetreuung | Childcare workers | 2 |
| 812 Sozialarbeit | Social workers | 4 |
| 813 Heilerziehungspflege | Special education teachers | 5 |
| 831 Krankenpflege | Registered nurses | 4 |
| 832 Rettungsdienst | EMTs and paramedics | 3 |
| 833 Geburtshilfe | Nurse midwives | 5 |

**Caveat:** Die Scores sind grobe LLM-Schätzungen, keine wissenschaftlichen Prognosen.
Ein hoher Score bedeutet nicht, dass der Beruf verschwindet — er beschreibt
das Ausmaß, in dem KI die Arbeit verändern wird.

---

## Entwicklungshistorie

| Datum | Stand |
|---|---|
| 2026-04-09 | Planungsdokument `sozialwesen_plan.md` erstellt; BA-Portal-Struktur und Cookie-Wall analysiert; Playwright als Download-Strategie gewählt; Scope festgelegt (KldB 81/83, WZ 87/88, Bundesebene + Länder + Kreise, Zeitreihe ab 2013) |
| 2026-04-09 | Implementierung: `scrape_ba.py`, `parse_ba.py`, `build_site_data.py`, `site/index.html`; KI-Scores von BLS adaptiert; Demo-Modus in Visualisierung integriert |

---

## Bekannte Einschränkungen

- **BA-Cookie-Wall:** Direkter HTTPS-Zugriff auf Excel-Dateien liefert HTTP 404.
  Der Scraper nutzt Playwright mit echtem Browser-Kontext. Falls Links nicht gefunden
  werden, manuellen Download als Fallback nutzen.
- **Header-Variabilität:** BA-Excel-Dateien haben je nach Jahrgang unterschiedlich
  viele Kopfzeilen. Der Parser probiert automatisch mehrere Varianten; bei Problemen
  `HEADER_ROW` in `parse_ba.py` manuell setzen.
- **Datenschutz-Suppression:** Kreisdaten für kleine Berufsgruppen werden von der BA
  mit `*` gesupprimiert. Der Parser wandelt diese in `NaN` um; betroffene Kreise
  fehlen dann in der Analyse.
- **6-Monats-Wartezeit:** BA-Beschäftigungsdaten erscheinen mit ca. 6 Monaten
  Verzögerung. Aktuellste stabile Daten sind typischerweise vom 30. Juni des Vorjahres.
- **KldB vs. WZ:** Beide Ansätze messen unterschiedliches. KldB = was die Person
  beruflich tut; WZ = in welcher Branche sie arbeitet. Für „soziale Dienstleistungen"
  ist KldB 81/83 der direktere Ansatz; WZ 88 erfasst auch Verwaltungspersonal
  von Sozialträgern.
