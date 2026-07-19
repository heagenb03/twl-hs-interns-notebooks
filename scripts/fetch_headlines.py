"""Network stage for the real-headlines dataset.

Queries the GDELT DOC 2.0 API once per (event x outlet) and caches raw results.
Run once; build_headlines.py consumes the cache offline.

    python scripts/fetch_headlines.py [--refresh]

GDELT notes, all verified 2026-07-19:
  * Coverage starts 2017-01-01. The launch blog's "last 3 months" limit is
    stale and no longer enforced.
  * No API key required.
  * Max 250 records per query; wide ranges silently TRUNCATE rather than error,
    which is why we query per event-window per outlet instead of in bulk.
  * Rate limit is ~1 request / 5 seconds, undocumented but enforced. Exceeding
    it returns PLAIN TEXT, not JSON, so .json() raises. Hence SLEEP_SECONDS.
  * `domain:` matches SUBDOMAINS -- domain:xinhuanet.com also returns
    spanish.xinhuanet.com and provincial sites. We use `domainis:` for exact
    match so the four classes stay clean.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import requests

from twl_common import RAW_DIR

API = "https://api.gdeltproject.org/api/v2/doc/doc"
RAW_PATH = RAW_DIR / "headlines_gdelt.json"
SLEEP_SECONDS = 6.0
MAX_RECORDS = 250

# Order matters: it becomes CSV row order, and the notebook relies on
# unique()[2] == "Phase One deal".
EVENTS: tuple[tuple[str, str, str], ...] = (
    ("2018 tariff announcement", "2018-03-22", "2018-03-29"),
    ("Huawei CFO arrest", "2018-12-05", "2018-12-12"),
    ("Phase One deal", "2020-01-15", "2020-01-22"),
    ("Hong Kong security law", "2020-06-30", "2020-07-07"),
    ("TikTok ban push", "2020-08-06", "2020-08-13"),
    ("Spy balloon", "2023-02-04", "2023-02-11"),
)

OUTLET_DOMAINS: dict[str, str] = {
    "NYT": "nytimes.com",
    "WSJ": "wsj.com",
    "Fox": "foxnews.com",
    "Xinhua": "xinhuanet.com",
}

QUERY_TERMS = "(china OR chinese)"


def _stamp(date: str, end_of_day: bool = False) -> str:
    """GDELT wants YYYYMMDDHHMMSS."""
    compact = date.replace("-", "")
    return compact + ("235959" if end_of_day else "000000")


def fetch_one(outlet: str, start: str, end: str) -> list[dict]:
    """Fetch articles for one outlet in one window. Returns [] on no results."""
    params = {
        "query": f"{QUERY_TERMS} domainis:{OUTLET_DOMAINS[outlet]} sourcelang:english",
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_RECORDS,
        "startdatetime": _stamp(start),
        "enddatetime": _stamp(end, end_of_day=True),
        "sort": "datedesc",
    }
    resp = requests.get(API, params=params, timeout=60)
    resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        return []
    if not text.startswith("{"):
        # Rate limit or error responses come back as plain text.
        raise RuntimeError(f"GDELT returned non-JSON for {outlet} {start}: {text[:200]}")

    articles = resp.json().get("articles", [])
    return [
        {
            "title": a.get("title", "").strip(),
            "url": a.get("url", ""),
            "domain": a.get("domain", ""),
            "seendate": a.get("seendate", ""),
        }
        for a in articles
    ]


def fetch_all() -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = {}
    for event, start, end in EVENTS:
        out[event] = {}
        for outlet in OUTLET_DOMAINS:
            print(f"  {event} / {outlet} ...", end="", flush=True)
            try:
                articles = fetch_one(outlet, start, end)
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f" ERROR: {exc}")
                articles = []
            else:
                print(f" {len(articles)}")
            out[event][outlet] = articles
            time.sleep(SLEEP_SECONDS)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="re-download")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_PATH.exists() and not args.refresh:
        print(f"cache exists: {RAW_PATH} (use --refresh to re-download)")
        return 0

    print(f"fetching {len(EVENTS)} events x {len(OUTLET_DOMAINS)} outlets "
          f"({len(EVENTS) * len(OUTLET_DOMAINS)} requests, "
          f"~{len(EVENTS) * len(OUTLET_DOMAINS) * SLEEP_SECONDS / 60:.0f} min)")
    data = fetch_all()
    RAW_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nwrote {RAW_PATH}")
    print("\ncounts per event x outlet:")
    for event in data:
        counts = ", ".join(f"{o} {len(v)}" for o, v in data[event].items())
        print(f"  {event}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
