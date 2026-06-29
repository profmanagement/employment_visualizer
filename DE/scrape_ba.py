"""
Lädt aktuelle BA-Beschäftigungsstatistik-Excel-Dateien herunter.

Die BA-Einzelheftsuche liefert KldB/WZ-Zeitreihen inzwischen nicht mehr über
den alten Sammelfilter ``topic_f=beschaeftigung-sozbe``, sondern über
spezifische Themenfilter. Dieses Skript lädt gezielt die Deutschland-Dateien,
die von ``parse_ba.py`` und der Visualisierung verwendet werden.

Dateien landen in DE/data/raw/{kategorie}/.

Verwendung:
    uv run python DE/scrape_ba.py
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent / "data" / "raw"
BASE_URL = "https://statistik.arbeitsagentur.de/"
SEARCH_URL = urljoin(BASE_URL, "SiteGlobals/Forms/Suche/Einzelheftsuche_Formular.html")


@dataclass(frozen=True)
class Dataset:
    topic: str
    category: str
    filename_prefix: str


DATASETS = [
    Dataset(
        topic="beschaeftigung-sozbe-kldb2010-zeitreihe",
        category="sozbe-kldb-blk",
        filename_prefix="kldb2010-zeitreihe-d-0-xlsx",
    ),
    Dataset(
        topic="beschaeftigung-sozbe-wz2008-zeitreihe",
        category="sozbe-wz-blk",
        filename_prefix="wz2008-zeitreihe-d-0-xlsx",
    ),
]


def filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    return name.split(";")[0]


def is_target_link(href: str, dataset: Dataset) -> bool:
    filename = filename_from_url(href)
    return filename.startswith(dataset.filename_prefix) and filename.endswith(".xlsx")


def find_dataset_links(client: httpx.Client, dataset: Dataset) -> list[str]:
    params = {"nn": "1523064", "topic_f": dataset.topic}
    response = client.get(SEARCH_URL, params=params)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = unescape(anchor["href"])
        if ".xlsx" not in href:
            continue
        url = urljoin(BASE_URL, href)
        if is_target_link(url, dataset):
            links.append(url)

    return list(dict.fromkeys(links))


def download_file(client: httpx.Client, url: str, dest: Path) -> bool:
    try:
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                print(f"  HTTP {response.status_code} für {url}")
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"  Fehler beim Download von {url}: {e}")
        return False


def main() -> None:
    print("Sammle aktuelle BA-Zeitreihen-Links...")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    downloaded, skipped, failed = 0, 0, 0
    with httpx.Client(headers=headers, follow_redirects=True, timeout=60.0) as client:
        for dataset in DATASETS:
            print(f"\nSuche [{dataset.category}]: {dataset.topic}")
            try:
                links = find_dataset_links(client, dataset)
            except Exception as e:
                print(f"  Fehler beim Laden der BA-Suche: {e}")
                failed += 1
                continue

            if not links:
                print("  Keine passende Deutschland-XLSX gefunden")
                failed += 1
                continue

            for url in links:
                filename = filename_from_url(url)
                dest = RAW_DIR / dataset.category / filename
                if dest.exists():
                    print(f"  Bereits vorhanden: {filename}")
                    skipped += 1
                    continue

                print(f"  Download: {filename}")
                if download_file(client, url, dest):
                    print(f"    -> {dest} ({dest.stat().st_size // 1024} KB)")
                    downloaded += 1
                else:
                    failed += 1

    print(f"\nFertig: {downloaded} neu, {skipped} übersprungen, {failed} fehlgeschlagen")


if __name__ == "__main__":
    main()
