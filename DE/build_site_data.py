"""
Baut DE/site/data.json aus den verarbeiteten CSVs und BLS-AI-Scores.

Quellen:
  DE/data/processed/kldb_blk.csv  – KldB BHG 81–88 (Soziales, Bildung, Gesundheit)
  DE/data/processed/wz_blk.csv   – WZ 85–88 (Bildung, Gesundheit, Sozialwesen)
  ../scores.json                  – BLS AI-Exposure-Scores (EN → DE gemappt)

Ausgabe:
  DE/site/data.json               – Für Treemap-Visualisierung

Verwendung:
    uv run python DE/build_site_data.py
"""

import json
import math
from pathlib import Path

import pandas as pd

HERE      = Path(__file__).parent
PROC_DIR  = HERE / "data" / "processed"
SITE_DIR  = HERE / "site"
SITE_DIR.mkdir(parents=True, exist_ok=True)

BLS_SCORES_PATH = HERE.parent / "scores.json"

# ── AI-Exposure-Mapping: KldB/WZ → BLS-Slug ────────────────────────────────
# Scores stammen aus scores.json (BLS Occupational Outlook Handbook, LLM-bewertet).
# Skala 0–10: 0 = kaum KI-Exposition, 10 = vollständig digital/automatisierbar.

KLDB_BLS_MAP: dict[str, str] = {
    # BHG 81 – Erziehung, soziale Arbeit, Heilerziehungspflege
    "81":  "social-workers",
    "811": "childcare-workers",                                          # → 2
    "812": "social-workers",                                             # → 4
    "813": "special-education-teachers",                                 # → 5
    # BHG 82 – Lehrende und Ausbildende
    "82":  "high-school-teachers",
    "821": "high-school-teachers",                                       # → 7
    "822": "middle-school-teachers",                                     # → 6
    "823": "postsecondary-teachers",                                     # → 7
    "824": "preschool-teachers",                                         # → 3
    # BHG 83 – Gesundheits- und Krankenpflege
    "83":  "registered-nurses",
    "831": "registered-nurses",                                          # → 4
    "832": "emts-and-paramedics",                                        # → 3
    "833": "nurse-anesthetists-nurse-midwives-and-nurse-practitioners",  # → 5
    # BHG 84 – Therapie und Heilpraktik
    "84":  "physical-therapists",
    "841": "physical-therapists",                                        # → 3
    "842": "occupational-therapists",                                    # → 3
    "843": "speech-language-pathologists",                               # → 3
    # BHG 85 – Human- und Zahnmedizin, Tiermedizin
    "85":  "physicians-and-surgeons",
    "851": "physicians-and-surgeons",                                    # → 5
    "852": "dentists",                                                   # → 3
    "853": "veterinarians",                                              # → 4
    # BHG 86 – Psychologie, nichtärztliche Psychotherapie
    "86":  "psychologists",
    "861": "psychologists",                                              # → 6
    # BHG 87 – Pharmazie
    "87":  "pharmacists",
    "871": "pharmacists",                                                # → 5
    # BHG 88 – Medizintechnik, Orthoptik, Audiologie
    "88":  "health-educators",
    "881": "health-educators",                                           # → 6
}

WZ_BLS_MAP: dict[str, str] = {
    # WZ 85 – Erziehung und Unterricht
    "85":   "high-school-teachers",                                      # → 7
    "85.1": "preschool-teachers",                                        # → 3
    "85.2": "high-school-teachers",                                      # → 7
    "85.3": "postsecondary-teachers",                                    # → 7
    "85.4": "health-educators",                                          # → 6
    # WZ 86 – Gesundheitswesen
    "86":   "physicians-and-surgeons",                                   # → 5
    "86.1": "registered-nurses",                                         # → 4
    "86.2": "physicians-and-surgeons",                                   # → 5
    "86.9": "physical-therapists",                                       # → 3
    # WZ 87 – Heime
    "87":   "nursing-assistants",                                        # → 2
    "87.1": "registered-nurses",                                         # → 4
    "87.2": "social-workers",                                            # → 4
    "87.3": "nursing-assistants",                                        # → 2
    # WZ 88 – Sozialwesen ohne Unterkunft
    "88":   "social-workers",                                            # → 4
    "88.1": "nursing-assistants",                                        # → 2
    "88.9": "recreation-workers",                                        # → 3
    # Abschnitt Q gesamt
    "Q":    "registered-nurses",                                         # → 4
}

# ── Beschreibungen auf Deutsch ─────────────────────────────────────────────

KLDB_LABELS: dict[str, str] = {
    # Soziales
    "81":  "Erziehung, soziale Arbeit, Heilerziehungspflege",
    "811": "Kinderbetreuung und -erziehung",
    "812": "Sozialarbeit, Sozialpädagogik",
    "813": "Heilerziehungspflege, Sonderpädagogik",
    # Bildung
    "82":  "Lehrende und Ausbildende",
    "821": "Lehrtätigkeit allgemeinbildende Schulen",
    "822": "Lehrtätigkeit berufsbildende Schulen",
    "823": "Hochschullehre und -forschung",
    "824": "Außerschulische Bildung, Kursleitung",
    # Pflege
    "83":  "Gesundheits- u. Krankenpflege, Rettungsdienst, Geburtshilfe",
    "831": "Gesundheits- und Krankenpflege",
    "832": "Rettungsdienst",
    "833": "Geburtshilfe (Hebammen)",
    # Therapie
    "84":  "Therapie und Heilpraktik",
    "841": "Physiotherapie",
    "842": "Ergotherapie",
    "843": "Logopädie, Sprachtherapie",
    # Medizin
    "85":  "Human- und Zahnmedizin, Tiermedizin",
    "851": "Humanmedizin (Ärzt*innen)",
    "852": "Zahnmedizin",
    "853": "Tiermedizin",
    # Psychologie
    "86":  "Psychologie, nichtärztliche Psychotherapie",
    "861": "Psychologische Beratung und Therapie",
    # Pharmazie
    "87":  "Pharmazie",
    "871": "Apotheke und Pharmaberatung",
    # Medizintechnik
    "88":  "Medizintechnik, Orthoptik, Audiologie",
    "881": "Medizintechnischer Dienst",
}

WZ_LABELS: dict[str, str] = {
    # Bildung
    "85":   "Erziehung und Unterricht (WZ 85)",
    "85.1": "Kindergärten, Vor- und Grundschulen (WZ 85.1)",
    "85.2": "Weiterführende Schulen (WZ 85.2)",
    "85.3": "Hochschulen (WZ 85.3)",
    "85.4": "Sonstiger Unterricht (WZ 85.4)",
    # Gesundheit
    "86":   "Gesundheitswesen (WZ 86)",
    "86.1": "Krankenhäuser (WZ 86.1)",
    "86.2": "Arzt- und Zahnarztpraxen (WZ 86.2)",
    "86.9": "Sonstiges Gesundheitswesen (WZ 86.9)",
    # Heime
    "87":   "Heime (WZ 87)",
    "87.1": "Pflegeheime (WZ 87.1)",
    "87.2": "Einrichtungen f. psych. Behinderungen (WZ 87.2)",
    "87.3": "Alten- und Pflegeheime (WZ 87.3)",
    # Sozialwesen
    "88":   "Sozialwesen ohne Unterkunft (WZ 88)",
    "88.1": "Soziale Betreuung Älterer u. Behinderter (WZ 88.1)",
    "88.9": "Sonstiges Sozialwesen (WZ 88.9)",
    # Abschnitt Q
    "Q":    "Gesundheits- und Sozialwesen gesamt (WZ Q)",
}

# ── KI-Exposure-Rationale auf Deutsch ─────────────────────────────────────

KLDB_RATIONALE: dict[str, str] = {
    # Soziales
    "81":  "Berufe in Erziehung und sozialer Arbeit sind stark personenbezogen und erfordern physische Präsenz sowie emotionale Kompetenz. KI kann administrative Aufgaben und Dokumentation übernehmen, der Kernbereich menschlicher Beziehungsarbeit bleibt jedoch weitgehend geschützt.",
    "811": "Kinderbetreuung erfordert kontinuierliche körperliche Anwesenheit, nonverbale Kommunikation und Fürsorge — Bereiche, in denen KI kaum substituieren kann. Administrative Aufgaben könnten automatisiert werden.",
    "812": "Sozialarbeiter*innen verbringen viel Zeit mit Beratung, Krisenintervention und Behördenkoordination. Dokumentation und Fallverwaltung sind KI-zugänglich; der direkte Klientenkontakt bleibt menschlich.",
    "813": "Heilerziehungspflege kombiniert pädagogische Facharbeit mit pflegerischer Begleitung. Individuelle Förderplanung kann KI-gestützt werden, der unmittelbare Beziehungsaufbau bleibt durch KI kaum ersetzbar.",
    # Bildung
    "82":  "Lehrende sind mit zunehmendem KI-Einsatz konfrontiert: Unterrichtsplanung, Materialerstellung und Feedback können KI-gestützt werden. Der direkte Unterricht und die Beziehungsgestaltung zur Klasse bleiben menschlich geprägt, jedoch ist die Exposition insgesamt höher als in Pflegeberufen.",
    "821": "Lehrkräfte an allgemeinbildenden Schulen erstellen wissensbasierte Inhalte und geben Feedback — beides KI-affine Tätigkeiten. Die Klassenführung, soziale Begleitung und individuelle Förderung erfordern weiterhin menschliche Präsenz.",
    "822": "Berufliche Bildung verbindet Fachtheorie (KI-zugänglich) mit praktischer Ausbildung an Maschinen und in Betrieben (KI-resistent). Die Exposition ist heterogen je nach Fachrichtung.",
    "823": "Hochschullehrende forschen und lehren überwiegend digital — Literaturauswertung, Manuskripterstellung und Prüfungsbewertung sind KI-affin. Originäre Forschungsideen und Lehrkommunikation bleiben menschliche Domänen.",
    "824": "Kursleitung und außerschulische Bildung ist stark kontextabhängig: digitale Weiterbildung ist hoch KI-exponiert, handwerkliche und sportliche Kurse kaum.",
    # Pflege
    "83":  "Pflegeberufe verbinden Fachwissen mit körperlicher Pflege und emotionaler Unterstützung. Diagnostik und Dokumentation sind KI-affin; Grundpflege, Patientenkommunikation und komplexe Situationsbeurteilung erfordern menschliches Urteil.",
    "831": "Krankenpfleger*innen übernehmen sowohl wissensintensive Aufgaben (Medikation, Vitalkontrolle) als auch körperliche Pflegehandlungen. KI kann Entscheidungsunterstützung und Dokumentation verbessern, nicht jedoch Pflege ersetzen.",
    "832": "Rettungssanitäter*innen arbeiten in unvorhersehbaren Notfallsituationen, die physische Präsenz und Schnellentscheidung erfordern. KI-Dispatch und Navigationsunterstützung sind möglich, der Kerneinsatz bleibt menschlich.",
    "833": "Hebammen leisten persönliche Begleitung während Schwangerschaft und Geburt. KI kann Risikoscreening und Dokumentation unterstützen; die direkte Geburtsbegleitung erfordert zwingend menschliche Präsenz.",
    # Therapie
    "84":  "Therapeutische Berufe kombinieren diagnostisches Fachwissen (KI-unterstützbar) mit körperlicher Behandlung und therapeutischer Beziehung. Befunddokumentation und Therapieplanung sind KI-zugänglich; die manuelle Behandlung und das therapeutische Verhältnis bleiben menschlich.",
    "841": "Physiotherapeut*innen arbeiten primär durch körperliche Behandlung — Mobilisation, Massage, Übungsanleitung. KI kann Befunderhebung und Übungsplanung unterstützen, ersetzt aber nicht den Behandlungskontakt.",
    "842": "Ergotherapie ist stark auf individuelle Alltagsanpassung ausgerichtet. Dokumentation und Therapieplanung sind KI-affin; die handlungsbasierte Therapiesitzung erfordert körperliche Ko-Präsenz.",
    "843": "Logopädie kombiniert Sprachdiagnostik (zunehmend KI-gestützt) mit individueller Sprachtherapie. KI-Tools für Sprachanalyse und Übungsrückmeldung sind bereits im Einsatz; der therapeutische Prozess bleibt menschlich.",
    # Medizin
    "85":  "Ärztliche Berufe sind stärker KI-exponiert als Pflegeberufe: Diagnostik, Bildauswertung und Literaturrecherche sind hochgradig KI-affin. Operativer und invasiver Eingriff sowie Patientenkommunikation erfordern weiterhin menschliches Urteil und Präsenz.",
    "851": "Ärzt*innen sind mit schnell wachsenden KI-Fähigkeiten konfrontiert: Radiologiebefunde, Pathologiediagnosen und klinische Entscheidungsunterstützung werden KI-gestützt. Arzt-Patienten-Gespräch, ethische Abwägung und operative Eingriffe bleiben menschlich.",
    "852": "Zahnärzt*innen arbeiten überwiegend körperlich-manuell. Diagnostik (Röntgenauswertung) ist KI-zugänglich; Behandlung am Patienten erfordert manuelle Präzision und persönliche Beziehung.",
    "853": "Tierärzt*innen kombinieren klinische Diagnostik mit manueller Behandlung und Chirurgie. KI kann Bilddiagnostik und Anamnese unterstützen; physische Untersuchung und operative Eingriffe bleiben menschliche Domäne.",
    # Psychologie
    "86":  "Psychologische Berufe sind zweigespalten: wissensintensive Diagnostik und Gutachtenerstellung sind hoch KI-exponiert; die therapeutische Beziehung und klinische Einschätzung komplexer Lebenssituationen bleiben menschlich geprägt.",
    "861": "Psychologische Beratung und Therapie basiert auf vertrauensvoller Beziehungsarbeit. KI kann Diagnostikinstrumente und Dokumentation unterstützen; die therapeutische Interaktion selbst hat einen erheblichen menschlichen Schutz.",
    # Pharmazie
    "87":  "Apotheker*innen übernehmen zunehmend beratungsintensive Aufgaben, da Dispensierung und Logistik automatisierbar sind. Arzneimittelinteraktionsprüfung ist KI-affin; persönliche Beratung und Medikationsmanagement bleiben menschlich.",
    "871": "Apothekenarbeit ist eine Mischung aus digitaler Datenverwaltung (KI-zugänglich) und persönlicher Beratung (menschlich). Routineaufgaben in der Logistik können vollständig automatisiert werden.",
    # Medizintechnik
    "88":  "Medizintechnische Berufe verbinden technisches Fachwissen mit praktischer Anwendung an Patient*innen. Geräteauswertung und Dokumentation sind KI-affin; Bedienung, Kalibrierung und Patientenbegleitung erfordern Präsenz.",
    "881": "Medizintechniker*innen warten und bedienen diagnostische Geräte. Auswertungsalgorithmen sind KI-affin; technische Wartung und Patientenkontakt bleiben körperlich.",
}

WZ_RATIONALE: dict[str, str] = {
    # Bildung
    "85":   "Der Bildungssektor steht KI-bedingten Veränderungen gegenüber: Unterrichtsmaterialien, Prüfungsbewertung und Lernstandsdiagnose sind KI-zugänglich. Direkte Lehr- und Erziehungsarbeit sowie schulisches Beziehungsgeschehen bleiben menschlich geprägt.",
    "85.1": "Kindergärten und Grundschulen sind stark durch Präsenzarbeit, emotionale Begleitung und frühkindliche Förderung geprägt. KI kann administrative Aufgaben übernehmen; der Kern der frühkindlichen Bildung bleibt menschlich.",
    "85.2": "Weiterführende Schulen kombinieren wissensbasierte Unterrichtsarbeit (KI-affin) mit Erziehungsaufgaben und Klassenführung. Exposition höher als im Primarbereich, aber Beziehungsarbeit schützt.",
    "85.3": "Hochschulen sind stark KI-exponiert: Forschung, Lehrmaterialien, Prüfungen und Verwaltung verändern sich durch KI grundlegend. Originäre Forschung und Wissensvermittlung im Dialog bleiben menschliche Stärken.",
    "85.4": "Sonstiger Unterricht (Volkshochschulen, Sprachschulen, Fahrschulen) variiert stark: digitale Kurse sind hoch exponiert, körperlich-praktische Ausbildung kaum.",
    # Gesundheit
    "86":   "Das Gesundheitswesen insgesamt ist mittelstark KI-exponiert: Diagnostik, Bildauswertung und Dokumentation verändern sich stark; körperliche Behandlung und Patientenbeziehung bleiben menschlich.",
    "86.1": "Krankenhäuser beschäftigen eine breite Mischung aus hochexponiertem medizinischem Fachpersonal (Diagnostik, Dokumentation) und wenig exponiertem Pflegepersonal (Grundpflege, körperliche Versorgung).",
    "86.2": "Arzt- und Zahnarztpraxen kombinieren KI-affine Diagnostik mit manueller Behandlung. Anamnese-Software und Röntgenauswertung werden KI-gestützt; Behandlungskontakt bleibt menschlich.",
    "86.9": "Sonstiges Gesundheitswesen (Physio, Ergo, Logopädie, Heilpraktik) ist primär körperlich-präsenzbasiert. KI unterstützt Dokumentation und Befundauswertung, ersetzt aber nicht den Behandlungskontakt.",
    # Heime
    "87":   "Heime beschäftigen überwiegend Pflegehilfskräfte und Fachkräfte in der Grundpflege. Körperliche Präsenz ist Kernkompetenz; Dienstplanung und Pflegedokumentation sind KI-zugänglich.",
    "87.1": "Pflegeheime sind stark durch körperliche Grundpflege und Begleitung geprägt. Digitale Pflegedokumentation und Medikamentenmanagement sind KI-affin; Pflege selbst bleibt menschlich.",
    "87.2": "Einrichtungen für Menschen mit psychischen Behinderungen verbinden therapeutische Beziehungsarbeit mit Alltagsbegleitung. KI kann Dokumentation und Therapieplanung unterstützen.",
    "87.3": "Alten- und Pflegeheime: Grundpflege und soziale Begleitung älterer Menschen sind kaum automatisierbar. Dienstplanung, Essensbestellung und Dokumentation sind KI-zugänglich.",
    # Sozialwesen
    "88":   "Das Sozialwesen ohne Unterkunft umfasst Beratung, ambulante Hilfen und Gemeinwesenprojekte. KI kann Fallverwaltung und Berichtswesen übernehmen; direkte Beziehungsarbeit bleibt menschlich.",
    "88.1": "Ambulante Betreuung älterer und behinderter Menschen erfordert regelmäßige körperliche Präsenz und persönliche Beziehungspflege. KI-Unterstützung bei Routinedokumentation möglich.",
    "88.9": "Sonstiges Sozialwesen (Jugendarbeit, Schuldnerberatung, Suchtberatung) verbindet Fachberatung mit Gemeinwesenarbeit. Beratungsdokumentation und Antragsbearbeitung sind KI-affin.",
    # Gesamt
    "Q":    "Der gesamte Gesundheits- und Sozialbereich ist eine Mischung aus wissensintensiver Arbeit und körperlicher Dienstleistung. KI verändert Dokumentation, Diagnostik und Verwaltung erheblich, während direkte Patientenversorgung menschliche Präsenz erfordert.",
}


def load_scores() -> dict[str, dict]:
    if not BLS_SCORES_PATH.exists():
        print(f"WARN: {BLS_SCORES_PATH} nicht gefunden — AI-Scores fehlen")
        return {}
    with open(BLS_SCORES_PATH) as f:
        raw = json.load(f)
    return {item["slug"]: item for item in raw}


def latest_year_data(df: pd.DataFrame) -> pd.DataFrame:
    """Gibt für jeden Code die Zeile des neuesten Jahres zurück."""
    if df.empty:
        return df
    return df.sort_values("year").groupby("code").last().reset_index()


def growth_pct(df: pd.DataFrame, code: str) -> float | None:
    """Berechnet prozentuale SVB-Veränderung vom frühesten zum neuesten Jahr."""
    if df.empty or "code" not in df.columns:
        return None
    rows = df[df["code"] == code].sort_values("year")
    rows = rows.dropna(subset=["svb_gesamt"])
    if len(rows) < 2:
        return None
    v_start = rows.iloc[0]["svb_gesamt"]
    v_end   = rows.iloc[-1]["svb_gesamt"]
    if v_start == 0:
        return None
    return round((v_end - v_start) / v_start * 100, 1)


def cagr(df: pd.DataFrame, code: str) -> float | None:
    """Berechnet CAGR (% p.a.) vom frühesten zum neuesten Jahr."""
    if df.empty or "code" not in df.columns:
        return None
    rows = df[df["code"] == code].sort_values("year").dropna(subset=["svb_gesamt"])
    if len(rows) < 2:
        return None
    v0, v1 = rows.iloc[0]["svb_gesamt"], rows.iloc[-1]["svb_gesamt"]
    n = rows.iloc[-1]["year"] - rows.iloc[0]["year"]
    if v0 <= 0 or n <= 0:
        return None
    return round((math.pow(v1 / v0, 1 / n) - 1) * 100, 2)


def frauenanteil(row: pd.Series) -> float | None:
    if pd.isna(row.get("svb_gesamt")) or row["svb_gesamt"] == 0:
        return None
    if pd.isna(row.get("svb_frauen")):
        return None
    return round(row["svb_frauen"] / row["svb_gesamt"], 4)


def teilzeitanteil(row: pd.Series) -> float | None:
    if pd.isna(row.get("svb_gesamt")) or row["svb_gesamt"] == 0:
        return None
    if pd.isna(row.get("svb_teilzeit")):
        return None
    return round(row["svb_teilzeit"] / row["svb_gesamt"], 4)


def geringfuegigenanteil(row: pd.Series) -> float | None:
    svb = row.get("svb_gesamt", float("nan"))
    gb  = row.get("gb_gesamt",  float("nan"))
    if pd.isna(svb) or pd.isna(gb) or (svb + gb) == 0:
        return None
    return round(gb / (svb + gb), 4)


def build_nodes(
    df: pd.DataFrame,
    code_label_map: dict[str, str],
    bls_map: dict[str, str],
    rationale_map: dict[str, str],
    scores: dict[str, dict],
    category: str,
) -> list[dict]:
    latest = latest_year_data(df)
    has_data = not latest.empty and "code" in latest.columns
    nodes = []

    for code, label in code_label_map.items():
        row_matches = latest[latest["code"] == code] if has_data else pd.DataFrame()
        if row_matches.empty:
            row = pd.Series(dtype=object)
        else:
            row = row_matches.iloc[0]

        bls_slug = bls_map.get(code)
        score_data = scores.get(bls_slug, {}) if bls_slug else {}

        node = {
            "id":       code,
            "label":    label,
            "category": category,
            # Beschäftigungszahlen
            "svb":      int(row["svb_gesamt"]) if not pd.isna(row.get("svb_gesamt", float("nan"))) else None,
            "svb_year": int(row["year"])        if not pd.isna(row.get("year", float("nan"))) else None,
            # Anteile
            "anteil_frauen":      frauenanteil(row),
            "anteil_teilzeit":    teilzeitanteil(row),
            "anteil_geringfuegig": geringfuegigenanteil(row),
            # Wachstum
            "wachstum_gesamt_pct": growth_pct(df, code),
            "cagr_pct":            cagr(df, code),
            # AI-Exposure (von BLS-Mapping)
            "exposure":            score_data.get("exposure"),
            "exposure_bls_title":  score_data.get("title"),
            "exposure_rationale":  rationale_map.get(code) or score_data.get("rationale"),
        }
        nodes.append(node)

    return nodes


def build_timeseries(df: pd.DataFrame, code_label_map: dict[str, str]) -> list[dict]:
    """Baut Zeitreihe pro Code für den Jahr-Slider."""
    if df.empty or "code" not in df.columns:
        return []
    series = []
    for code in code_label_map:
        rows = df[df["code"] == code].sort_values("year").dropna(subset=["svb_gesamt"])
        if rows.empty:
            continue
        series.append({
            "id":   code,
            "data": [{"year": int(r["year"]), "svb": int(r["svb_gesamt"])} for _, r in rows.iterrows()],
        })
    return series


def main():
    scores = load_scores()

    # KldB laden
    kldb_path = PROC_DIR / "kldb_blk.csv"
    kldb_df   = pd.read_csv(kldb_path, dtype={"code": str}) if kldb_path.exists() else pd.DataFrame()
    if kldb_df.empty:
        print(f"WARN: {kldb_path} fehlt oder leer — führe erst parse_ba.py aus")

    # WZ laden
    wz_path = PROC_DIR / "wz_blk.csv"
    wz_df   = pd.read_csv(wz_path, dtype={"code": str}) if wz_path.exists() else pd.DataFrame()
    if wz_df.empty:
        print(f"WARN: {wz_path} fehlt oder leer — führe erst parse_ba.py aus")

    kldb_nodes = build_nodes(kldb_df, KLDB_LABELS, KLDB_BLS_MAP, KLDB_RATIONALE, scores, "kldb")
    wz_nodes   = build_nodes(wz_df,   WZ_LABELS,   WZ_BLS_MAP,   WZ_RATIONALE,   scores, "wz")

    kldb_series = build_timeseries(kldb_df, KLDB_LABELS)
    wz_series   = build_timeseries(wz_df,   WZ_LABELS)

    all_years = sorted({
        r["year"] for df in [kldb_df, wz_df]
        if not df.empty
        for r in df.to_dict("records")
        if not pd.isna(r.get("year"))
    })

    output = {
        "nodes":       kldb_nodes + wz_nodes,
        "timeseries":  kldb_series + wz_series,
        "years":       [int(y) for y in all_years],
        "meta": {
            "source":    "Bundesagentur für Arbeit — Beschäftigungsstatistik",
            "kldb":      "KldB 2010, Berufshauptgruppen 81–88 (Soziales, Bildung, Gesundheit)",
            "wz":        "WZ 2008, Abteilungen 85–88 (Bildung, Gesundheit, Sozialwesen)",
            "stichtag":  "30. Juni (jeweils)",
            "ai_scores": "Adaptiert von BLS Occupational Outlook Handbook (via LLM)",
        },
    }

    dest = SITE_DIR / "data.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_svb = sum(n["svb"] or 0 for n in kldb_nodes if n["category"] == "kldb" and len(n["id"]) == 3)
    print(f"Geschrieben: {dest}")
    print(f"  {len(kldb_nodes)} KldB-Nodes, {len(wz_nodes)} WZ-Nodes")
    print(f"  SVB 3-Steller gesamt: {total_svb:,}")
    print(f"  Jahre: {all_years or '(keine Daten)'}")


if __name__ == "__main__":
    main()
