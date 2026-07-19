"""Pure, offline transform: data/_raw/tariff_yahoo.csv -> data/tariff_prices.csv.

Deterministic and network-free. Safe to re-run.

    python scripts/build_tariff.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from twl_common import DATA_DIR, EXPECTED_TICKERS, RAW_DIR

RAW_PATH = RAW_DIR / "tariff_yahoo.csv"
OUT_PATH = DATA_DIR / "tariff_prices.csv"


def normalize_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """Sort, dedupe, drop incomplete rows, order columns, round to 2dp.

    Rows with ANY null are dropped rather than filled: the notebook's helpers
    do not tolerate NaN, and interpolating a price would invent data — the
    exact thing this project exists to stop doing.
    """
    out = raw.copy()
    out = out[~out.index.duplicated(keep="first")]
    out = out.sort_index()
    out = out.reindex(columns=list(EXPECTED_TICKERS))
    out = out.dropna(how="any")
    out = out.round(2)
    out.index.name = "date"
    return out


def build(raw_path: Path = RAW_PATH, out_path: Path = OUT_PATH) -> pd.DataFrame:
    raw = pd.read_csv(raw_path, index_col="date", parse_dates=True)
    prices = normalize_prices(raw)
    prices.to_csv(out_path)
    return prices


def main() -> int:
    if not RAW_PATH.exists():
        print(f"missing {RAW_PATH} — run: python scripts/fetch_tariff.py")
        return 1
    prices = build()
    print(f"wrote {OUT_PATH}  rows={len(prices)}")
    print(f"range: {prices.index.min().date()} -> {prices.index.max().date()}")
    print(prices.head(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
