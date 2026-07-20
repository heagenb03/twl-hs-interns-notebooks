import pandas as pd
import pytest

from print_anchors import day_zero_move, market_adjusted_move, tariff_anchors
from twl_common import DATA_DIR


@pytest.fixture
def real_prices() -> pd.DataFrame:
    """The committed, real tariff price series (not a toy fixture).

    The double-rounding and CAR-formula regressions below only reproduce
    against real data: the toy fixture's round numbers never land on the
    boundary where `round(x, 2)` then `{:+.1f}` disagrees with formatting
    the raw float directly.
    """
    return pd.read_csv(DATA_DIR / "tariff_prices.csv", index_col="date", parse_dates=True)


@pytest.fixture
def toy_prices() -> pd.DataFrame:
    index = pd.DatetimeIndex(
        ["2019-08-22", "2019-08-23", "2019-08-26", "2019-08-27"], name="date"
    )
    return pd.DataFrame(
        {
            "SPY": [100.0, 98.0, 99.0, 99.0],
            "FXI": [50.0, 48.0, 48.0, 48.0],
            "BA": [200.0, 190.0, 190.0, 190.0],
            "CAT": [100.0, 98.0, 98.0, 98.0],
            "SOYB": [20.0, 19.8, 19.8, 19.8],
            "AAPL": [50.0, 49.0, 49.0, 49.0],
        },
        index=index,
    )


def test_day_zero_move_is_percent_change_versus_prior_session(toy_prices):
    assert day_zero_move(toy_prices, "SPY", "2019-08-23") == pytest.approx(-2.0)


def test_day_zero_move_rolls_forward_from_a_non_trading_day(toy_prices):
    # 2019-08-24 is a Saturday; the next session is 2019-08-26.
    assert day_zero_move(toy_prices, "SPY", "2019-08-24") == pytest.approx(
        (99.0 / 98.0 - 1) * 100
    )


def test_market_adjusted_move_subtracts_the_spy_move(toy_prices):
    # BA falls 5% on day 0; SPY falls 2%. Excess is about -3 points.
    excess = market_adjusted_move(toy_prices, "BA", "2019-08-23", days=0)
    assert excess == pytest.approx(-3.0, abs=0.2)


def test_market_adjusted_move_of_spy_against_itself_is_zero(toy_prices):
    assert market_adjusted_move(toy_prices, "SPY", "2019-08-23", days=0) == pytest.approx(
        0.0, abs=1e-9
    )


def test_tariff_anchors_reports_the_loaded_row_count(toy_prices):
    anchors = tariff_anchors(toy_prices)
    assert anchors["n_trading_days"] == 4


def test_tariff_anchors_lists_the_tickers_in_order(toy_prices):
    anchors = tariff_anchors(toy_prices)
    assert anchors["tickers"] == ["SPY", "FXI", "BA", "CAT", "SOYB", "AAPL"]


def test_market_adjusted_move_pins_the_cumulative_abnormal_return_formula(real_prices):
    """Pins the CAR formula at days > 0, where it is NOT algebraically
    identical to a difference of total returns.

    Both of the existing `market_adjusted_move` tests use `days=0`, where
    cumsum-of-daily-excess-returns and (total stock return - total SPY
    return) give the same number by construction — a single period has no
    compounding to diverge on. That leaves the notebook's actual formula
    (cumulative sum of daily excess returns) completely unguarded: someone
    could "simplify" `market_adjusted_move` to the total-return difference
    and every prior test would keep passing, even though the emitted anchor
    would then silently disagree with what the notebook prints.

    Do NOT replace this with the total-return formula to make it "cleaner" —
    that is precisely the regression this test exists to catch. BA / 2019-08-23
    / days=5: the correct cumsum formula gives ~2.6392; the wrong
    total-return-difference formula gives ~2.7005. This asserts we land on
    the former and are clearly NOT the latter.
    """
    result = market_adjusted_move(real_prices, "BA", "2019-08-23", days=5)
    assert result == pytest.approx(2.6392, abs=0.001)
    assert result != pytest.approx(2.7005, abs=0.001)


def test_tariff_anchors_day0_move_is_formatted_once_not_double_rounded(real_prices):
    """Guards against double rounding: `tariff_anchors` must keep raw, unrounded
    day-0 floats so that formatting with `{:+.1f}` at print time matches what
    the notebook itself prints (the notebook formats the raw float directly).

    BA's real day-0 move on 2018-06-15 is -1.2526...%, which formats to
    "-1.3%" when rounded once. If `tariff_anchors` instead pre-rounds to
    `round(x, 2)` (-1.25) and that gets formatted again, Python's float
    formatting yields "-1.2%" — a number that gets copied into notebook
    markdown and then contradicted the moment a student re-runs the cell.
    """
    anchors = tariff_anchors(real_prices)
    raw = anchors["day0/2018-06-15/BA"]
    assert isinstance(raw, float)
    assert f"{raw:+.1f}%" == "-1.3%"
