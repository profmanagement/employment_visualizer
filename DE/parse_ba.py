"""
Liest BA-Excel-Tabellen (KldB + WZ), filtert auf relevante Berufsgruppen
und schreibt bereinigte CSVs nach DE/data/processed/.

Unterstützte Kategorien:
  sozbe-kldb-blk    → BHG 81–88 Soziales, Bildung, Gesundheit (Bund + Länder)
  sozbe-kldb-kreis  → BHG 81–88 (Kreise)
  sozbe-wz-blk      → WZ 85–88 Bildung, Gesundheit, Sozialwesen (Bund + Länder)
  sozbe-wz-kreis    → WZ 85–88 (Kreise)

Verwendung:
    uv run python DE/parse_ba.py

Hinweis:
    BA-Excel-Dateien variieren im internen Aufbau je nach Jahrgang.
    Falls der erste Durchlauf keine Zeilen liefert, bitte Header-Zeilen-
    Nummer (HEADER_ROW) und Spaltennamen-Mappings unten anpassen.
"""

import re
import sys
from pathlib import Path

import pandas as pd

RAW_DIR  = Path(__file__).parent / "data" / "raw"
PROC_DIR = Path(__file__).parent / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

# Zu filternde Codes
# KldB: Soziales (81), Lehrende (82), Pflege (83), Therapie (84),
#        Medizin (85), Pharmazie (86), Psychologie (87), Medizintechnik (88)
KLDB_PREFIXES = ("81", "82", "83", "84", "85", "86", "87", "88")
# WZ: Erziehung/Unterricht (85), Gesundheitswesen (86), Heime (87),
#     Sozialwesen (88)
WZ_PREFIXES   = ("85", "86", "87", "88", "Q")

# Wie viele Kopfzeilen BA-Excel-Dateien typischerweise haben.
# Falls parse_ba.py keine Zeilen findet: 4, 5, 6 oder 7 ausprobieren.
HEADER_ROW = 5

# Spaltennamen-Kandidaten für den Code (erste Treffer-Spalte wird verwendet)
CODE_COL_CANDIDATES = [
    "Berufsgruppe", "Berufshauptgruppe", "Beruf", "KldB",
    "WZ", "Wirtschaftszweig", "WZ-Code",
    "Unnamed: 0",  # Fallback wenn erste Spalte keinen Kopf hat
]

# Spaltennamen-Kandidaten für SVB/GB-Werte
COLUMN_MAP_CANDIDATES = {
    "svb_gesamt":   ["Insgesamt", "SVB insgesamt", "Beschäftigte insgesamt", "SVB_gesamt"],
    "svb_maenner":  ["Männer", "SVB Männer", "männlich"],
    "svb_frauen":   ["Frauen", "SVB Frauen", "weiblich"],
    "svb_teilzeit": ["Teilzeit", "SVB Teilzeit", "TZ"],
    "gb_gesamt":    ["Geringfügig Beschäftigte", "GB insgesamt", "GB_gesamt", "Geringfügig"],
}


def year_from_path(p: Path) -> int:
    """Extrahiert Jahrgang aus BA-Dateinamen, z.B. '...202406...' → 2024."""
    m = re.search(r"(\d{4})\d{2}", p.stem)
    return int(m.group(1)) if m else 0


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Gibt den ersten Spaltennamen zurück, der in df vorkommt."""
    for c in candidates:
        if c in df.columns:
            return c
    # Fuzzy: Teilstring-Suche (case-insensitive)
    for c in candidates:
        for col in df.columns:
            if c.lower() in str(col).lower():
                return col
    return None


def read_ba_excel(path: Path, code_col_candidates: list[str], prefixes: tuple) -> pd.DataFrame | None:
    """
    Liest eine BA-Excel-Datei, überspringt Kopfzeilen und filtert
    auf die gewünschten Code-Präfixe.
    """
    # Versuche verschiedene Header-Zeilen falls Standard nicht passt
    for header in [HEADER_ROW, 4, 6, 7, 3]:
        try:
            df = pd.read_excel(path, header=header, dtype=str)
        except Exception as e:
            print(f"    WARN read_excel(header={header}): {e}")
            continue

        code_col = find_col(df, code_col_candidates)
        if code_col is None:
            continue

        df[code_col] = df[code_col].astype(str).str.strip()
        mask = df[code_col].str.startswith(prefixes, na=False)
        filtered = df[mask].copy()
        if len(filtered) > 0:
            return filtered, code_col

    return None, None


def normalize_frame(df: pd.DataFrame, code_col: str, path: Path) -> pd.DataFrame:
    """Benennt Spalten in ein einheitliches Schema um."""
    out = pd.DataFrame()
    out["code"]        = df[code_col].str.strip()
    out["year"]        = year_from_path(path)
    out["source_file"] = path.name

    # Bezeichnung (zweite Spalte nach Code, falls vorhanden)
    cols = [c for c in df.columns if c != code_col]
    if cols:
        # Erste nicht-Code-Spalte = Bezeichnung
        out["bezeichnung"] = df[cols[0]].astype(str).str.strip()
    else:
        out["bezeichnung"] = ""

    for target, candidates in COLUMN_MAP_CANDIDATES.items():
        col = find_col(df, candidates)
        if col:
            # BA nutzt '*' für Datenschutz-Suppression → NaN
            out[target] = pd.to_numeric(
                df[col].astype(str).str.replace(r"[*\s]", "", regex=True),
                errors="coerce"
            )
        else:
            out[target] = pd.NA

    return out


def process_category(
    raw_subdir: str,
    code_col_candidates: list[str],
    prefixes: tuple,
    out_name: str,
) -> None:
    src = RAW_DIR / raw_subdir
    if not src.exists():
        print(f"  Verzeichnis nicht gefunden: {src}  (übersprungen)")
        return

    xlsx_files = sorted(src.glob("*.xlsx"))
    if not xlsx_files:
        print(f"  Keine .xlsx-Dateien in {src}  (übersprungen)")
        return

    frames = []
    for xlsx in xlsx_files:
        print(f"  Lese: {xlsx.name}")
        result, code_col = read_ba_excel(xlsx, code_col_candidates, prefixes)
        if result is None or len(result) == 0:
            print(f"    WARN: Keine passenden Zeilen gefunden (Header/Spaltennamen prüfen)")
            continue
        normed = normalize_frame(result, code_col, xlsx)
        print(f"    → {len(normed)} Zeilen, Jahr {normed['year'].iloc[0]}")
        frames.append(normed)

    if not frames:
        print(f"  Keine Daten für {out_name}")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[combined["year"] >= 2013]
    combined = combined.sort_values(["code", "year"]).reset_index(drop=True)

    dest = PROC_DIR / out_name
    combined.to_csv(dest, index=False)
    print(f"  → {dest}  ({len(combined)} Zeilen, {combined['year'].nunique()} Jahre)")


def main():
    print("=== parse_ba.py ===\n")

    print("KldB BHG 81–88 (Soziales, Bildung, Gesundheit) — Bund + Länder:")
    process_category("sozbe-kldb-blk",   CODE_COL_CANDIDATES, KLDB_PREFIXES, "kldb_blk.csv")

    print("\nKldB BHG 81–88 — Kreise:")
    process_category("sozbe-kldb-kreis", CODE_COL_CANDIDATES, KLDB_PREFIXES, "kldb_kreis.csv")

    print("\nWZ 85–88 (Bildung, Gesundheit, Sozialwesen) — Bund + Länder:")
    process_category("sozbe-wz-blk",     CODE_COL_CANDIDATES, WZ_PREFIXES,   "wz_blk.csv")

    print("\nWZ 85–88 — Kreise:")
    process_category("sozbe-wz-kreis",   CODE_COL_CANDIDATES, WZ_PREFIXES,   "wz_kreis.csv")

    print("\nFertig.")


if __name__ == "__main__":
    main()
