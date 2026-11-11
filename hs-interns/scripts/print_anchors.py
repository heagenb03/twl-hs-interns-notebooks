"""Print every data-derived narrative claim ("anchor") the notebooks make.

Anchors are the "What you should see" numbers, and the shape-claims in prose
(e.g. "china mentions climb steeply after 2017", "Marco Rubio pulls away from
the average after ~2018"). Any data change invalidates them. This module is the
single source of truth for computing them from the built CSVs, so recapture is
mechanical instead of a manual hunt through markdown cells.

Anchors are informational, not invariants: they feed manual notebook-prose
recapture rather than a pass/fail gate (see validate_data.py for that). A
hardcoded name or shape claim that no longer holds against the data is still
printed -- as a loud sentinel string ("ABSENT FROM DATA", "NEVER CROSSES") --
rather than silently dropped, so a human notices and updates the prose. It is
NOT this module's job to make a claim true by fuzzy-matching or aliasing names.

Usage:  python scripts/print_anchors.py

This file was created independently on two branches and merged as a union:
`tariff_anchors` came from the tariff work, `congress_anchors` from the congress
work, and `main()` prints whichever sections have their source CSVs on disk.
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
                anchors[key] = day_zero_move(prices, ticker, date)
            except (KeyError, ValueError) as exc:
                anchors[key] = f"unavailable: {exc}"

    # Beat 3 stretch: BA's market-adjusted move 5 sessions after 2019-08-23.
    # Kept as a raw float — format once, at print time, to match the notebook.
    anchors["stretch/BA_market_adjusted_5d/2019-08-23"] = market_adjusted_move(
        prices, "BA", "2019-08-23", days=5
    )
    return anchors


def congress_anchors() -> dict[str, str]:
    """Every data-derived claim in congress_mentions.ipynb, keyed by beat."""
    mentions = pd.read_csv(DATA_DIR / "congress_mentions.csv")
    companions = pd.read_csv(DATA_DIR / "congress_companions.csv")
    senators = pd.read_csv(DATA_DIR / "congress_senators.csv")

    china = mentions[mentions.term == "china"].sort_values("year")
    out: dict[str, str] = {}

    out["setup/counts"] = (
        f"Loaded {len(mentions)} year-term counts, {len(companions)} companion "
        f"words, {len(senators)} senator-year counts."
    )
    out["setup/terms"] = str(sorted(mentions.term.unique()))
    out["beat1/china_series"] = (
        f"'china': {china.mentions.iloc[0]} mentions in {china.year.iloc[0]} -> "
        f"{china.mentions.iloc[-1]} in {china.year.iloc[-1]} "
        f"(peak: {china.mentions.max()} in {china.loc[china.mentions.idxmax(), 'year']})"
    )
    for era in ("1990s", "2000s", "2010s", "2020s"):
        top3 = (
            companions[companions.era == era]
            .sort_values("count", ascending=False)
            .word.head(3)
            .tolist()
        )
        out[f"beat2/{era}_top_three"] = ", ".join(top3)

    real = senators[senators.senator != "Senate average"]
    top2024 = real[real.year == 2024].sort_values("mentions", ascending=False)
    out["beat3/leaderboard_2024_top5"] = ", ".join(
        f"{r.senator} ({r.mentions})" for r in top2024.head(5).itertuples()
    )
    for name in ("Marco Rubio", "Tom Cotton", "Josh Hawley", "Chuck Schumer"):
        d = real[real.senator == name]
        if len(d) == 0:
            out[f"beat3/{name}"] = "ABSENT FROM DATA - prose must change"
            continue
        peak = d.loc[d.mentions.idxmax()]
        out[f"beat3/{name}"] = (
            f"first year {d.year.min()}, peaked at {peak.mentions} in {peak.year}"
        )

    japan = mentions[mentions.term == "japan"].set_index("year").mentions
    ratio = (china.set_index("year").mentions / japan).dropna()
    crossed = ratio[ratio > 1]
    out["stretch/china_overtook_japan"] = (
        str(crossed.index[0]) if len(crossed) else "NEVER CROSSES - stretch prose must change"
    )
    return out


def _print_tariff(prices: pd.DataFrame) -> None:
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


def main() -> int:
    """Print every anchor section whose source CSVs are present.

    Anchors are informational (they feed manual notebook-prose recapture, not a
    hard data invariant), so a missing set of source CSVs skips that section
    with a note rather than failing the run. Only finding no sections at all is
    treated as an error, mirroring validate_data.py's "nothing to check"
    convention. That matters more after the branch merge than it did on either
    branch alone: either notebook's CSVs can legitimately be absent while the
    other's are present, and the pre-merge tariff version returned 1 in exactly
    that case.
    """
    printed = 0

    tariff_path = DATA_DIR / "tariff_prices.csv"
    if tariff_path.exists():
        _print_tariff(pd.read_csv(tariff_path, index_col="date", parse_dates=True))
        printed += 1
    else:
        print(f"SKIP tariff: {tariff_path} not found")

    congress_paths = [
        DATA_DIR / "congress_mentions.csv",
        DATA_DIR / "congress_companions.csv",
        DATA_DIR / "congress_senators.csv",
    ]
    if all(p.exists() for p in congress_paths):
        print("\n" + "=" * 62)
        print("notebooks/congress_mentions.ipynb")
        print("=" * 62)
        for key, value in congress_anchors().items():
            print(f"{key}: {value}")
        printed += 1
    else:
        missing = [p.name for p in congress_paths if not p.exists()]
        print(f"SKIP congress: {', '.join(missing)} not found")

    if not printed:
        print("No anchor sources found.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
