"""Shared helpers for the TWL intern-notebook data pipeline.

Imported by fetch_*, build_*, validate_data, and print_anchors. Deliberately
pandas-only (no `requests`) so the offline modules (build_*, validate_data)
never pull the network stage's dependency in transitively.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = REPO_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "_raw"

EXPECTED_TICKERS: tuple[str, ...] = ("SPY", "FXI", "BA", "CAT", "SOYB", "AAPL")

# Order matters: it becomes CSV row order, and the notebook relies on
# unique()[2] == "Phase One deal".
HEADLINE_EVENTS: tuple[tuple[str, str, str], ...] = (
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
