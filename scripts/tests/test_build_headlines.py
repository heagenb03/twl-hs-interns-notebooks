import json

import pandas as pd
import pytest

from build_headlines import build, build_frame, clean_title


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


def test_duplicate_headlines_across_events_for_same_outlet_are_dropped():
    """A headline republished under two different events for the same outlet
    is a train/test leak for the outlet classifier, so it must be kept only
    once -- at its canonically-first occurrence (per fetch_headlines.EVENTS)."""
    raw = {
        "Phase One deal": {
            "NYT": [
                {"title": "China Trade Tensions Rise - The New York Times",
                 "url": "u10", "domain": "nytimes.com", "seendate": "20200115T120000Z"},
            ],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
        "2018 tariff announcement": {
            "NYT": [
                {"title": "China Trade Tensions Rise - The New York Times",
                 "url": "u11", "domain": "nytimes.com", "seendate": "20180322T120000Z"},
            ],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
    }
    out = build_frame(raw)
    matches = out[(out.outlet == "NYT") & (out.headline == "China Trade Tensions Rise")]
    assert len(matches) == 1
    assert matches.iloc[0]["event"] == "2018 tariff announcement"


def test_blank_titles_are_dropped():
    raw = {"Phase One deal": {"NYT": [
        {"title": "   ", "url": "u", "domain": "nytimes.com", "seendate": ""},
    ], "WSJ": [], "Fox": [], "Xinhua": []}}
    out = build_frame(raw)
    assert len(out) == 0


def test_clean_title_removes_space_before_punctuation():
    assert clean_title("Hello , World . Fine : Yes") == "Hello, World. Fine: Yes"


def test_clean_title_repairs_tokenized_hyphens():
    assert clean_title("COVID - 19 forces re - election") == "COVID-19 forces re-election"


def test_clean_title_collapses_tokenized_possessive():
    assert clean_title("China 's Economy Slows") == "China's Economy Slows"


def test_clean_title_still_strips_outlet_suffixes_and_leaves_clean_titles_alone():
    assert clean_title("Some Headline - The New York Times") == "Some Headline"
    assert clean_title("Tariffs Imposed on Chinese Goods") == "Tariffs Imposed on Chinese Goods"


def test_fuyuan_false_positive_on_yuan_substring_is_not_treated_as_on_topic():
    """Minor fix: TOPIC_PATTERN's 'yuan' term lacked a word boundary, so
    'Fuyuan' (a place name containing the substring 'yuan') falsely matched
    a headline with no actual China/currency content."""
    raw = {"Phase One deal": {"NYT": [
        {"title": "Port of Fuyuan in Heilongjiang carries out strict "
                   "measures against COVID-19",
         "url": "u", "domain": "nytimes.com", "seendate": ""},
    ], "WSJ": [], "Fox": [], "Xinhua": []}}
    out = build_frame(raw)
    assert len(out) == 0


def test_off_topic_headline_is_dropped():
    """GDELT's (china OR chinese) query matches the article body, not the
    title, so many fetched headlines have no China/trade keyword at all."""
    raw = {"Phase One deal": {"NYT": [
        {"title": "Your Thursday Briefing", "url": "u", "domain": "nytimes.com", "seendate": ""},
    ], "WSJ": [], "Fox": [], "Xinhua": []}}
    out = build_frame(raw)
    assert len(out) == 0


def test_on_topic_headline_is_kept():
    raw = {"Phase One deal": {"NYT": [
        {"title": "China Trade Deal Reached", "url": "u", "domain": "nytimes.com", "seendate": ""},
    ], "WSJ": [], "Fox": [], "Xinhua": []}}
    out = build_frame(raw)
    assert len(out) == 1
    assert out.iloc[0]["headline"] == "China Trade Deal Reached"


def test_clean_title_collapses_spaced_initials():
    assert clean_title("Warns U. S. Treasury") == "Warns U.S. Treasury"


def test_clean_title_collapses_three_spaced_initials():
    assert clean_title("F. C. C. Joins Push") == "F.C.C. Joins Push"


def test_clean_title_leaves_sentence_boundary_alone():
    """Two single-letter-initial fix must not merge across a real sentence
    boundary, where a full word ends in a period and the next word (which
    happens to start with a capital) is unrelated."""
    assert clean_title("Trade talks stall. China responds") == "Trade talks stall. China responds"


def test_clean_title_is_idempotent_on_already_joined_initials():
    assert clean_title("U.S. Treasury Secretary Speaks") == "U.S. Treasury Secretary Speaks"


def test_build_refuses_to_write_csv_when_third_event_is_wrong(tmp_path):
    """Finding 3: build() must validate BEFORE writing. A frame whose third
    distinct event (in canonical order) is not 'Phase One deal' violates the
    notebook's unique()[2] invariant and must never reach disk."""
    raw = {
        "2018 tariff announcement": {
            "NYT": [{"title": "China Tariffs Announced", "url": "u1",
                      "domain": "nytimes.com", "seendate": ""}],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
        "Huawei CFO arrest": {
            "NYT": [{"title": "China Huawei Arrest Sparks Anger", "url": "u2",
                      "domain": "nytimes.com", "seendate": ""}],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
        # "Phase One deal" deliberately has no on-topic headlines, so it is
        # skipped and "Hong Kong security law" becomes the third distinct event.
        "Hong Kong security law": {
            "NYT": [{"title": "China Hong Kong Law Passed", "url": "u3",
                      "domain": "nytimes.com", "seendate": ""}],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
    }
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "out.csv"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    frame, problems = build(raw_path=raw_path, out_path=out_path)

    assert any("Phase One deal" in p and "third" in p.lower() for p in problems)
    assert not out_path.exists(), "a constraint-violating CSV must never be written"


def test_build_writes_csv_for_a_frame_with_at_least_three_events(tmp_path):
    raw = {
        event: {
            "NYT": [{"title": f"China {event}", "url": f"u-{event}",
                      "domain": "nytimes.com", "seendate": ""}],
            "WSJ": [], "Fox": [], "Xinhua": [],
        }
        for event in ("2018 tariff announcement", "Huawei CFO arrest", "Phase One deal")
    }
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "out.csv"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    frame, problems = build(raw_path=raw_path, out_path=out_path)

    assert problems == []
    assert out_path.exists()
    on_disk = pd.read_csv(out_path)
    assert len(on_disk) == len(frame)


def test_build_reports_clear_message_for_fewer_than_three_events_no_indexerror(tmp_path):
    """Finding 3: fewer than three surviving events must give a clear
    message, not an IndexError from unique()[2]."""
    raw = {
        "2018 tariff announcement": {
            "NYT": [{"title": "China Tariffs Announced", "url": "u1",
                      "domain": "nytimes.com", "seendate": ""}],
            "WSJ": [], "Fox": [], "Xinhua": [],
        },
    }
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "out.csv"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    frame, problems = build(raw_path=raw_path, out_path=out_path)

    assert any("only 1 distinct event" in p or "need at least 3" in p for p in problems)
    assert not out_path.exists()


def test_detokenization_runs_before_dedup():
    """Two raw titles differing only by tokenization spacing must collapse
    into a single row -- dedup has to run on the DE-TOKENIZED headline."""
    raw = {"Phase One deal": {"NYT": [
        {"title": "China Trade Deal , Explained", "url": "u1", "domain": "nytimes.com", "seendate": ""},
        {"title": "China Trade Deal, Explained", "url": "u2", "domain": "nytimes.com", "seendate": ""},
    ], "WSJ": [], "Fox": [], "Xinhua": []}}
    out = build_frame(raw)
    assert len(out) == 1
    assert out.iloc[0]["headline"] == "China Trade Deal, Explained"
