import pandas as pd
import pytest

from build_headlines import build_frame, clean_title


@pytest.fixture
def raw() -> dict:
    """Two events, out of canonical order, with dirty titles and a duplicate."""
    return {
        "Phase One deal": {
            "NYT": [
                {"title": "U.S. and China Sign Phase One Deal - The New York Times",
                 "url": "u1", "domain": "nytimes.com", "seendate": "20200115T120000Z"},
                {"title": "  Trade Truce Leaves Tariffs In Place  ",
                 "url": "u2", "domain": "nytimes.com", "seendate": "20200116T120000Z"},
            ],
            "WSJ": [
                {"title": "Markets Shrug at Phase One | WSJ",
                 "url": "u3", "domain": "wsj.com", "seendate": "20200115T130000Z"},
            ],
            "Fox": [], "Xinhua": [],
        },
        "2018 tariff announcement": {
            "NYT": [
                {"title": "Tariffs Imposed on Chinese Goods",
                 "url": "u4", "domain": "nytimes.com", "seendate": "20180322T120000Z"},
                {"title": "Tariffs Imposed on Chinese Goods",
                 "url": "u5", "domain": "nytimes.com", "seendate": "20180323T120000Z"},
            ],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
    }


def test_clean_title_strips_dash_outlet_suffix():
    assert clean_title("Some Headline - The New York Times") == "Some Headline"


def test_clean_title_strips_pipe_outlet_suffix():
    assert clean_title("Some Headline | WSJ") == "Some Headline"


def test_clean_title_collapses_whitespace():
    assert clean_title("  Spaced   Out  ") == "Spaced Out"


def test_clean_title_leaves_a_clean_title_alone():
    assert clean_title("Tariffs Imposed on Chinese Goods") == "Tariffs Imposed on Chinese Goods"


def test_columns_match_the_synthetic_schema(raw):
    out = build_frame(raw)
    assert list(out.columns) == ["event", "outlet", "headline"]


def test_events_appear_in_canonical_order_not_input_order(raw):
    """Row order is load-bearing: the notebook uses unique()[2]."""
    out = build_frame(raw)
    assert list(out.event.unique()) == ["2018 tariff announcement", "Phase One deal"]


def test_duplicate_headlines_within_an_outlet_are_dropped(raw):
    out = build_frame(raw)
    nyt_2018 = out[(out.event == "2018 tariff announcement") & (out.outlet == "NYT")]
    assert len(nyt_2018) == 1


def test_empty_outlets_produce_no_rows(raw):
    out = build_frame(raw)
    assert "Fox" not in set(out.outlet)


def test_headlines_are_stripped(raw):
    out = build_frame(raw)
    assert "Trade Truce Leaves Tariffs In Place" in set(out.headline)


def test_blank_titles_are_dropped():
    raw = {"Phase One deal": {"NYT": [
        {"title": "   ", "url": "u", "domain": "nytimes.com", "seendate": ""},
    ], "WSJ": [], "Fox": [], "Xinhua": []}}
    out = build_frame(raw)
    assert len(out) == 0
