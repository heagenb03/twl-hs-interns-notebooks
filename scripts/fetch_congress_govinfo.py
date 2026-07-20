# scripts/fetch_congress_govinfo.py
"""Network stage: pull Senate CREC granules from GovInfo's keyless bulk paths.

One JSON file per CREC day under data/_raw/congress_govinfo/{year}/. Days
already on disk are skipped, so an interrupted run resumes by re-invoking.

No API key. The rate-limited api.govinfo.gov JSON API is deliberately avoided:
/granules/{id}/summary is rendered from the daily MODS file, and MODS is served
unauthenticated at one request per DAY instead of one per granule.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

from twl_common import (
    CONGRESS_RAW_GOVINFO,
    GOVINFO_HTML_URL,
    GOVINFO_MODS_URL,
    GOVINFO_SITEMAP_URL,
    USER_AGENT,
)

MODS_NS = "{http://www.loc.gov/mods/v3}"
HEADERS = {"User-Agent": USER_AGENT}
SLEEP_SECONDS = 0.1
MAX_RETRIES = 5


def get(url: str) -> requests.Response:
    """GET with exponential backoff. .gov bulk paths throttle sustained pulls."""
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        response = requests.get(url, headers=HEADERS, timeout=180)
        if response.status_code == 200:
            time.sleep(SLEEP_SECONDS)
            return response
        if response.status_code in (429, 500, 502, 503, 504):
            print(f"  {response.status_code} on {url} - retry in {delay:.0f}s")
            time.sleep(delay)
            delay *= 2
            continue
        response.raise_for_status()
    raise RuntimeError(f"giving up after {MAX_RETRIES} attempts: {url}")


def session_days(year: int) -> list[str]:
    """Every CREC package id published in `year`, from the sitemap."""
    text = get(GOVINFO_SITEMAP_URL.format(year=year)).text
    return sorted(set(re.findall(r"CREC-\d{4}-\d{2}-\d{2}", text)))


def _text(node, path: str) -> str:
    el = node.find(path)
    return (el.text or "").strip() if el is not None and el.text else ""


def senate_granules(pkg: str) -> list[dict]:
    """Senate granules for one CREC day, with their congMember metadata."""
    root = ET.fromstring(get(GOVINFO_MODS_URL.format(pkg=pkg)).content)
    out: list[dict] = []
    for part in root.findall(f"{MODS_NS}relatedItem[@type='constituent']"):
        if _text(part, f"{MODS_NS}extension/{MODS_NS}granuleClass") != "SENATE":
            continue
        members = []
        for m in part.findall(f"{MODS_NS}extension/{MODS_NS}congMember"):
            lnf = ""
            for name in m.findall(f"{MODS_NS}name"):
                if name.get("type") == "authority-lnf":
                    lnf = (name.text or "").strip()
            members.append(
                {
                    "lnf": lnf,
                    "bio": m.get("bioGuideId", ""),
                    "role": m.get("role", ""),
                    "party": m.get("party", ""),
                    "state": m.get("state", ""),
                }
            )
        out.append(
            {
                "granule_id": _text(part, f"{MODS_NS}extension/{MODS_NS}accessId"),
                "title": _text(part, f"{MODS_NS}titleInfo/{MODS_NS}title"),
                "members": members,
            }
        )
    return out


def fetch_day(pkg: str, out_path: Path) -> None:
    granules = senate_granules(pkg)
    for granule in granules:
        url = GOVINFO_HTML_URL.format(pkg=pkg, granule=granule["granule_id"])
        granule["text"] = re.sub(r"<[^>]+>", "", get(url).text)
    out_path.write_text(
        json.dumps({"package": pkg, "granules": granules}, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=1994)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--refresh", action="store_true", help="re-download cached days")
    args = parser.parse_args()

    for year in range(args.start_year, args.end_year + 1):
        year_dir = CONGRESS_RAW_GOVINFO / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        days = session_days(year)
        print(f"{year}: {len(days)} CREC days")
        for i, pkg in enumerate(days, 1):
            out_path = year_dir / f"{pkg}.json"
            if out_path.exists() and not args.refresh:
                continue
            fetch_day(pkg, out_path)
            if i % 25 == 0:
                print(f"  {year}: {i}/{len(days)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
