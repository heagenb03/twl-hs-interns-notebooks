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

from fetch_headlines import EVENTS, OUTLET_DOMAINS
from twl_common import DATA_DIR, RAW_DIR

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


def clean_title(title: str) -> str:
    """Strip outlet suffixes and collapse whitespace."""
    cleaned = _SUFFIX.sub("", title or "")
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
    """
    rows: list[dict[str, str]] = []
    seen_by_outlet: dict[str, set[str]] = {outlet: set() for outlet in OUTLET_DOMAINS}
    for event, _start, _end in EVENTS:
        outlets = raw.get(event, {})
        for outlet in OUTLET_DOMAINS:
            seen = seen_by_outlet[outlet]
            for article in outlets.get(outlet, []):
                headline = clean_title(article.get("title", ""))
                if not headline or headline in seen:
                    continue
                seen.add(headline)
                rows.append({"event": event, "outlet": outlet, "headline": headline})

    return pd.DataFrame(rows, columns=["event", "outlet", "headline"])


def build(raw_path: Path = RAW_PATH, out_path: Path = OUT_PATH) -> pd.DataFrame:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    frame = build_frame(raw)
    frame.to_csv(out_path, index=False, encoding="utf-8")
    return frame


def main() -> int:
    if not RAW_PATH.exists():
        print(f"missing {RAW_PATH} — run: python scripts/fetch_headlines.py")
        return 1
    frame = build()
    print(f"wrote {OUT_PATH}  rows={len(frame)}")
    print("\nrows per event x outlet:")
    print(frame.groupby(["event", "outlet"]).size().unstack(fill_value=0).to_string())
    print(f"\nevent order: {list(frame.event.unique())}")
    print(f"unique()[2] == {list(frame.event.unique())[2]!r} (must be 'Phase One deal')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
