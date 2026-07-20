# scripts/tests/test_print_anchors.py
"""Tests for print_anchors.

This file was created independently on two branches and merged as a union: the
tariff-anchor tests came from one, the congress-anchor tests from the other.
Neither set was dropped -- print_anchors.py itself is the same union.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import print_anchors
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
    return) give the same number by construction â€” a single period has no
    compounding to diverge on. That leaves the notebook's actual formula
    (cumulative sum of daily excess returns) completely unguarded: someone
    could "simplify" `market_adjusted_move` to the total-return difference
    and every prior test would keep passing, even though the emitted anchor
    would then silently disagree with what the notebook prints.

    Do NOT replace this with the total-return formula to make it "cleaner" â€”
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
    formatting yields "-1.2%" â€” a number that gets copied into notebook
    markdown and then contradicted the moment a student re-runs the cell.
    """
    anchors = tariff_anchors(real_prices)
    raw = anchors["day0/2018-06-15/BA"]
    assert isinstance(raw, float)
    assert f"{raw:+.1f}%" == "-1.3%"


def test_congress_anchors_on_real_data_has_expected_keys() -> None:
    """Exercise the emitter against the real (still-synthetic) CSVs in data/.

    Values are not meaningful yet (data/ is schema-valid but synthetic), but
    the emitter must run without error against the real files and produce
    every expected beat key as a string.
    """
    anchors = print_anchors.congress_anchors()

    expected_keys = {
        "setup/counts",
        "setup/terms",
        "beat1/china_series",
        "beat2/1990s_top_three",
        "beat2/2000s_top_three",
        "beat2/2010s_top_three",
        "beat2/2020s_top_three",
        "beat3/leaderboard_2024_top5",
        "beat3/Marco Rubio",
        "beat3/Tom Cotton",
        "beat3/Josh Hawley",
        "beat3/Chuck Schumer",
        "stretch/china_overtook_japan",
    }
    assert expected_keys <= anchors.keys()
    assert all(isinstance(v, str) for v in anchors.values())


@pytest.fixture
def congress_csvs(tmp_path: Path) -> Path:
    """Write minimal, schema-valid congress_*.csv fixtures to a temp dir.

    Only 'Marco Rubio' appears as a senator here â€” Tom Cotton, Josh Hawley,
    and Chuck Schumer are deliberately absent so the ABSENT FROM DATA path
    can be exercised without touching the real (still-synthetic) data/ CSVs.
    """
    mentions = pd.DataFrame(
        {
            "year": [1990, 2000, 2010, 2020, 2024] * 2,
            "term": ["china"] * 5 + ["japan"] * 5,
            "mentions": [10, 20, 30, 40, 50, 100, 90, 80, 70, 60],
        }
    )
    mentions.to_csv(tmp_path / "congress_mentions.csv", index=False)

    companions = pd.DataFrame(
        {
            "era": ["1990s", "1990s", "1990s"],
            "word": ["trade", "wto", "tariff"],
            "count": [30, 20, 10],
        }
    )
    companions.to_csv(tmp_path / "congress_companions.csv", index=False)

    senators = pd.DataFrame(
        {
            "senator": ["Marco Rubio", "Marco Rubio", "Senate average"],
            "year": [2020, 2024, 2024],
            "mentions": [5, 15, 8],
        }
    )
    senators.to_csv(tmp_path / "congress_senators.csv", index=False)

    return tmp_path


def test_name_absent_from_data_reports_loud_failure_string(
    monkeypatch: pytest.MonkeyPatch, congress_csvs: Path
) -> None:
    """A hardcoded senator name absent from the data must surface loudly.

    congress_anchors() intentionally does NOT fuzzy-match or alias names.
    With only 'Marco Rubio' present, the other three hardcoded names (Tom
    Cotton, Josh Hawley, Chuck Schumer) must each come back as the literal
    'ABSENT FROM DATA - prose must change' sentinel â€” not an empty result,
    not a KeyError/IndexError, and not a silent wrong match.
    """
    monkeypatch.setattr(print_anchors, "DATA_DIR", congress_csvs)

    anchors = print_anchors.congress_anchors()

    for absent_name in ("Tom Cotton", "Josh Hawley", "Chuck Schumer"):
        assert (
            anchors[f"beat3/{absent_name}"]
            == "ABSENT FROM DATA - prose must change"
        )
    assert anchors["beat3/Marco Rubio"] != "ABSENT FROM DATA - prose must change"
    assert "peaked" in anchors["beat3/Marco Rubio"]


def test_ratio_never_crossing_reports_loud_failure_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If china never overtakes japan, the stretch claim must say so loudly."""
    mentions = pd.DataFrame(
        {
            "year": [1990, 2000, 2010, 2020] * 2,
            "term": ["china"] * 4 + ["japan"] * 4,
            "mentions": [5, 6, 7, 8, 50, 60, 70, 80],
        }
    )
    mentions.to_csv(tmp_path / "congress_mentions.csv", index=False)

    companions = pd.DataFrame({"era": ["1990s"], "word": ["trade"], "count": [1]})
    companions.to_csv(tmp_path / "congress_companions.csv", index=False)

    senators = pd.DataFrame(
        {"senator": ["Senate average"], "year": [2020], "mentions": [1]}
    )
    senators.to_csv(tmp_path / "congress_senators.csv", index=False)

    monkeypatch.setattr(print_anchors, "DATA_DIR", tmp_path)

    anchors = print_anchors.congress_anchors()

    assert (
        anchors["stretch/china_overtook_japan"]
        == "NEVER CROSSES - stretch prose must change"
    )


def test_main_runs_and_exits_zero_against_real_data(capsys: pytest.CaptureFixture) -> None:
    """python scripts/print_anchors.py should run cleanly against data/.

    The section header changed at the branch merge: the congress branch printed
    "== congress ==" while the tariff branch used a banner naming the notebook.
    The merged main() uses the banner for both, so this asserts on the notebook
    name rather than the old header.
    """
    exit_code = print_anchors.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "congress_mentions.ipynb" in captured.out
    assert "beat3/Marco Rubio" in captured.out


def test_main_prints_both_notebooks_sections_after_the_merge(
    capsys: pytest.CaptureFixture,
) -> None:
    """Neither branch's anchors may be dropped by the union.

    print_anchors.py was created independently on both branches; the merge
    resolution is a union, and losing one side's section is the failure mode
    that resolution invites.
    """
    print_anchors.main()
    out = capsys.readouterr().out
    assert "tariff_event_study.ipynb" in out
    assert "congress_mentions.ipynb" in out
    assert "Day-0 moves by event" in out  # a tariff anchor section
    assert "beat1/china_series" in out    # a congress anchor
