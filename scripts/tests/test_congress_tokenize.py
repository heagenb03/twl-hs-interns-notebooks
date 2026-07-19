# scripts/tests/test_congress_tokenize.py
from congress_tokenize import STOPWORDS, companion_words, count_all_terms, count_term


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
