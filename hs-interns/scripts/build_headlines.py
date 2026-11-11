"""Pure, offline transform: data/_raw/headlines_gdelt.json -> data/headlines_real.csv.

Deterministic and network-free. Safe to re-run.

    python scripts/build_headlines.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from twl_common import DATA_DIR, RAW_DIR
from twl_common import HEADLINE_EVENTS as EVENTS
from twl_common import OUTLET_DOMAINS
from validate_data import validate_headlines

RAW_PATH = RAW_DIR / "headlines_gdelt.json"
OUT_PATH = DATA_DIR / "headlines_real.csv"

# GDELT titles often carry an outlet suffix. Removing it is essential: leaving
# "- The New York Times" in place would let the outlet classifier win by
# reading the suffix rather than the writing style, making Beat 2 meaningless.
_SUFFIX = re.compile(
    r"\s*[-|–—]\s*(the\s+new\s+york\s+times|new\s+york\s+times|nytimes(\.com)?"
    r"|wsj(\.com)?|the\s+wall\s+street\s+journal|wall\s+street\s+journal"
    r"|fox\s+news(\.com)?|foxnews(\.com)?"
    r"|xinhua(net)?(\.com)?|xinhua\s+news\s+agency)\s*$",
    flags=re.IGNORECASE,
)

# GDELT's title field inserts spaces around punctuation ("U . S .",
# "COVID - 19", "A Huge , Uncharted Experiment", "re - election"). This is
# tokenizer corruption, not editorial style -- it degrades VADER sentiment
# scoring and classifier input, so it is repaired here rather than left as
# signal.
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?%])")
_TOKENIZED_HYPHEN = re.compile(r"(?<=\w) - (?=\w)")
# Defensive: GDELT strips apostrophes upstream in practice, so this never
# fires against the real feed (the output CSV has zero apostrophes). Kept in
# case that changes; do not assume it is load-bearing.
_TOKENIZED_POSSESSIVE = re.compile(r"\s+'s\b")

# GDELT also leaves the tokenizer space AFTER a period between initials
# ("U . S ." becomes "U. S." once _SPACE_BEFORE_PUNCT runs, but the space
# between "U." and "S." survives). This rule joins a single uppercase letter
# + period to an immediately following single uppercase letter + period
# ("U. S." -> "U.S.", "F. C. C." -> "F.C.C."), via a lookahead so runs of
# 2+ initials cascade in one non-overlapping pass.
#
# It cannot fire on a real sentence boundary ("Trade talks stall. China
# responds"): the capture group only matches a SINGLE uppercase letter that
# is not preceded by another letter (?<![A-Za-z]), so a period ending an
# ordinary multi-letter word (e.g. "stall.") never matches -- the letter
# immediately before that period ("l") is lowercase and/or part of a longer
# token, not a standalone initial. The lookahead additionally requires the
# very next token to itself be a single uppercase letter followed by a
# period, so "Deal. A New Era" (a lone capital word after the period) will
# not match either, since "A" alone isn't followed by ".".
_TOKENIZED_INITIALS = re.compile(r"(?<![A-Za-z])([A-Z])\.\s+(?=[A-Z]\.)")

# GDELT's "(china OR chinese)" query matches the ARTICLE BODY, not the title, so
# roughly half the fetched headlines are unrelated to China or trade. Worse, the
# off-topic rate varies by outlet, which would let the notebook's outlet classifier
# win by learning topic mix rather than writing style. Requiring the topic in the
# HEADLINE removes that confound.
TOPIC_PATTERN = re.compile(
    r"china|chinese|beijing|xi jinping|tariff|trade war|trade deal|huawei|tiktok"
    r"|\byuan\b|hong kong|xinjiang|taiwan|phase one|spy balloon|\bwto\b",
    flags=re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """Strip outlet suffixes, repair GDELT tokenizer spacing, and collapse whitespace."""
    cleaned = _SUFFIX.sub("", title or "")
    cleaned = _SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
    cleaned = _TOKENIZED_HYPHEN.sub("-", cleaned)
    cleaned = _TOKENIZED_POSSESSIVE.sub("'s", cleaned)
    cleaned = _TOKENIZED_INITIALS.sub(r"\1.", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def build_frame(raw: dict) -> pd.DataFrame:
    """Flatten the raw cache into the synthetic file's schema.

    Events are emitted in the canonical order defined by fetch_headlines.EVENTS,
    NOT the order they appear in `raw`. The notebook selects its default event
    with unique()[2], so row order is load-bearing.

    Dedup scope is per-outlet, across ALL events -- not per (event, outlet).
    A headline republished under two different events for the same outlet is
    kept only once, at its first occurrence in canonical event order. This is
    required because the notebook trains an outlet classifier on headline
    text: a duplicate (outlet, headline) surviving under two events would let
    the same example leak into both a train split and a test split.

    Dedup runs on the DE-TOKENIZED headline (clean_title output), so two raw
    titles that differ only by GDELT tokenizer spacing collapse into one row.

    Headlines with no China/trade keyword (see TOPIC_PATTERN) are dropped --
    GDELT's query matches the article body, not the title, so a large share
    of fetched headlines are off-topic, and that off-topic rate varies by
    outlet, which would otherwise confound the outlet classifier.
    """
    rows: list[dict[str, str]] = []
    seen_by_outlet: dict[str, set[str]] = {outlet: set() for outlet in OUTLET_DOMAINS}
    for event, _start, _end in EVENTS:
        outlets = raw.get(event, {})
        for outlet in OUTLET_DOMAINS:
            seen = seen_by_outlet[outlet]
            for article in outlets.get(outlet, []):
                headline = clean_title(article.get("title", ""))
                if not headline or headline in seen or not TOPIC_PATTERN.search(headline):
                    continue
                seen.add(headline)
                rows.append({"event": event, "outlet": outlet, "headline": headline})

    return pd.DataFrame(rows, columns=["event", "outlet", "headline"])


def build(raw_path: Path = RAW_PATH, out_path: Path = OUT_PATH) -> tuple[pd.DataFrame, list[str]]:
    """Build the frame from the raw cache, validate it, then write the CSV.

    Validation runs BEFORE the write: a frame that violates a load-bearing
    invariant (e.g. the third distinct event isn't "Phase One deal") must
    never reach disk. Returns (frame, problems); `problems` is empty on
    success. The caller (main()) is responsible for turning a non-empty
    `problems` into a non-zero exit code.
    """
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    frame = build_frame(raw)
    problems = validate_headlines(frame)
    if not problems:
        frame.to_csv(out_path, index=False, encoding="utf-8")
    return frame, problems


def main() -> int:
    if not RAW_PATH.exists():
        print(f"missing {RAW_PATH} — run: python scripts/fetch_headlines.py")
        return 1
    frame, problems = build(RAW_PATH, OUT_PATH)
    if problems:
        print(f"FAIL: refusing to write {OUT_PATH} -- validation problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"wrote {OUT_PATH}  rows={len(frame)}")
    print("\nrows per event x outlet:")
    print(frame.groupby(["event", "outlet"]).size().unstack(fill_value=0).to_string())
    order = list(frame.event.unique())
    print(f"\nevent order: {order}")
    # Safe by construction: validate_headlines() above already guarantees at
    # least 3 distinct events when problems is empty, so order[2] cannot
    # IndexError here.
    print(f"unique()[2] == {order[2]!r} (must be 'Phase One deal')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
