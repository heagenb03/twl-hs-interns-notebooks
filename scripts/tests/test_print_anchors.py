import pandas as pd
import pytest

from print_anchors import day_zero_move, market_adjusted_move, tariff_anchors


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
