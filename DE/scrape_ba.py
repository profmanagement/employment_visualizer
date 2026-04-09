"""
Lädt BA-Beschäftigungsstatistik-Excel per Playwright herunter.

Navigiert statistik.arbeitsagentur.de, akzeptiert Cookies und harvested
alle xlsx-Download-Links für Beschäftigung nach KldB und WZ.

Dateien landen in DE/data/raw/{kategorie}/.

Verwendung:
    uv run python DE/scrape_ba.py
    # oder nach manuellem pip install playwright && playwright install chromium:
    python DE/scrape_ba.py
"""

import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright

RAW_DIR = Path(__file__).parent / "data" / "raw"

# Einstiegspunkte: Navigationsseiten der BA-Statistik
NAV_URLS = [
    # Beschäftigung – Tabellenübersicht
    "https://statistik.arbeitsagentur.de/DE/Navigation/Statistiken/Fachstatistiken/Beschaeftigung/Beschaeftigung-Nav.html",
    # Direktlink Tabellen (alternativer Pfad)
    "https://statistik.arbeitsagentur.de/SiteGlobals/Forms/Suche/Einzelheftsuche_Formular.html?nn=1523064&topic_f=beschaeftigung-sozbe",
]

# Welche Datei-Kürzel uns interessieren
TARGET_PATTERNS = [
    r"sozbe-kldb-blk",
    r"sozbe-kldb-kreis",
    r"sozbe-wz-blk",
    r"sozbe-wz-kreis",
]


def category_from_url(url: str) -> str | None:
    for pat in TARGET_PATTERNS:
        m = re.search(pat, url)
        if m:
            return m.group()
    return None


async def accept_cookies(page) -> None:
    for selector in [
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Alle zulassen')",
        "button:has-text('Akzeptieren')",
        "button:has-text('Accept all')",
        "#cookiebanner-accept-all",
        ".cookie-accept",
    ]:
        try:
            await page.click(selector, timeout=3000)
            print("  Cookie-Banner akzeptiert")
            await page.wait_for_timeout(500)
            return
        except Exception:
            pass


async def harvest_xlsx_links(page, url: str) -> list[str]:
    """Lädt eine Seite und sammelt alle .xlsx-Links."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await accept_cookies(page)
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception as e:
        print(f"  WARN beim Laden von {url}: {e}")

    links = await page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => e.href).filter(h => h.endsWith('.xlsx') || h.includes('.xlsx'))"
    )
    return links


async def follow_sublinks_and_harvest(page, start_url: str) -> list[str]:
    """
    Lädt eine Navigationsseite, findet Links zu Unterseiten mit
    'Beschäftigung' / 'sozbe' im Pfad und sammelt .xlsx-Links dort.
    """
    all_xlsx: list[str] = []

    await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
    await accept_cookies(page)
    await page.wait_for_load_state("networkidle", timeout=10000)

    # Direkte xlsx-Links auf der Einstiegsseite
    direct = await harvest_xlsx_links(page, start_url)
    all_xlsx.extend(direct)

    # Sub-Links, die nach Beschäftigungs-Tabellen aussehen
    sub_links = await page.eval_on_selector_all(
        "a[href]",
        """els => els
            .map(e => e.href)
            .filter(h =>
                (h.includes('sozbe') || h.includes('Beschaeftigung')) &&
                !h.endsWith('.xlsx') &&
                h.startsWith('http')
            )
        """
    )
    # Deduplizieren und auf max. 20 begrenzen, um Timeouts zu vermeiden
    sub_links = list(dict.fromkeys(sub_links))[:20]

    for sub in sub_links:
        print(f"  Unterseite: {sub}")
        links = await harvest_xlsx_links(page, sub)
        all_xlsx.extend(links)

    return all_xlsx


async def download_file(page, url: str, dest: Path) -> bool:
    """Lädt eine Datei über den Playwright-Request-Kontext herunter."""
    try:
        response = await page.request.get(url, timeout=60000)
        if response.status != 200:
            print(f"  HTTP {response.status} für {url}")
            return False
        dest.write_bytes(await response.body())
        return True
    except Exception as e:
        print(f"  Fehler beim Download von {url}: {e}")
        return False


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        print("Sammle xlsx-Links von BA-Statistik...")
        all_links: list[str] = []
        for nav_url in NAV_URLS:
            print(f"Navigiere: {nav_url}")
            links = await follow_sublinks_and_harvest(page, nav_url)
            all_links.extend(links)

        # Deduplizieren
        all_links = list(dict.fromkeys(all_links))
        print(f"\nGefundene xlsx-Links gesamt: {len(all_links)}")

        # Nur relevante filtern
        relevant = [(url, category_from_url(url)) for url in all_links if category_from_url(url)]
        print(f"Davon relevant (KldB/WZ): {len(relevant)}")

        if not relevant:
            print(
                "\nKeine passenden Links gefunden. Mögliche Ursachen:\n"
                "  - BA-Portal hat die URL-Struktur geändert\n"
                "  - Cookie/Session-Sperre aktiv\n"
                "\nFallback: Dateien manuell herunterladen und in\n"
                "  DE/data/raw/{kategorie}/  ablegen.\n"
                "Kategorien: sozbe-kldb-blk, sozbe-kldb-kreis, sozbe-wz-blk, sozbe-wz-kreis"
            )
            await browser.close()
            return

        downloaded, skipped, failed = 0, 0, 0
        for url, category in relevant:
            filename = url.split("/")[-1].split("?")[0]
            dest_dir = RAW_DIR / category
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / filename

            if dest.exists():
                print(f"  Bereits vorhanden: {filename}")
                skipped += 1
                continue

            print(f"  Download [{category}]: {filename}")
            ok = await download_file(page, url, dest)
            if ok:
                print(f"    → {dest} ({dest.stat().st_size // 1024} KB)")
                downloaded += 1
            else:
                failed += 1

        await browser.close()

    print(f"\nFertig: {downloaded} neu, {skipped} übersprungen, {failed} fehlgeschlagen")


if __name__ == "__main__":
    asyncio.run(main())
