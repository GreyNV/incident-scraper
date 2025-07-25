import argparse
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import List, Dict, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Playwright is used for the Ramapo property search
try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - playwright may not be installed
    sync_playwright = None

TOWNS = ["Clarkstown", "Orangetown", "Ramapo", "Stony Point"]

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@dataclass
class ScrapeResult:
    address: str
    owner_name: Optional[str]
    source: str
    status: str


def load_incident_addresses(path: str) -> List[str]:
    """Load incident addresses from a JSON or CSV file."""
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [item.get("address", "") for item in data]
    elif path.lower().endswith(".csv"):
        df = pd.read_csv(path)
        return df.get("address", pd.Series()).dropna().tolist()
    else:
        raise ValueError(f"Unsupported file type: {path}")


def detect_town(address: str) -> Optional[str]:
    """Return the supported town name found in the address string."""
    for town in TOWNS:
        if town.lower() in address.lower():
            return town
    return None


def group_addresses_by_town(addresses: List[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {town: [] for town in TOWNS}
    grouped["Unknown"] = []
    for addr in addresses:
        town = detect_town(addr)
        if town:
            grouped[town].append(addr)
        else:
            grouped["Unknown"].append(addr)
    return grouped


def requests_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session


def parse_bas_response(html: str) -> Optional[str]:
    """Parse owner name from BAS portal HTML."""
    soup = BeautifulSoup(html, "html.parser")
    label = soup.find(text=re.compile(r"Owner Name", re.I))
    if label and label.parent:
        td = label.find_parent("tr").find_all("td")
        if len(td) >= 2:
            return td[1].get_text(strip=True)
    return None


def search_bas_portal(address: str, url: str, source: str) -> ScrapeResult:
    """Submit an address to a BAS tax portal and return the owner name."""
    number_match = re.match(r"(\d+)\s+(.*)", address)
    number = number_match.group(1) if number_match else ""
    street = number_match.group(2) if number_match else address
    payload = {"house_number": number, "street": street}
    session = requests_session()
    try:
        resp = session.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        owner = parse_bas_response(resp.text)
        status = "success" if owner else "not found"
    except Exception as exc:
        logger.error("%s: error fetching %s -> %s", source, address, exc)
        owner = None
        status = "error"
    return ScrapeResult(address=address, owner_name=owner, source=source, status=status)


def scrape_clarkstown(addresses: List[str]) -> List[ScrapeResult]:
    url = "https://www.townofclarkstown.org/cn/TaxSearch/index.cfm"
    results = []
    for addr in addresses:
        results.append(search_bas_portal(addr, url, "Clarkstown Tax Search"))
    return results


def scrape_orangetown(addresses: List[str]) -> List[ScrapeResult]:
    url = "https://www.orangetown.com/departments/receiver-of-taxes/tax-bill-search/"
    results = []
    for addr in addresses:
        results.append(search_bas_portal(addr, url, "Orangetown Tax Search"))
    return results


def scrape_ramapo(addresses: List[str]) -> List[ScrapeResult]:
    if sync_playwright is None:
        logger.error("Playwright is not installed; cannot scrape Ramapo")
        return [ScrapeResult(addr, None, "Ramapo Property Search", "error") for addr in addresses]

    results: List[ScrapeResult] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:
            logger.error("Unable to launch Playwright browser: %s", exc)
            return [ScrapeResult(addr, None, "Ramapo Property Search", "error") for addr in addresses]
        page = browser.new_page()
        for addr in addresses:
            number_match = re.match(r"(\d+)\s+(.*)", addr)
            number = number_match.group(1) if number_match else ""
            street = number_match.group(2) if number_match else addr
            try:
                page.goto("https://ramapo.prosgar.com/")
                page.fill("input[name=houseNumber]", number)
                page.fill("input[name=streetName]", street)
                page.click("text=Search")
                page.wait_for_selector("text=Owner", timeout=5000)
                owner = page.text_content("xpath=//td[contains(text(), 'Owner')]/following-sibling::td")
                status = "success" if owner else "not found"
            except Exception as exc:
                logger.error("Ramapo search error for %s: %s", addr, exc)
                owner = None
                status = "error"
            results.append(ScrapeResult(addr, owner, "Ramapo Property Search", status))
            time.sleep(1)
        browser.close()
    return results


def scrape_stony_point(addresses: List[str]) -> List[ScrapeResult]:
    # Attempt to download and parse the latest assessment roll
    url = "https://www.townofstonypoint.org/files/assessment_roll.xlsx"
    local_file = "stony_point_roll.xlsx"
    try:
        if not os.path.exists(local_file):
            logger.info("Downloading Stony Point assessment roll")
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with open(local_file, "wb") as f:
                f.write(resp.content)
        df = pd.read_excel(local_file)
    except Exception as exc:
        logger.error("Unable to download or parse Stony Point roll: %s", exc)
        return [ScrapeResult(addr, None, "Stony Point Assessment Roll", "error") for addr in addresses]

    results: List[ScrapeResult] = []
    for addr in addresses:
        owner = None
        try:
            match = df[df['Address'].str.contains(addr, case=False, na=False)]
            if not match.empty:
                owner = match.iloc[0]['Owner']
        except Exception as exc:
            logger.error("Error searching Stony Point roll for %s: %s", addr, exc)
        status = "success" if owner else "not found"
        results.append(ScrapeResult(addr, owner, "Stony Point Assessment Roll", status))
    return results


SCRAPER_MAP = {
    "Clarkstown": scrape_clarkstown,
    "Orangetown": scrape_orangetown,
    "Ramapo": scrape_ramapo,
    "Stony Point": scrape_stony_point,
}


def save_results(results: List[ScrapeResult], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([r.__dict__ for r in results], f, indent=2)
    logger.info("Wrote %d results to %s", len(results), path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape property owner names for incident addresses")
    parser.add_argument("input_file", help="CSV or JSON file with incidents")
    parser.add_argument("--output", default="scraped_owner_names.json", help="Output JSON file")
    args = parser.parse_args()

    addresses = load_incident_addresses(args.input_file)
    logger.info("Loaded %d addresses", len(addresses))

    groups = group_addresses_by_town(addresses)
    all_results: List[ScrapeResult] = []
    for town, addr_list in groups.items():
        if not addr_list or town == "Unknown":
            continue
        scraper = SCRAPER_MAP.get(town)
        if scraper:
            logger.info("Processing %d addresses for %s", len(addr_list), town)
            results = scraper(addr_list)
            for r in results:
                logger.info("%s -> %s (%s)", r.address, r.owner_name, r.status)
            all_results.extend(results)

    save_results(all_results, args.output)


if __name__ == "__main__":
    main()
