"""Network stage for the real-headlines dataset.

Queries the GDELT DOC 2.0 API once per (event x outlet) and caches raw results.
Run once; build_headlines.py consumes the cache offline.

    python scripts/fetch_headlines.py [--refresh]

Resumable by default: re-runs only fetch cells that are missing or previously
errored, merging into the existing cache. Pass --refresh to re-fetch every
cell from scratch. Cache is written incrementally (after each event), so an
interrupted run never loses completed work.

GDELT notes, all verified 2026-07-19:
  * Coverage starts 2017-01-01. The launch blog's "last 3 months" limit is
    stale and no longer enforced.
  * No API key required.
  * Max 250 records per query; wide ranges silently TRUNCATE rather than error,
    which is why we query per event-window per outlet instead of in bulk.
  * Rate limit is much stricter than the ~1 req/5s the launch docs imply:
    a probe sent 8s after a prior request still came back 429. SLEEP_SECONDS
    is 15.0, and fetch_one additionally retries on 429 (and on a plain-text
    "throttled" body, which is also a 429-equivalent response) with
    exponential backoff -- 20s, 40s, 80s, 160s -- up to 5 attempts total
    before giving up and raising. A raised exception is recorded in the
    status sidecar as an error, never silently coerced to an empty result.
  * `domain:` matches SUBDOMAINS -- domain:xinhuanet.com also returns
    spanish.xinhuanet.com and provincial sites. We use `domainis:` for exact
    match so the four classes stay clean.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from twl_common import RAW_DIR

API = "https://api.gdeltproject.org/api/v2/doc/doc"
RAW_PATH = RAW_DIR / "headlines_gdelt.json"
STATUS_PATH = RAW_DIR / "headlines_gdelt_status.json"
SLEEP_SECONDS = 15.0
MAX_RECORDS = 250

# On a 429 (or a non-JSON "throttled" body, which is also a throttle
# response), retry with this exponential backoff schedule. Combined with the
# initial attempt, this is a maximum of 5 attempts per cell.
RETRY_DELAYS: tuple[float, ...] = (20.0, 40.0, 80.0, 160.0)
MAX_ATTEMPTS: int = 5

assert len(RETRY_DELAYS) == MAX_ATTEMPTS - 1, (
    "RETRY_DELAYS must have exactly MAX_ATTEMPTS - 1 entries (one delay between "
    "each pair of attempts); raising MAX_ATTEMPTS without extending RETRY_DELAYS "
    "would IndexError at runtime in fetch_one"
)

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


class _Throttled(Exception):
    """Internal signal: GDELT returned a 429, or a non-JSON throttle body."""


def _attempt_fetch(outlet: str, start: str, params: dict) -> list[dict]:
    resp = requests.get(API, params=params, timeout=60)
    if resp.status_code == 429:
        raise _Throttled(f"429 Too Many Requests for {outlet} {start}")
    resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        return []
    if not text.startswith("{"):
        # Rate limit / throttle responses come back as plain text.
        raise _Throttled(f"non-JSON (throttle) body for {outlet} {start}: {text[:200]}")

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


def fetch_one(outlet: str, start: str, end: str) -> list[dict]:
    """Fetch articles for one outlet in one window.

    Returns [] only for a genuine, successfully-parsed empty result. Retries
    on HTTP 429 or a non-JSON (plain-text) throttle response with exponential
    backoff (20s, 40s, 80s, 160s), for up to 5 attempts total. Raises on final
    failure -- callers must not treat that as an empty result.
    """
    params = {
        "query": f"{QUERY_TERMS} domainis:{OUTLET_DOMAINS[outlet]} sourcelang:english",
        "mode": "artlist",
        "format": "json",
        "maxrecords": MAX_RECORDS,
        "startdatetime": _stamp(start),
        "enddatetime": _stamp(end, end_of_day=True),
        "sort": "datedesc",
    }
    for attempt in range(MAX_ATTEMPTS):
        try:
            return _attempt_fetch(outlet, start, params)
        except _Throttled as exc:
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(RETRY_DELAYS[attempt])
                continue
            raise RuntimeError(str(exc)) from exc
    raise AssertionError("unreachable")  # pragma: no cover


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` without ever leaving a truncated/partial file.

    Writes to a sibling temp file first, then swaps it into place with
    os.replace, which is atomic on both POSIX and Windows. A crash or
    interruption mid-write leaves either the old file (untouched) or the new
    one -- never a half-written file at `path`.
    """
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _write_cache(data: dict, status: dict) -> None:
    # Order is load-bearing: RAW_PATH must be written before STATUS_PATH.
    # Each _atomic_write_text call is individually atomic, but the pair is
    # not transactional -- a crash between the two os.replace calls is
    # possible. If status were written first (or the order were reversed),
    # a crash mid-write during a re-fetch could leave status durably saying
    # "ok" while data still held the OLD, stale value from before this
    # re-fetch. The `outlet in data[event]` skip-check in fetch_all cannot
    # detect that case, because the key exists -- so the stale cell would be
    # trusted forever. Writing data first means the only inconsistent state
    # a crash can leave behind is fresh data with stale/missing status,
    # which just triggers a harmless re-fetch on resume, never a silent
    # trust of stale data.
    _atomic_write_text(RAW_PATH, json.dumps(data, indent=2, ensure_ascii=False))
    _atomic_write_text(STATUS_PATH, json.dumps(status, indent=2, ensure_ascii=False))


def fetch_all(
    data: dict[str, dict[str, list[dict]]],
    status: dict[str, dict[str, str]],
    refresh: bool,
    events: tuple[tuple[str, str, str], ...] = EVENTS,
    outlets: tuple[str, ...] | None = None,
) -> tuple[dict[str, dict[str, list[dict]]], dict[str, dict[str, str]]]:
    """Fetch missing/errored cells, merging into `data`/`status` in place.

    A cell whose status is already "ok" (and refresh is False) is skipped
    entirely -- fetch_one is not called and its cached value is untouched --
    but only if that cached data actually exists. A cell marked "ok" with no
    matching entry in `data` (e.g. from a desynced dual-file write) is not
    trusted and is re-fetched instead, so a broken cache can self-heal on
    the next resume rather than silently skipping forever.

    `status` describes the trustworthiness of the CACHED data, not the
    outcome of the most recent fetch attempt. If an attempt fails but the
    cell already holds previously-fetched articles, that data is still
    trustworthy: `data` is left untouched and `status` is (re)recorded as
    "ok", never downgraded to "error" just because a later resume attempt
    got throttled. Only a cell with no prior data to fall back on gets
    "error: <message>" recorded; it is never overwritten with [].
    """
    if outlets is None:
        outlets = tuple(OUTLET_DOMAINS)

    for event, start, end in events:
        data.setdefault(event, {})
        status.setdefault(event, {})
        for outlet in outlets:
            cell_status = status[event].get(outlet)
            if not refresh and cell_status == "ok" and outlet in data[event]:
                cached_n = len(data[event].get(outlet, []))
                print(f"  {event} / {outlet} ... skip (cached ok, {cached_n})")
                continue

            print(f"  {event} / {outlet} ...", end="", flush=True)
            try:
                articles = fetch_one(outlet, start, end)
            except Exception as exc:  # noqa: BLE001 - report and continue
                if outlet in data[event]:
                    # Cached data from an earlier successful fetch is still
                    # trustworthy -- this attempt's failure does not taint it.
                    kept_n = len(data[event][outlet])
                    print(f" ERROR: {exc} (keeping {kept_n} cached articles, status stays ok)")
                    status[event][outlet] = "ok"
                else:
                    print(f" ERROR: {exc}")
                    status[event][outlet] = f"error: {exc}"
            else:
                print(f" {len(articles)}")
                data[event][outlet] = articles
                status[event][outlet] = "ok"
            time.sleep(SLEEP_SECONDS)
        _write_cache(data, status)
    return data, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-download every cell from scratch (default: resume, re-fetching only missing/errored cells)",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.refresh:
        data: dict[str, dict[str, list[dict]]] = {}
        status: dict[str, dict[str, str]] = {}
    else:
        data = _load_json(RAW_PATH)
        status = _load_json(STATUS_PATH)

    n_total = len(EVENTS) * len(OUTLET_DOMAINS)
    n_cached_ok = sum(
        1
        for event, _, _ in EVENTS
        for outlet in OUTLET_DOMAINS
        if status.get(event, {}).get(outlet) == "ok"
    )
    n_to_fetch = n_total if args.refresh else n_total - n_cached_ok
    print(
        f"fetching {n_to_fetch} of {n_total} cells "
        f"(~{n_to_fetch * SLEEP_SECONDS / 60:.0f}+ min before any retries/backoff)"
    )

    data, status = fetch_all(data, status, args.refresh)

    print(f"\nwrote {RAW_PATH}")
    print(f"wrote {STATUS_PATH}")

    print("\ncounts per event x outlet:")
    for event, _, _ in EVENTS:
        counts = ", ".join(
            f"{outlet} {len(data.get(event, {}).get(outlet, []))}" for outlet in OUTLET_DOMAINS
        )
        print(f"  {event}: {counts}")

    errors = []
    for event, _, _ in EVENTS:
        for outlet in OUTLET_DOMAINS:
            cell_status = status.get(event, {}).get(outlet, "missing")
            if cell_status != "ok":
                errors.append(f"{event} / {outlet}: {cell_status}")

    n_ok = n_total - len(errors)
    print(f"\nstatus summary: {n_ok}/{n_total} cells ok")

    if errors:
        print(
            "\nWARNING: the following cells are still NOT ok -- the cache is "
            "contaminated for them. Do not build downstream data from this run "
            "without re-fetching these cells:"
        )
        for line in errors:
            print(f"  - {line}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
