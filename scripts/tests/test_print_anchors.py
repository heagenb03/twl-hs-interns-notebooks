from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import print_anchors


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

    Only 'Marco Rubio' appears as a senator here — Tom Cotton, Josh Hawley,
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
    'ABSENT FROM DATA - prose must change' sentinel — not an empty result,
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
    """python scripts/print_anchors.py should run cleanly against data/."""
    exit_code = print_anchors.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "== congress ==" in captured.out
    assert "beat3/Marco Rubio" in captured.out
