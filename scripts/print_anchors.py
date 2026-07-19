"""Emit every anchor value the intern notebooks claim, keyed by notebook + beat.

Anchors are the "What you should see" numbers in notebook markdown. Any data
change invalidates them. This script makes recapture mechanical instead of a
manual hunt through markdown cells.

    python scripts/print_anchors.py

Extension point: later plans add `headlines_anchors()` and `congress_anchors()`
to this module, each following the same `anchors: dict[str, object]` shape and
each folded into `main()` alongside `tariff_anchors()`.
"""
from __future__ import annotations

import sys

import pandas as pd

from twl_common import DATA_DIR, EVENT_DATES, EXPECTED_TICKERS, event_day


def day_zero_move(prices: pd.DataFrame, ticker: str, date: str) -> float:
    """Percent change on the event day versus the prior session."""
    day = event_day(prices.index, date)
    i = prices.index.get_loc(day)
    if i == 0:
        raise ValueError(f"{date} has no preceding session")
    return (prices[ticker].iloc[i] / prices[ticker].iloc[i - 1] - 1) * 100


def market_adjusted_move(
    prices: pd.DataFrame, ticker: str, date: str, days: int
) -> float:
    """Cumulative abnormal return: `ticker`'s move beyond SPY over `days` sessions.

    Mirrors the notebook's `market_adjusted()` helper exactly: it sums the
    *daily* excess return (ticker's daily return minus SPY's daily return)
    across each session from the prior close through `date + days` sessions,
    rather than differencing the two total returns. The two approaches agree
    only when there is a single period (`days == 0`); over multiple sessions
    they diverge because of compounding, and the notebook's cumulative-sum
    version is what the notebook actually prints (and is the standard
    definition of Cumulative Abnormal Return in event studies).
    """
    day = event_day(prices.index, date)
    i = prices.index.get_loc(day)
    if i == 0:
        raise ValueError(f"{date} has no preceding session")
    window = int(days)
    stock = prices[ticker].iloc[i - 1 : i + window + 1].pct_change().dropna()
    mkt = prices["SPY"].iloc[i - 1 : i + window + 1].pct_change().dropna()
    abnormal = ((stock - mkt) * 100).cumsum()
    return abnormal.iloc[-1]


def tariff_anchors(prices: pd.DataFrame) -> dict[str, object]:
    """Every anchor claimed by notebooks/tariff_event_study.ipynb."""
    anchors: dict[str, object] = {
        "n_trading_days": len(prices),
        "tickers": list(prices.columns),
        "date_range": (
            f"{prices.index.min().date()} -> {prices.index.max().date()}"
        ),
    }

    for date in EVENT_DATES:
        for ticker in EXPECTED_TICKERS:
            key = f"day0/{date}/{ticker}"
            try:
                anchors[key] = round(day_zero_move(prices, ticker, date), 2)
            except (KeyError, ValueError) as exc:
                anchors[key] = f"unavailable: {exc}"

    # Beat 3 stretch: BA's market-adjusted move 5 sessions after 2019-08-23.
    anchors["stretch/BA_market_adjusted_5d/2019-08-23"] = round(
        market_adjusted_move(prices, "BA", "2019-08-23", days=5), 2
    )
    return anchors


def main() -> int:
    path = DATA_DIR / "tariff_prices.csv"
    if not path.exists():
        print(f"missing {path}")
        return 1

    prices = pd.read_csv(path, index_col="date", parse_dates=True)

    print("=" * 62)
    print("notebooks/tariff_event_study.ipynb")
    print("=" * 62)
    print("\n-- Setup --")
    print(f"  Loaded {len(prices)} trading days for {len(prices.columns)} tickers:")
    print(f"    {list(prices.columns)}")

    anchors = tariff_anchors(prices)
    print("\n-- Day-0 moves by event --")
    for date in EVENT_DATES:
        moves = ", ".join(
            f"{tk} {anchors[f'day0/{date}/{tk}']:+.1f}%"
            for tk in EXPECTED_TICKERS
            if isinstance(anchors[f"day0/{date}/{tk}"], float)
        )
        print(f"  {date}: {moves}")

    print("\n-- Beat 3 stretch --")
    val = anchors["stretch/BA_market_adjusted_5d/2019-08-23"]
    print(f"  After 5 days, BA moved {val:+.1f}% beyond what the market explains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
