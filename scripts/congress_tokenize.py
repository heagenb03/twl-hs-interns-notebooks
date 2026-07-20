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

Companion-word tokenization rules (companion_words), also for
data/PROVENANCE.md:
  - a hyphen immediately followed by a line break is rejoined (the line
    break is removed, the hyphen is kept) before tokenizing, so a compound
    hard-wrapped by CREC's fixed-column layout ("most-favored-\nnation")
    still tokenizes as one word instead of splitting into "most-favored-"
    and "nation"
  - "--" (two or more consecutive hyphens) becomes a space; a single hyphen
    stays inside its token, so compounds like "most-favored-nation" survive
  - possessives fold to their base form on every token, corpus-wide, not
    just china-forms ("taiwan's" -> "taiwan", "america's" -> "america");
    this is deliberate, so the companions axis folds possessives the same
    way count_term's TERM_VARIANTS already does on the mentions axis
  - china is excluded as the pivot if it appears, possessive or not, as one
    of a token's hyphen-separated segments ("china", "china's",
    "anti-china", "china-based", "china's-based")
  - tokens of 2 characters or fewer are dropped, then stopwords are dropped
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

    Before tokenizing, a hyphen immediately followed by a line break is
    rejoined to a bare hyphen, so a compound that CREC's fixed-column layout
    hard-wraps across two lines ("most-favored-\r\nnation") still tokenizes
    as one word instead of splitting into "most-favored-" and "nation" --
    which would silently cost the notebook's Beat 2 top-three companion-word
    anchor. A hyphen not followed by a line break, such as the suspended
    elision in "one- and two-child policies", is untouched.

    CREC's unspaced `--` (used for asides and vote tallies) is then
    normalized to a space, so e.g. "announced--yeas" splits into two words
    instead of fusing into one that dodges both the stopword and pivot
    filters. Ordinary single hyphens are left alone, so hyphenated compounds
    like "most-favored-nation" still tokenize as one word.

    Possessives fold to their base form ("china's" -> "china", "taiwan's" ->
    "taiwan") for every token, not just china-forms, so this axis agrees with
    the mentions axis in count_term, which already folds possessives via
    TERM_VARIANTS.

    A token is excluded from the companion list as a self-mention of the
    pivot if, after stripping any trailing possessive from each of its
    hyphen-separated segments, one of those segments is exactly "china".
    This covers the bare pivot ("china"), a token-final possessive
    ("china's"), hyphenated compounds ("anti-china", "china-based"), and a
    possessive fused onto a compound ("china's-based").
    """
    if window != "speech":
        raise ValueError(f"unsupported window: {window!r}")
    if not count_term(text, "china"):
        return []
    # CREC hard-wraps at a fixed column, so a hyphenated compound can land
    # with its hyphen at end-of-line and the rest of the word on the next
    # line ("most-favored-\r\nnation"). That line break is a typesetting
    # artifact, not a second hyphen boundary. Left alone, _WORD_RE (which
    # does not match across a newline) would split it into "most-favored-"
    # and "nation", and neither reaches the notebook's Beat 2 top-three
    # companion-word anchor -- silently degrading the very anchor this
    # module's single-hyphen invariant exists to protect. Rejoining the
    # hyphen-newline sequence back to a bare hyphen BEFORE tokenizing fixes
    # this without touching an ordinary hyphen anywhere else: a hyphen
    # followed by a space, as in the real 2021 fixture's "one- and
    # two-child policies" (a suspended-compound elision, not a line-wrap),
    # is untouched because it is not followed by a newline.
    text = re.sub(r"-[ \t]*\r?\n[ \t]*", "-", text)
    text = re.sub(r"-{2,}", " ", text)  # CREC uses -- for asides
    out: list[str] = []
    for w in _WORD_RE.findall(text.lower()):
        w = re.sub(r"'s$", "", w)  # possessive
        if "china" in [re.sub(r"'s$", "", part) for part in w.split("-")]:
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
