# scripts/tests/test_congress_tokenize.py
import re
from pathlib import Path

from congress_tokenize import STOPWORDS, companion_words, count_all_terms, count_term

FIXTURES = Path(__file__).parent / "fixtures" / "crec"


def _load(gid: str) -> str:
    """Load a real CREC granule fixture as plain text (tags stripped)."""
    return re.sub(r"<[^>]+>", "", (FIXTURES / f"{gid}.htm").read_text(encoding="utf-8"))


def test_counts_occurrences_not_documents():
    # The whole point of the full-text path: a speech saying China eighty times
    # is eighty mentions, not one.
    assert count_term("China China China", "china") == 3


def test_is_case_insensitive():
    assert count_term("CHINA china China", "china") == 3


def test_possessive_counts():
    assert count_term("China's economy", "china") == 1


def test_adjectival_form_does_not_count():
    # 'Chinese' is a different word. Counting it would redefine the y-axis.
    assert count_term("Chinese exports", "china") == 0


def test_substring_does_not_count():
    assert count_term("Indochina and chinaware", "china") == 0


def test_tariff_plural_counts():
    assert count_term("tariff and tariffs", "tariff") == 2


def test_count_all_terms_returns_every_term():
    counts = count_all_terms("China and Japan and China")
    assert counts["china"] == 2
    assert counts["japan"] == 1
    assert counts["trade"] == 0
    assert set(counts) == {
        "china", "climate", "japan", "russia",
        "taiwan", "tariff", "terrorism", "trade",
    }


def test_companion_words_excludes_stopwords_and_the_pivot():
    words = companion_words("China and the trade deficit with China")
    assert "china" not in words
    assert "the" not in words
    assert "and" not in words
    assert "trade" in words
    assert "deficit" in words


def test_companion_words_returns_empty_when_china_absent():
    # Companions are words co-occurring with China. No China, no companions.
    assert companion_words("The Senator yields the floor.") == []


def test_companion_words_preserves_repeats_for_frequency_counting():
    words = companion_words("China trade China trade tariffs")
    assert words.count("trade") == 2


def test_stopwords_include_procedural_record_boilerplate():
    # CREC is dense with 'Mr. President', 'yield', 'Senator' - these would
    # otherwise dominate every era's top ten and teach nothing.
    for w in ("president", "senator", "yield", "floor", "amendment", "unanimous"):
        assert w in STOPWORDS


def test_possessive_pivot_does_not_leak_as_companion():
    # "China's" is a mention of China (count_term counts it), but it must not
    # also show up as China's own companion word.
    words = companion_words("China's economy grew")
    assert "china's" not in words
    assert "china" not in words


def test_hyphenated_china_compounds_do_not_leak_as_companions():
    words = companion_words("China trade with anti-China sentiment and China-based firms")
    assert "anti-china" not in words
    assert "china-based" not in words
    assert "china" not in words


def test_double_hyphen_fusion_is_split_and_filtered():
    # CREC uses unspaced -- for asides; without splitting, "policy--and" fuses
    # into one token that escapes both the stopword filter (hiding "and") and
    # would otherwise leak into the companion list wholesale.
    words = companion_words("China policy--and again the trade deficit")
    assert not any("--" in w for w in words)
    assert "policy--and" not in words
    assert "and" not in words  # was hidden inside the fused token; now split and filtered
    assert "policy" in words
    assert "again" in words


def test_hyphenated_compound_survives_intact():
    # Regression guard: single hyphens must be preserved. Splitting on them
    # would destroy real compounds like "most-favored-nation", a documented
    # top-three 1990s companion word.
    words = companion_words("China trade and most-favored-nation status")
    assert "most-favored-nation" in words


def test_possessive_hyphenated_china_compound_does_not_leak_as_companion():
    # "china's-based" is a possessive fused onto a hyphenated compound. The
    # token-final possessive strip never fires (the token ends in "-based",
    # not "'s"), so the pivot check must strip 's per hyphen-segment instead
    # of relying on the whole-token strip.
    words = companion_words("China trade with China's-based firms")
    assert "china's-based" not in words
    assert "china" not in words


# --- I4: line-break hyphenation must rejoin, not split, into one token ---
#
# CREC hard-wraps lines at a fixed column, so a hyphenated compound can land
# with its hyphen at end-of-line and the rest of the word on the next line
# (e.g. "most-favored-\nnation"). That line break is a typesetting artifact,
# not a second hyphen boundary -- treating it as one silently breaks the
# single-hyphen invariant this module exists to protect: an occurrence of
# 'most-favored-nation' broken across a line would decompose into
# 'most-favored-' + 'nation', and neither reaches the notebook's Beat 2
# top-three companion-word anchor.


def test_line_break_hyphenation_rejoins_into_one_token():
    words = companion_words("China trade and most-favored-\nnation status")
    assert "most-favored-nation" in words
    assert "most-favored-" not in words
    assert "nation" not in words


def test_most_favored_nation_anchor_survives_line_break_hyphenation():
    # The notebook's Beat 2 anchor cites 'most-favored-nation' as a 1990s
    # top-three companion word. CREC's real line endings are \r\n, so the
    # rejoin must handle that, not just a bare \n.
    words = companion_words("China policy on most-favored-\r\nnation status endures")
    assert words.count("most-favored-nation") == 1
    assert "most-favored-" not in words


def test_hyphen_not_followed_by_newline_keeps_token_intact():
    # Regression guard: the rejoin must trigger only on a hyphen immediately
    # followed by a line break, never on an ordinary single hyphen elsewhere
    # in running text. The real 2021 fixture has "one- and two-child
    # policies" -- a suspended-compound elision (hyphen before a space, not
    # a newline). That is intentional English, not a line-wrap artifact, and
    # must be left exactly as written.
    words = companion_words("China shifted from one- and two-child policies")
    assert "one-" in words
    assert "two-child" in words


def test_double_hyphen_aside_still_splits_across_a_line_break():
    # Regression guard: the real 2019 fixture has "workers--\r\nmanufacturing"
    # -- a double-hyphen aside that happens to fall at a hard-wrap. The new
    # single-hyphen rejoin must not interfere with the existing '--' -> space
    # split; the two words must still separate.
    words = companion_words("China trade workers--\r\nmanufacturing jobs")
    assert "workers" in words
    assert "manufacturing" in words
    assert not any("--" in w for w in words)
    assert "workers--manufacturing" not in words
    assert "workers-manufacturing" not in words


def test_real_2019_fixture_has_no_line_wrap_trailing_hyphen_tokens():
    # Measured defect (I4): CREC-2019-05-22 hard-wraps four words across a
    # single hyphen -- so-/called, vis-a-/vis, State-/owned, rules-/based.
    # Each must now rejoin into one correctly hyphenated companion word.
    words = companion_words(_load("CREC-2019-05-22-pt1-PgS3039-2"))
    assert "so-called" in words
    assert "vis-a-vis" in words
    assert "state-owned" in words
    assert "rules-based" in words
    for broken in ("so-", "vis-a-", "state-", "rules-"):
        assert broken not in words


def test_real_2021_fixture_has_no_line_wrap_trailing_hyphen_tokens():
    # Measured defect (I4): CREC-2021-06-08 hard-wraps one word across a
    # single hyphen -- game-/changing. It must rejoin into one token.
    #
    # Note: this fixture also contains "one- and two-child policies" (see
    # test_hyphen_not_followed_by_newline_keeps_token_intact above), which
    # legitimately still ends in a hyphen after the fix -- it is a suspended
    # elision, not a line-wrap artifact, so it is intentionally NOT covered
    # by a blanket "no token ends in a hyphen" assertion here.
    words = companion_words(_load("CREC-2021-06-08-pt1-PgS3975-2"))
    assert "game-changing" in words
    assert "game-" not in words
