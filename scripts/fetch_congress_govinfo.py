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

# Fraction of a year's CREC days that may legitimately be phantom packages
# (bare ids the sitemap regex produced that only ever existed under a
# volume/issue suffix) before we assume something worse is happening -- a
# GovInfo outage or a changed URL scheme -- rather than the normal handful
# of suffixed-only days. The only measured real-world rate is 2023: 3/209
# days (~1.4%). 15% is roughly 10x that observed rate: generous enough to
# absorb year-to-year variation in how often GovInfo splits/reissues a
# day's Record, but far below the rate an outage or scheme change would
# produce (every day would fail, i.e. ~100%).
PHANTOM_SKIP_RATE_THRESHOLD = 0.15

# Hard floor on how many days a year's sitemap must yield to be believable.
# No real CREC session year has fewer than 20 days -- the actual figure is
# well over 100 -- so a year below this floor means session_days() itself
# failed: the sitemap URL served an HTML error page and the CREC-id regex
# matched almost nothing. That is the same "outage or scheme change" failure
# mode as a high phantom-skip rate, but it surfaces BEFORE there is any rate
# to compute, which is exactly why it needs its own check. Without it, a
# sitemap outage yields `days == []`, the rate gate divides by nothing, and
# the year passes as a silent no-op.
MIN_DAYS_FOR_SANITY_CHECK = 20


class PhantomPackageError(Exception):
    """A CREC package id has no standalone package -- GovInfo served HTML.

    GovInfo returns HTTP 200 (not 404) for package ids that don't exist on
    their own, so this can't be detected from status code. It happens when
    `session_days()`'s regex strips a volume/issue suffix (e.g.
    CREC-2023-01-03-v168) down to a bare id (CREC-2023-01-03) that was
    never published standalone.
    """


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
    """Senate granules for one CREC day, with their congMember metadata.

    Raises PhantomPackageError if `pkg` has no standalone package on
    GovInfo -- detected two ways, since either can miss: (1) content
    sniffing the response body for an HTML doctype/tag before parsing, and
    (2) catching the ET.ParseError that results if sniffing misses an HTML
    variant that doesn't start with those exact bytes.
    """
    content = get(GOVINFO_MODS_URL.format(pkg=pkg)).content
    sniff = content.lstrip()[:20].lower()
    if sniff.startswith(b"<!doctype html") or sniff.startswith(b"<html"):
        raise PhantomPackageError(pkg)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise PhantomPackageError(pkg) from exc
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
    """Fetch and write one CREC day. Propagates PhantomPackageError as-is
    so callers can distinguish it from other failures."""
    granules = senate_granules(pkg)
    for granule in granules:
        url = GOVINFO_HTML_URL.format(pkg=pkg, granule=granule["granule_id"])
        granule["text"] = re.sub(r"<[^>]+>", "", get(url).text)
    out_path.write_text(
        json.dumps({"package": pkg, "granules": granules}, ensure_ascii=False),
        encoding="utf-8",
    )


def _phantom_marker_path(year_dir: Path, pkg: str) -> Path:
    """Durable marker recording `pkg` as a known phantom package.

    Lives inside data/_raw/congress_govinfo/{year}/, which is gitignored,
    alongside the day JSON files it stands in for. Its purpose is to make a
    resumed run skip a known phantom without re-requesting it.
    """
    return year_dir / f"{pkg}.phantom.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=1994)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--refresh", action="store_true", help="re-download cached days")
    args = parser.parse_args()

    run_skipped: dict[int, list[str]] = {}

    for year in range(args.start_year, args.end_year + 1):
        year_dir = CONGRESS_RAW_GOVINFO / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        days = session_days(year)
        print(f"{year}: {len(days)} CREC days")

        # A healthy sitemap for any real CREC year lists 100+ days. A near-empty
        # list means the sitemap URL itself served an error page and the CREC-id
        # regex matched almost nothing -- the same outage/scheme-change failure
        # as a high phantom rate, but arriving before there is any rate to
        # compute. Caught here because the rate gate below cannot see it: with
        # `days` tiny, that gate is skipped entirely and the year would pass as
        # a silent no-op.
        if len(days) < MIN_DAYS_FOR_SANITY_CHECK:
            print(
                f"ABORT: {year} sitemap yielded only {len(days)} CREC day(s), "
                f"below the {MIN_DAYS_FOR_SANITY_CHECK}-day floor. Every real "
                "CREC session year has well over 100. This almost certainly "
                "means the sitemap URL served an error page or GovInfo changed "
                "its scheme -- not that this year had no Senate business. "
                "Aborting instead of silently recording an empty year."
            )
            return 1

        skipped: list[str] = []
        # Phantoms are buffered, NOT written to disk as we go. A marker makes
        # every future run skip that day, so writing one during an outage --
        # when every day looks phantom -- would permanently poison the cache:
        # the abort below would fire, but the markers would already be on disk,
        # and the next healthy run would skip the whole year and silently build
        # an empty corpus. Markers are only committed once the year clears the
        # sanity gate and the phantoms are therefore believable.
        for i, pkg in enumerate(days, 1):
            out_path = year_dir / f"{pkg}.json"
            marker_path = _phantom_marker_path(year_dir, pkg)
            if out_path.exists() and not args.refresh:
                continue
            if marker_path.exists() and not args.refresh:
                skipped.append(pkg)
                print(f"  skip {pkg}: known phantom package (marker on disk)")
                continue
            try:
                fetch_day(pkg, out_path)
            except PhantomPackageError:
                skipped.append(pkg)
                print(f"  skip {pkg}: phantom package (HTML instead of MODS XML)")
                continue
            else:
                if marker_path.exists():
                    # A --refresh run found this package now exists after
                    # all (e.g. GovInfo backfilled it) -- the old marker
                    # would otherwise cause future runs to skip it forever.
                    marker_path.unlink()
            if i % 25 == 0:
                print(f"  {year}: {i}/{len(days)}")

        run_skipped[year] = skipped
        skip_rate = len(skipped) / len(days)
        print(f"{year}: {len(skipped)}/{len(days)} days skipped as phantom ({skip_rate:.1%})")
        if skipped:
            print(f"  phantom package ids: {', '.join(skipped)}")

        if skip_rate > PHANTOM_SKIP_RATE_THRESHOLD:
            print(
                f"ABORT: {year} phantom-skip rate {skip_rate:.1%} exceeds the "
                f"{PHANTOM_SKIP_RATE_THRESHOLD:.0%} sanity threshold "
                f"({len(skipped)}/{len(days)} days). The only measured "
                "real-world rate is ~1.4% (2023: 3/209 days); a rate this "
                "high likely means GovInfo is having an outage or has "
                "changed its URL scheme, not that this many days are "
                "legitimately missing phantom packages. Aborting instead of "
                "silently producing an incomplete corpus. No phantom markers "
                "were written, so a later healthy run will retry these days."
            )
            return 1

        # The year is believable: commit its phantoms so a resumed run does not
        # re-request them.
        for pkg in skipped:
            _phantom_marker_path(year_dir, pkg).write_text(
                json.dumps(
                    {"package": pkg, "reason": "HTML response instead of MODS XML"}
                ),
                encoding="utf-8",
            )

    total_skipped = sum(len(pkgs) for pkgs in run_skipped.values())
    print(f"Run complete: {total_skipped} phantom day(s) skipped this run")
    for year, pkgs in run_skipped.items():
        if pkgs:
            print(f"  {year}: {', '.join(pkgs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
