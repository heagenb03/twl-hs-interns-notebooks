"""Beat 3's claim, as an executable assertion.

The notebook says surprise escalations move markets hard while Phase One
"barely twitches" because it was priced in. The surprise here is the
2019-05-06 session — the market's reaction to Trump's Sunday tweet
(2019-05-05) threatening to raise tariffs on $200B of Chinese goods,
re-escalating the trade war out of nowhere. Phase One, by contrast, is the
long-anticipated 2020-01-15 signing. If real data breaks that contrast, the
notebook's headline story needs rewriting — surface it loudly.

Note: this file defines its own local `day_zero_move()` helper rather than
importing one from `scripts/print_anchors.py`. That duplication is
intentional — this test is a decision gate and must not depend on that
script existing.
"""
import pandas as pd
import pytest

from twl_common import DATA_DIR, event_day

SURPRISE_ESCALATION = "2019-05-06"
PHASE_ONE = "2020-01-15"


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return pd.read_csv(
        DATA_DIR / "tariff_prices.csv", index_col="date", parse_dates=True
    )


def day_zero_move(prices: pd.DataFrame, ticker: str, date: str) -> float:
    """Percent change on the event day versus the prior session."""
    day = event_day(prices.index, date)
    i = prices.index.get_loc(day)
    assert i > 0, f"{date} has no preceding session"
    return (prices[ticker].iloc[i] / prices[ticker].iloc[i - 1] - 1) * 100


def test_phase_one_moves_less_than_the_surprise_escalation(prices):
    """The core of Beat 3: priced-in news moves markets less than a surprise."""
    for ticker in ("SPY", "FXI", "BA"):
        surprise = abs(day_zero_move(prices, ticker, SURPRISE_ESCALATION))
        phase_one = abs(day_zero_move(prices, ticker, PHASE_ONE))
        assert phase_one < surprise, (
            f"{ticker}: Phase One moved {phase_one:.2f}% vs surprise "
            f"{surprise:.2f}% — Beat 3's premise does not hold in real data"
        )


def test_phase_one_is_a_small_move_in_absolute_terms(prices):
    """'Barely twitches' should mean under ~1%, not merely 'less than'."""
    for ticker in ("SPY", "FXI", "BA"):
        move = abs(day_zero_move(prices, ticker, PHASE_ONE))
        assert move < 1.0, f"{ticker}: Phase One day-0 move was {move:.2f}%"


def test_covid_crash_is_present_in_the_data(prices):
    """Documents the confound rather than hiding it: BA really does collapse."""
    covid_window = prices.loc["2020-02-01":"2020-04-30", "BA"]
    assert covid_window.min() < 150, (
        "expected the March 2020 BA collapse in real data; if absent, the "
        "fetch may not have used real prices"
    )
