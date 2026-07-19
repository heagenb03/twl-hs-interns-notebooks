"""Network stage for the tariff event-study dataset.

Pulls daily closes from Yahoo Finance and caches them to data/_raw/.
Run once; build_tariff.py consumes the cache offline.

    python scripts/fetch_tariff.py [--refresh]

IMPORTANT: auto_adjust=False and the `Close` column are deliberate. That gives
split-adjusted, NON-dividend-adjusted prices, matching what the original real
pull used. Verification: AAPL's 2017-01-03 close lands near 29 (nominal was
~116; the 4:1 split was Aug 2020). auto_adjust=True yields a materially
different series and would silently break the notebook's price-level prose.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd
import yfinance as yf

from twl_common import EXPECTED_TICKERS, PRICE_END, PRICE_START, RAW_DIR

RAW_PATH = RAW_DIR / "tariff_yahoo.csv"


def fetch(
    tickers: tuple[str, ...] = EXPECTED_TICKERS,
    start: str = PRICE_START,
    end: str = PRICE_END,
) -> pd.DataFrame:
    """Download daily closes. Returns a wide frame indexed by date."""
    # yfinance's `end` is exclusive; nudge it so PRICE_END is included.
    end_exclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        list(tickers),
        start=start,
        end=end_exclusive,
        auto_adjust=False,
        progress=False,
        group_by="column",
    )
    if raw.empty:
        raise RuntimeError("yfinance returned no data; check network and tickers")

    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close = close.reindex(columns=list(tickers))
    close.index.name = "date"
    return close


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="re-download even if the cache exists"
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_PATH.exists() and not args.refresh:
        print(f"cache exists: {RAW_PATH} (use --refresh to re-download)")
        return 0

    close = fetch()
    close.to_csv(RAW_PATH)
    print(f"wrote {RAW_PATH}  rows={len(close)}  cols={list(close.columns)}")
    print(f"range: {close.index.min().date()} -> {close.index.max().date()}")
    print("\nnull counts per ticker:")
    print(close.isna().sum().to_string())
    print(f"\nAAPL first close (expect ~29): {close['AAPL'].iloc[0]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
