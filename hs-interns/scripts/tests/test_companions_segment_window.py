# scripts/tests/test_companions_segment_window.py
"""C3: the Beat 2 co-occurrence window must not change definition at 2017.

A Gentzkow segment is ONE senator's ONE speech. A GovInfo segment was the whole
GRANULE, which the real fixtures show is a multi-speaker section: the committed
2021 granule is 19 turns across 10 senators. So the co-occurrence window
silently widened at exactly the splice year, and the split lands INSIDE the
2010s era while the notebook's default comparison is 1990s vs 2020s -- tight
windows on the left, whole-day sections on the right.

Measured on the committed real fixtures, before the fix:

  CREC-2021-06-08 whole-granule: presiding, officer, all, legislation, yeas,
                                 nays, colleagues, cantwell
  CREC-2021-06-08 per-turn:      all, america, competition, states, research,
                                 plant, semiconductors, supply

Procedural boilerplate and a senator's surname, versus actual vocabulary. The
notebook promises interns they will watch words shift from "trade, WTO,
most-favored-nation" to "CCP, threat, genocide". Whole-granule windows do not
reproduce that.

Separately, the notebook markdown tells interns the window is "the same sentence
as China" while the code's window was the entire segment. The taught definition
and the computed one disagreed.

THE FIX IS AT THE SEGMENT LAYER, NOT THE TOKENIZER. Touching congress_tokenize
or _WORD_RE endangers the most-favored-nation anchor, which is itself a Beat 2
teaching claim.
"""
import json
import re

import pytest

import congress_speakers
from build_congress_companions import govinfo_segments_by_era
from congress_cache import write_manifest
from congress_tokenize import count_term, top_companions

FIXTURE_DIR = __import__("pathlib").Path(__file__).parent / "fixtures" / "crec"


def _granule_text(name: str) -> str:
    html = (FIXTURE_DIR / name).read_text(encoding="utf-8", errors="replace")
    match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.S | re.I)
    return re.sub(r"<[^>]+>", "", match.group(1)) if match else ""


def _cache_with(tmp_path, year, granule_texts):
    year_dir = tmp_path / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    pkg = f"CREC-{year}-01-01"
    write_manifest(tmp_path, year, [pkg])
    (year_dir / f"{pkg}.json").write_text(
        json.dumps({"package": pkg, "granules": [{"text": t} for t in granule_texts]}),
        encoding="utf-8",
    )
    return tmp_path


def test_a_multi_speaker_granule_becomes_many_segments_not_one(tmp_path):
    """The 2021 fixture is 19 turns across 10 senators, and was one segment."""
    text = _granule_text("CREC-2021-06-08-pt1-PgS3975-2.htm")
    assert len(congress_speakers.split_turns(text)) == 19, "fixture changed"

    _cache_with(tmp_path, 2021, [text])
    segments, _ = govinfo_segments_by_era(tmp_path, 2021, 2021)
    assert len(segments["2020s"]) > 1


def test_only_china_bearing_turns_donate_companion_words(tmp_path):
    """The whole point. A granule where one turn mentions China must not donate
    the other eighteen turns' vocabulary."""
    text = _granule_text("CREC-2021-06-08-pt1-PgS3975-2.htm")
    _cache_with(tmp_path, 2021, [text])
    segments, _ = govinfo_segments_by_era(tmp_path, 2021, 2021)
    for segment in segments["2020s"]:
        assert count_term(segment, "china") > 0


def test_the_2020s_top_words_are_vocabulary_not_procedural_boilerplate(tmp_path):
    """The measured before/after, asserted directly.

    Before the fix this granule's top words were procedural -- presiding,
    officer, yeas, nays -- plus the surname `cantwell`. Those are the words
    Beat 2 would have taught as the 2020s China vocabulary.
    """
    text = _granule_text("CREC-2021-06-08-pt1-PgS3975-2.htm")
    _cache_with(tmp_path, 2021, [text])
    segments, _ = govinfo_segments_by_era(tmp_path, 2021, 2021)
    top = [word for word, _ in top_companions(segments["2020s"], n=8)]

    for procedural in ["presiding", "officer", "yeas", "nays"]:
        assert procedural not in top, f"{procedural!r} is boilerplate, not vocabulary"
    assert "cantwell" not in top, "senator surnames are not China vocabulary"
    assert "semiconductors" in top


def test_a_lone_china_mention_no_longer_donates_the_whole_granule(tmp_path):
    """The 1999 aviation granule mentions china ONCE in 36k characters. Under a
    whole-granule window that single mention donated every word in the section
    -- airports, extensions, the presiding officer -- to whatever era it landed
    in. The granule's real recorded date is 1999, but CONGRESS_ERAS no longer
    has a 1990s bucket (see twl_common.CONGRESS_ERAS), so this cache is written
    under 2015 -- inside the surviving 2010s era -- purely to give
    govinfo_segments_by_era a bucket to write into. Only the era label moved;
    the fixture content (a real granule with exactly one china mention buried
    in 36k characters) and the property under test are unchanged."""
    text = _granule_text("CREC-1999-03-17-pt1-PgS2821-2.htm")
    assert count_term(text, "china") == 1, "fixture changed"

    _cache_with(tmp_path, 2015, [text])
    segments, _ = govinfo_segments_by_era(tmp_path, 2015, 2015)
    donated = sum(len(s) for s in segments["2010s"])
    assert donated < len(text) / 10


# --- the two mandatory guards ---------------------------------------------


def test_a_granule_with_no_speaker_headers_falls_back_to_the_whole_granule(tmp_path):
    """GUARD (a). Task 9's synthetic fixture has no headers at all, and all four
    of its tests break without this fallback. Real headerless granules exist
    too: CREC-2023-06-14 is 286 characters and legitimately has none."""
    text = "China trade competition semiconductors research supply"
    assert congress_speakers.split_turns(text) == []

    _cache_with(tmp_path, 2021, [text])
    segments, skips = govinfo_segments_by_era(tmp_path, 2021, 2021)
    assert segments["2020s"] == [text]
    assert skips["granule_without_speaker_headers"] == 1


def test_head_text_is_dropped_and_counted_never_silently(tmp_path):
    """GUARD (b). split_turns drops everything before the first header. In the
    real fixtures that is the page-title block (0.7-3.9% of the granule, zero
    china mentions), so dropping it also removes a known contaminant. But it
    can also be a continuation of the previous granule's speech, so the volume
    dropped has to be visible rather than assumed harmless."""
    head = "China tariffs semiconductors\n"
    text = head + "  Mr. CANTWELL. China competition research.\n"
    _cache_with(tmp_path, 2021, [text])
    segments, skips = govinfo_segments_by_era(tmp_path, 2021, 2021)

    assert skips["head_text_segments_dropped"] == 1
    assert skips["head_text_china_dropped"] == count_term(head, "china")
    assert not any("tariffs" in s for s in segments["2020s"])


def test_real_fixture_head_text_carries_no_china_so_nothing_is_lost(tmp_path):
    """Documents the measurement the drop policy rests on."""
    for name in [
        "CREC-1999-03-17-pt1-PgS2821-2.htm",
        "CREC-2019-05-22-pt1-PgS3039-2.htm",
        "CREC-2021-06-08-pt1-PgS3975-2.htm",
    ]:
        text = _granule_text(name)
        match = congress_speakers.SPEAKER_RE.search(text)
        assert count_term(text[: match.start()], "china") == 0, name


def test_every_drop_reason_is_counted(tmp_path):
    """Counting discipline: dropped data is reported, never merely dropped."""
    _cache_with(tmp_path, 2021, ["no headers and no pivot word here"])
    _, skips = govinfo_segments_by_era(tmp_path, 2021, 2021)
    assert set(skips) >= {
        "bad_json",
        "phantom_marker",
        "granule_no_text",
        "year_outside_known_eras",
        "no_china_mention",
        "granule_without_speaker_headers",
        "head_text_segments_dropped",
        "head_text_china_dropped",
    }
