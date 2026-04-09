# Plan: Beschäftigungsanalyse Soziale Dienstleistungen (BA-Daten)

## Ziel

Extraktion und Analyse von Beschäftigungsdaten der Bundesagentur für Arbeit (BA)
für den Bereich soziale Dienstleistungen, gefiltert nach:

- **KldB 2010 Berufshauptgruppe 81** – Erziehung, soziale Arbeit, Heilerziehungspflege
- **KldB 2010 Berufshauptgruppe 83** – Gesundheits- und Krankenpflege, Rettungsdienst, Geburtshilfe
- **WZ 2008 Abschnitt Q / Abteilung 88** – Sozialwesen ohne Unterkunft

---

## Schritt 1: Datenquellen identifizieren und herunterladen

### 1a. Beschäftigte nach Berufen (KldB 2010)

**Quelle:** BA Statistik > Fachstatistiken > Beschäftigung > Tabellen  
**URL-Muster:**
```
https://statistik.arbeitsagentur.de/Statistikdaten/Detail/Aktuell/iiia4/
  beschaeftigung-sozbe-kldb-blk/beschaeftigung-sozbe-kldb-blk-d-0-xlsx.xlsx
```

**Enthält:**
- Sozialversicherungspflichtig Beschäftigte (SVB) nach 2-/3-/4-/5-Steller KldB
- Geringfügig Beschäftigte (GB) nach KldB
- Zeitreihen ab 2013 (Stichtag jeweils 30. Juni)
- Gliederung nach Bundesland und Deutschland gesamt

**Ziel-Berufshauptgruppen:**
| Code | Bezeichnung |
|------|-------------|
| 81   | Erziehung, soziale Arbeit, Heilerziehungspflege |
| 811  | Kinderbetreuung, -erziehung |
| 812  | Sozialarb., Sozpäd., Soziolog. |
| 813  | Heilerziehungspflege, Sonderpäd. |
| 83   | Gesundheits- u. Krankenpflege |
| 831  | Gesundheits- u. Krankenpflege |
| 832  | Rettungsdienst |
| 833  | Geburtshilfe |

### 1b. Beschäftigte nach Wirtschaftszweigen (WZ 2008)

**Quelle:** BA Statistik > Fachstatistiken > Beschäftigung > Tabellen  
**URL-Muster:**
```
https://statistik.arbeitsagentur.de/Statistikdaten/Detail/Aktuell/iiia4/
  beschaeftigung-sozbe-wz-blk/beschaeftigung-sozbe-wz-blk-d-0-xlsx.xlsx
```

**Ziel-Wirtschaftszweige:**
| Code | Bezeichnung |
|------|-------------|
| Q    | Gesundheits- und Sozialwesen (Abschnitt) |
| 87   | Heime (ohne Erholungs- und Ferienheime) |
| 88   | Sozialwesen (ohne Unterkunft) |
| 88.1 | Soziale Betreuung älterer Menschen u. Behinderter |
| 88.9 | Sonstiges Sozialwesen |

### 1c. Ergänzende Quellen (optional)

- **Gemeldete Arbeitsstellen nach Berufen** (offene Stellen, Zeitreihe): gleiche Portalstruktur
- **Arbeitslose nach Berufen (KldB)**: für Fachkräftemangel-Analyse
- **Entgelt-Statistik nach Berufen**: für Lohnniveau-Vergleich

---

## Schritt 2: Download-Skript (`download_ba_data.py`)

```python
"""
Lädt Excel-Tabellen der BA Statistik herunter:
- Beschäftigte nach Berufen (KldB 2010)
- Beschäftigte nach Wirtschaftszweigen (WZ 2008)
"""
import httpx
from pathlib import Path

DATA_DIR = Path("data/ba_raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://statistik.arbeitsagentur.de/Statistikdaten/Detail/Aktuell/iiia4"

DOWNLOADS = {
    "beschaeftigung_kldb_bund.xlsx": f"{BASE}/beschaeftigung-sozbe-kldb-blk/beschaeftigung-sozbe-kldb-blk-d-0-xlsx.xlsx",
    "beschaeftigung_wz_bund.xlsx":   f"{BASE}/beschaeftigung-sozbe-wz-blk/beschaeftigung-sozbe-wz-blk-d-0-xlsx.xlsx",
}

for filename, url in DOWNLOADS.items():
    dest = DATA_DIR / filename
    if dest.exists():
        print(f"Already exists: {filename}")
        continue
    print(f"Downloading {filename}...")
    r = httpx.get(url, follow_redirects=True, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"Saved: {dest} ({len(r.content)//1024} KB)")
```

**Hinweis:** Die genauen URL-Pfade müssen beim ersten Durchlauf manuell auf
`statistik.arbeitsagentur.de` verifiziert werden — die BA ändert Dateinamen
gelegentlich bei Aktualisierungen. Alternativ: manueller Download über
`Statistik > Beschäftigung > Tabellen > Excel`.

---

## Schritt 3: Parse-Skript (`parse_ba_data.py`)

Die heruntergeladenen Excel-Dateien haben typischerweise:
- Zeile 1–5: Metadaten/Titel (überspringen)
- Zeile 6: Spaltenheader
- Spalten: Berufscode | Berufsbezeichnung | Jahr/Quartal | SVB gesamt | SVB männlich | SVB weiblich | GB gesamt | ...

```python
import pandas as pd
from pathlib import Path

# KldB-Filter: Berufshauptgruppen 81 und 83 (2-Steller)
KLDB_PREFIXES = ("81", "83")

def parse_kldb(path: Path) -> pd.DataFrame:
    # Titelzeilen überspringen — typischerweise 5-6 Zeilen
    df = pd.read_excel(path, header=5, dtype={"Berufsgruppe": str})
    
    # Nur relevante Berufsgruppen
    mask = df["Berufsgruppe"].str.startswith(KLDB_PREFIXES, na=False)
    return df[mask].copy()

def parse_wz(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, header=5, dtype={"WZ": str})
    
    # WZ 87, 88 und Untergruppen
    mask = df["WZ"].str.startswith(("87", "88", "Q"), na=False)
    return df[mask].copy()

if __name__ == "__main__":
    raw = Path("data/ba_raw")
    out = Path("data/ba_processed")
    out.mkdir(parents=True, exist_ok=True)

    kldb = parse_kldb(raw / "beschaeftigung_kldb_bund.xlsx")
    kldb.to_csv(out / "soziale_berufe_kldb.csv", index=False)
    print(f"KldB: {len(kldb)} Zeilen")

    wz = parse_wz(raw / "beschaeftigung_wz_bund.xlsx")
    wz.to_csv(out / "sozialwesen_wz.csv", index=False)
    print(f"WZ: {len(wz)} Zeilen")
```

**Wichtig:** Header-Zeilennummer (`header=5`) und Spaltennamen müssen nach
dem ersten Download gegen die tatsächliche Dateistruktur geprüft und
angepasst werden.

---

## Schritt 4: Analyseskript (`analyse_sozialwesen.py`)

Zielgrößen der Analyse:

| Metrik | Beschreibung |
|--------|-------------|
| SVB gesamt | Sozialversicherungspflichtig Beschäftigte |
| Anteil Frauen | Feminisierungsgrad des Berufsfelds |
| Anteil Teilzeit | Teilzeitquote |
| Anteil geringfügig | GB / (SVB + GB) |
| Veränderung p.a. | Wachstumsrate Zeitreihe |
| Anforderungsniveau | KldB Steller 5 (Helfer / Fachkraft / Spezialist / Experte) |

---

## Schritt 5: Datenstruktur (Output)

```
data/
  ba_raw/
    beschaeftigung_kldb_bund.xlsx      # Original-Download KldB
    beschaeftigung_wz_bund.xlsx        # Original-Download WZ
  ba_processed/
    soziale_berufe_kldb.csv            # Gefiltert auf BHG 81, 83
    sozialwesen_wz.csv                 # Gefiltert auf WZ 87, 88
    summary.csv                        # Aggregierte Kennzahlen für Visualisierung
```

---

## Offene Fragen (vor Implementierung klären)

1. **Geographische Ebene:** Bundesweit reicht aus, oder sollen Bundesländer / Kreise einbezogen werden?
2. **Zeitraum:** Zeitreihe ab 2013 (Beginn KldB 2010) oder nur aktuelles Jahr?
3. **Abgrenzung:** Nur KldB-Ansatz, nur WZ-Ansatz, oder beide parallel (für Kreuzvalidierung)?
4. **Anforderungsniveau:** Soll nach Helfer/Fachkraft/Spezialist/Experte (5. Stelle KldB) differenziert werden?
5. **Vergleichsgruppen:** Soll ein Vergleich mit anderen Berufsfeldern (z.B. IT, Bau) eingebaut werden?
6. **Output:** Reine Datenextraktion als CSV, oder auch Visualisierung (analog zum BLS-Projekt)?
