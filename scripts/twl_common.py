"""Shared helpers for the TWL intern-notebook data pipeline.

Imported by fetch_*, build_*, validate_data, and print_anchors.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = REPO_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "_raw"

EXPECTED_TICKERS: tuple[str, ...] = ("SPY", "FXI", "BA", "CAT", "SOYB", "AAPL")

# The six real trade-war announcement dates. Labels live in the notebook, not here.
EVENT_DATES: tuple[str, ...] = (
    "2018-03-22",
    "2018-06-15",
    "2018-12-03",
    "2019-05-06",
    "2019-08-23",
    "2020-01-15",
)

PRICE_START: str = "2017-01-03"
PRICE_END: str = "2020-06-30"


def event_day(index: pd.DatetimeIndex, date: str | pd.Timestamp) -> pd.Timestamp:
    """Return `date` if it is in `index`, else the next entry after it.

    Real market data has holidays, so an arbitrary calendar date may not be a
    trading day. Rolling forward matches how a market participant would act on
    news released when the market was shut.

    Raises KeyError if no index entry falls on or after `date`.
    """
    stamp = pd.Timestamp(date)
    later = index[index >= stamp]
    if len(later) == 0:
        raise KeyError(
            f"{stamp.date()} is after the last available date ({index[-1].date()})"
        )
    return later[0]


# ---------------------------------------------------------------- congress

CONGRESS_ERAS: tuple[str, ...] = ("1990s", "2000s", "2010s", "2020s")
MENTIONS_YEARS: range = range(1990, 2025)
SENATOR_YEARS: range = range(2010, 2025)

# One regex per notebook term. Possessives count ("China's" is a mention of
# China); adjectival forms do not ("Chinese" is a different word, and counting
# it would quietly change what the y-axis means). Plurals count only where the
# plural is the same concept ("tariffs").
TERM_VARIANTS: dict[str, str] = {
    "china": r"\bchina(?:'s)?\b",
    "japan": r"\bjapan(?:'s)?\b",
    "russia": r"\brussia(?:'s)?\b",
    "taiwan": r"\btaiwan(?:'s)?\b",
    "tariff": r"\btariffs?\b",
    "trade": r"\btrade\b",
    "terrorism": r"\bterrorism\b",
    "climate": r"\bclimate\b",
}

# GovInfo bulk paths. No API key, no rate limit metering. Note the prefix split:
# metadata under /metadata/pkg/, document text under /content/pkg/.
GOVINFO_MODS_URL: str = "https://www.govinfo.gov/metadata/pkg/{pkg}/mods.xml"
GOVINFO_HTML_URL: str = "https://www.govinfo.gov/content/pkg/{pkg}/html/{granule}.htm"
GOVINFO_SITEMAP_URL: str = "https://www.govinfo.gov/sitemap/CREC_{year}_sitemap.xml"
USER_AGENT: str = "twl-intern-notebooks-research"

CONGRESS_RAW_GOVINFO: Path = RAW_DIR / "congress_govinfo"
CONGRESS_RAW_GENTZKOW: Path = RAW_DIR / "congress_gentzkow"
