# scripts/congress_tokenize.py
"""One definition of what counts as a mention, shared by every congress build.

The notebook's y-axis is labelled "mentions". This module is what that word
means. `build_congress_mentions` and `build_congress_companions` both import
from here so the two charts cannot drift apart.

Tokenization rules, stated for data/PROVENANCE.md:
  - matching is case-insensitive
  - possessives count      ("China's" is a mention of China)
  - adjectival forms do not ("Chinese" is a different word)
  - substrings do not      ("Indochina" is not a mention of China)
  - "tariffs" counts as "tariff"; no other plural is folded
"""
from __future__ import annotations

import re
from collections import Counter

from twl_common import TERM_VARIANTS

_COMPILED: dict[str, re.Pattern[str]] = {
    term: re.compile(pattern, re.IGNORECASE) for term, pattern in TERM_VARIANTS.items()
}

_WORD_RE = re.compile(r"[a-z][a-z'\-]+")

# Ordinary English function words, plus the procedural vocabulary that saturates
# the Congressional Record. Without the second group, every era's top ten is
# "president, senator, yield, floor" and the beat teaches nothing.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an and are as at be been but by for from had has have he her his i if in
    is it its me my no not of on or our she that the their them then there these
    they this to was we were what when which who will with would you your
    mr mrs ms miss president senator senators yield yielded yielding floor
    chair chairman madam speaker gentleman gentlewoman amendment amendments
    unanimous consent quorum motion vote votes voting bill act resolution
    committee record congress congressional senate house session ask
    """.split()
)


def count_term(text: str, term: str) -> int:
    """Count true occurrences of `term` in `text`."""
    return len(_COMPILED[term].findall(text))


def count_all_terms(text: str) -> dict[str, int]:
    """Count every notebook term in `text`. Terms absent from the text count 0."""
    return {term: count_term(text, term) for term in _COMPILED}


def companion_words(text: str, window: str = "speech") -> list[str]:
    """Words co-occurring with 'china', as a repeat-preserving list.

    Co-occurrence window is the whole speech segment: if the segment mentions
    China at all, every non-stopword in it is a companion. This is the
    definition documented in PROVENANCE.md. Repeats are preserved so the caller
    can count frequency.

    Before tokenizing, CREC's unspaced `--` (used for asides and vote tallies)
    is normalized to a space, so e.g. "announced--yeas" splits into two words
    instead of fusing into one that dodges both the stopword and pivot
    filters. Ordinary single hyphens are left alone, so hyphenated compounds
    like "most-favored-nation" still tokenize as one word.

    Any token that is 'china' or a china-possessive/compound built from it
    ("china's", "anti-china", "china-based") is excluded from the companion
    list as a self-mention of the pivot, not a companion of it.
    """
    if window != "speech":
        raise ValueError(f"unsupported window: {window!r}")
    if not count_term(text, "china"):
        return []
    text = re.sub(r"-{2,}", " ", text)  # CREC uses -- for asides
    out: list[str] = []
    for w in _WORD_RE.findall(text.lower()):
        w = re.sub(r"'s$", "", w)  # possessive
        if "china" in w.split("-"):
            continue
        if w in STOPWORDS or len(w) <= 2:
            continue
        out.append(w)
    return out


def top_companions(segments: list[str], n: int = 10) -> list[tuple[str, int]]:
    """The `n` most frequent companion words across many speech segments."""
    tally: Counter[str] = Counter()
    for seg in segments:
        tally.update(companion_words(seg))
    return tally.most_common(n)
