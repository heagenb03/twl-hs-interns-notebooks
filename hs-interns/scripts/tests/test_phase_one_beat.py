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


def _assert_covid_crash_bounds(covid_window: pd.Series) -> None:
    """Two-sided COVID-crash canary.

    The upper bound (<120) rejects "no crash at all" data (BA stayed high
    through the window). The lower bound (>80) is the one that matters most
    here — it rejects implausible/placeholder data, e.g. a column held
    constant at 1.0 (min == 1.0, well under 80). Do not simplify this back
    to one-sided: a naive `min() < 150` passes on an all-1.0 BA column,
    which also clears validate_tariff's non-positive-price check (1.0 > 0),
    so nothing else would catch it. The real 2020 BA low (95.01) sits
    comfortably inside (80, 120).
    """
    assert 80 < covid_window.min() < 120, (
        "expected the March 2020 BA collapse (real low ~95.01) inside "
        "(80, 120) in real data; if outside this band, the fetch may not "
        "have used real prices or the series may be a placeholder"
    )


def test_covid_crash_is_present_in_the_data(prices):
    """Documents the confound rather than hiding it: BA really does collapse."""
    covid_window = prices.loc["2020-02-01":"2020-04-30", "BA"]
    _assert_covid_crash_bounds(covid_window)


def test_covid_canary_rejects_constant_placeholder_data():
    """Finding 3 regression.

    A positive placeholder (BA held constant at 1.0) must fail the canary.
    It clears a naive `min() < 150` check and validate_tariff's
    non-positive-price check (1.0 > 0), so the two-sided bound here is the
    only thing standing between placeholder data and a passing suite.
    """
    covid_window = pd.Series(
        1.0, index=pd.date_range("2020-02-01", "2020-04-30", freq="B")
    )
    with pytest.raises(AssertionError):
        _assert_covid_crash_bounds(covid_window)
