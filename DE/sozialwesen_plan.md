# Plan: Beschäftigungsanalyse Soziale Dienstleistungen (BA-Daten)

## Scope

- **Geographie:** Deutschland gesamt + Bundesländer + Kreise (sofern verfügbar)
- **Zeitraum:** 2013–heute (Jahresstichtage 30. Juni, KldB-Zeitreihe)
- **Filter:**
  - KldB 2010 Berufshauptgruppe **81** – Erziehung, soziale Arbeit, Heilerziehungspflege
  - KldB 2010 Berufshauptgruppe **83** – Gesundheits- und Krankenpflege
  - WZ 2008 Abteilung **87/88** – Heime, Sozialwesen
- **Output:** Bereinigte CSVs + Visualisierung (analog BLS-Treemap)

---

## Erkenntnisse zur Datenstruktur (verifiziert 2026-04-09)

Die BA-Statistik-Seite läuft hinter einer Cookie-Wall. Direkte HTTPS-Anfragen
auf Excel-Dateien geben **HTTP 404** zurück — der Server liefert Dateien nur
nach Portalnavigation mit Session-Cookie. Konsequenz:

> **Download muss per Playwright (Browser-Automatisierung) erfolgen**, nicht per `httpx`.
> Das Projekt nutzt Playwright bereits für den BLS-Teil (`scrape.py`).

Bekanntes funktionierendes URL-Schema (aus Monatsbericht-Link verifiziert):
```
https://statistik.arbeitsagentur.de/Statistikdaten/Detail/{YYYYMM}/{kategorie}/{dateiname}-{YYYYMM}-xlsx.xlsx
```

Die genauen Dateinamen-Segmente für Beschäftigung nach KldB/WZ müssen beim
ersten Playwright-Lauf aus dem Portal-HTML extrahiert werden (Link-Harvesting).

### Verfügbare Tabellentypen (BA Beschäftigung)

| Kürzel | Inhalt | Gliederung |
|--------|--------|-----------|
| `sozbe-kldb-blk` | SVB + GB nach KldB 2010 | Bund + Länder |
| `sozbe-kldb-kreis` | SVB + GB nach KldB 2010 | Kreise |
| `sozbe-wz-blk` | SVB + GB nach WZ 2008 | Bund + Länder |
| `sozbe-wz-kreis` | SVB + GB nach WZ 2008 | Kreise |

Kreis-Ebene: **Verfügbarkeit noch zu prüfen** — nicht alle Merkmale werden
auf Kreisebene veröffentlicht, insbesondere bei kleinen Berufsgruppen
(Datenschutz-Suppression möglich).

---

## Projektstruktur

```
DE/
  sozialwesen_plan.md          ← dieser Plan
  scrape_ba.py                 ← Playwright-Download (Schritt 1)
  parse_ba.py                  ← Excel → CSV (Schritt 2)
  build_site_data.py           ← CSV → site/data.json (Schritt 3)
  site/                        ← Visualisierung (Schritt 4)
    index.html
    data.json
  data/
    raw/                       ← Original-Downloads (nicht im Git)
      kldb_bund/               # Zeitreihe Bund+Länder
      kldb_kreis/              # Zeitreihe Kreise (falls verfügbar)
      wz_bund/
      wz_kreis/
    processed/
      soziale_berufe_kldb.csv  # Gefiltert BHG 81, 83 — alle Jahre, alle Ebenen
      sozialwesen_wz.csv       # Gefiltert WZ 87, 88 — alle Jahre, alle Ebenen
      summary.csv              # Aggregiert für Visualisierung
```

---

## Schritt 1: Portal-Scraper (`DE/scrape_ba.py`)

Da direkte URLs Session-Cookies erfordern, navigiert Playwright das Portal
und harvested Download-Links, dann lädt die Dateien herunter.

```python
"""
Lädt BA-Beschäftigungsstatistik-Excel per Playwright herunter.
Navigiert statistik.arbeitsagentur.de und extrahiert alle xlsx-Links
für die Kategorien sozbe-kldb und sozbe-wz (Bund+Länder und Kreise).
"""
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://statistik.arbeitsagentur.de"
NAV_URL = (
    f"{BASE_URL}/DE/Navigation/Statistiken/Fachstatistiken/"
    "Beschaeftigung/Beschaeftigung-Nav.html"
)

TARGET_PATTERNS = [
    r"sozbe-kldb-blk",
    r"sozbe-kldb-kreis",
    r"sozbe-wz-blk",
    r"sozbe-wz-kreis",
]

RAW_DIR = Path("DE/data/raw")

async def harvest_and_download():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Cookie-Banner akzeptieren
        await page.goto(NAV_URL)
        try:
            await page.click("text=Alle zulassen", timeout=5000)
        except Exception:
            pass
        await page.wait_for_load_state("networkidle")

        # Alle xlsx-Links auf der Seite und verlinkten Unterseiten sammeln
        links = await page.eval_on_selector_all(
            "a[href*='.xlsx']",
            "els => els.map(e => e.href)"
        )

        for url in links:
            for pattern in TARGET_PATTERNS:
                if re.search(pattern, url):
                    # Zielordner aus Muster ableiten
                    category = re.search(r"sozbe-\w+-\w+", url).group()
                    dest_dir = RAW_DIR / category
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    filename = url.split("/")[-1].split("?")[0]
                    dest = dest_dir / filename
                    if dest.exists():
                        print(f"Skip: {filename}")
                        continue
                    print(f"Download: {filename}")
                    response = await page.request.get(url)
                    dest.write_bytes(await response.body())
                    print(f"  → {dest}")
                    break

        await browser.close()

if __name__ == "__main__":
    asyncio.run(harvest_and_download())
```

**Fallback (manueller Download):** Falls Playwright die Links nicht findet,
manuell auf `statistik.arbeitsagentur.de > Statistiken > Beschäftigung > Tabellen`
navigieren und Excel-Dateien in `DE/data/raw/{kategorie}/` ablegen.

---

## Schritt 2: Parse-Skript (`DE/parse_ba.py`)

BA-Excel-Dateien haben typischerweise 5–7 Kopfzeilen (Titel, Quellenangabe,
Stichtag). Die genaue Header-Zeile wird beim ersten Durchlauf angepasst.

```python
"""
Liest BA-Excel-Tabellen, filtert auf KldB 81/83 und WZ 87/88,
normalisiert Zeitreihen (2013–heute) und schreibt CSVs.
Unterstützt Bund+Länder und Kreisebene in einem Durchlauf.
"""
import pandas as pd
from pathlib import Path

RAW_DIR   = Path("DE/data/raw")
PROC_DIR  = Path("DE/data/processed")
PROC_DIR.mkdir(parents=True, exist_ok=True)

KLDB_PREFIXES = ("81", "83")
WZ_PREFIXES   = ("87", "88", "Q")

# Jahrgang aus Dateinamen extrahieren, z.B. "...202406..." → 2024
import re
def year_from_path(p: Path) -> int:
    m = re.search(r"(\d{4})\d{2}", p.stem)
    return int(m.group(1)) if m else 0

def read_ba_excel(path: Path, code_col: str, prefixes: tuple) -> pd.DataFrame:
    # Kopfzeilen überspringen — BA-Standard: 5 Zeilen (anpassen nach erstem Test)
    df = pd.read_excel(path, header=5, dtype={code_col: str})
    df = df[df[code_col].str.startswith(prefixes, na=False)].copy()
    df["year"] = year_from_path(path)
    df["source_file"] = path.name
    return df

def process_category(raw_subdir: str, code_col: str, prefixes: tuple, out_name: str):
    frames = []
    for xlsx in sorted((RAW_DIR / raw_subdir).glob("*.xlsx")):
        try:
            df = read_ba_excel(xlsx, code_col, prefixes)
            frames.append(df)
        except Exception as e:
            print(f"  WARN {xlsx.name}: {e}")
    if frames:
        out = pd.concat(frames, ignore_index=True)
        # Nur 2013–heute
        out = out[out["year"] >= 2013]
        out.to_csv(PROC_DIR / out_name, index=False)
        print(f"{out_name}: {len(out)} Zeilen, {out['year'].nunique()} Jahre")

if __name__ == "__main__":
    # KldB — Bund+Länder
    process_category("sozbe-kldb-blk",   "Berufsgruppe", KLDB_PREFIXES, "kldb_blk.csv")
    # KldB — Kreise (falls vorhanden)
    process_category("sozbe-kldb-kreis", "Berufsgruppe", KLDB_PREFIXES, "kldb_kreis.csv")
    # WZ — Bund+Länder
    process_category("sozbe-wz-blk",     "WZ",           WZ_PREFIXES,   "wz_blk.csv")
    # WZ — Kreise (falls vorhanden)
    process_category("sozbe-wz-kreis",   "WZ",           WZ_PREFIXES,   "wz_kreis.csv")
```

**Zu prüfen nach erstem Download:**
- Korrekte `header=`-Zeilennummer (typisch: 4–6)
- Exakte Spaltennamen (`Berufsgruppe`, `WZ`, `Insgesamt`, `Männer`, `Frauen`, `Teilzeit`, ...)
- Ob Kreisdaten überhaupt für KldB 81/83 geliefert werden (Datenschutz-Suppression)

---

## Schritt 3: Site-Daten (`DE/build_site_data.py`)

Erzeugt `DE/site/data.json` für die Treemap-Visualisierung.
Struktur analog `build_site_data.py` im BLS-Teil:

```json
{
  "nodes": [
    {
      "id": "81",
      "label": "Erziehung, soziale Arbeit",
      "parent": null,
      "svb_2024": 123456,
      "svb_2013": 98765,
      "change_pct": 25.0,
      "anteil_frauen": 0.82,
      "anteil_teilzeit": 0.45,
      "anteil_geringfuegig": 0.08,
      "geo": "DE",
      "geo_type": "bund"
    }
  ],
  "years": [2013, 2014, ..., 2024],
  "geo_levels": ["bund", "land", "kreis"]
}
```

---

## Schritt 4: Visualisierung (`DE/site/`)

Analog BLS-Projekt: interaktive Treemap mit D3.js.

**Dimensionen:**
- Rechteckgröße: SVB-Bestand (aktuellstes Jahr)
- Farbe (wählbar): Veränderung 2013–heute | Frauenanteil | Teilzeitquote | Geringfügigenanteil
- Filter: Geographieebene (Bund / Land / Kreis) + Jahr-Slider

**Erweiterung gegenüber BLS-Projekt:**
- Zeitreihen-Slider (2013–heute)
- Geo-Dropdown (Bundesland / Kreis auswählen)
- KldB- und WZ-Ansicht umschaltbar

---

## Metriken der Analyse

| Metrik | Spalte (BA) | Beschreibung |
|--------|------------|--------------|
| SVB gesamt | `Insgesamt` | Sozialversicherungspflichtig Beschäftigte |
| SVB Frauen | `Frauen` | Absolut + Anteil |
| SVB Teilzeit | `Teilzeit` | Absolut + Anteil |
| Geringfügig Beschäftigte | GB-Spalten | Absolut + Anteil an Gesamtbeschäftigung |
| Wachstum p.a. | berechnet | CAGR 2013–heute |
| Anforderungsniveau | KldB Stelle 5 | Helfer / Fachkraft / Spezialist / Experte |

---

## Implementierungsreihenfolge

1. `DE/scrape_ba.py` ausführen → Raw-Excel in `DE/data/raw/`
2. Dateistruktur der Excel-Dateien prüfen (Header, Spaltennamen)
3. `DE/parse_ba.py` anpassen und ausführen → CSVs in `DE/data/processed/`
4. `DE/build_site_data.py` schreiben → `DE/site/data.json`
5. `DE/site/index.html` erstellen (D3-Treemap, analog BLS-Site)

---

## Hinweise

- **Wartezeit:** BA-Beschäftigungsdaten haben 6 Monate Wartezeit; aktuellste
  stabile Daten sind i.d.R. vom 30. Juni des Vorjahres.
- **Kreisdaten:** Werden für kleine Berufsgruppen oft durch `*` (Datenschutz)
  supprimiert. Fallback: Aggregation auf Länderebene.
- **KldB vs. WZ:** Beide Ansätze messen unterschiedliches:
  KldB = was die Person beruflich tut; WZ = in welcher Branche sie arbeitet.
  Für „soziale Dienstleistungen" ist KldB 81/83 der direktere Ansatz;
  WZ 88 erfasst auch Verwaltungspersonal von Sozialträgern.
