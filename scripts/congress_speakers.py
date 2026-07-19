"""Attribute Congressional Record text to the senator who said it.

Granule metadata (congMember) gives the SET of members who spoke in a granule,
but not which of them said any given word. Multi-speaker granules must be split
on speaker headers.

Three rendering facts make this harder than it looks, all verified against real
granules (see docs/superpowers/specs/2026-07-19-congress-spike-findings.md):

  1. A speaker turn is set in ALL CAPS ('Mr. CORNYN.'). A citation of another
     member inside a speech is set in mixed case ('Mr. Cornyn.'). The pattern
     MUST stay case-sensitive; a case-insensitive one splits at citations and
     misattributes the rest of the current speaker's words.
  2. Mc/Mac/O' names keep their lowercase letter ('Mr. McCAIN.'), so an
     all-caps character class misses every one of their turns.
  3. Same-last-name senators are disambiguated by a qualifier that moves the
     period ('Mr. SCOTT of Florida.').

And turns span granule boundaries: a continuation is not re-headed, so text
before the first header belongs to the previous granule's last speaker.
"""
from __future__ import annotations

import re

# A surname token: mostly caps, tolerating the Mc/Mac/O' prefixes CREC renders
# in mixed case. The {2,} floor is what keeps mixed-case citations from matching.
_TOKEN = r"(?:Mc|Mac|O')?[A-Z]{2,}"

SPEAKER_RE: re.Pattern[str] = re.compile(
    r"\b(?:Mr|Ms|Mrs|Miss)\.\s+"
    rf"({_TOKEN}(?:[ '\-]{_TOKEN})*)"
    r"(?:\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?"
    r"\."
)

_SUFFIX_RE = re.compile(r"\s*,?\s*(JR|SR|II|III|IV)\.?$", re.IGNORECASE)


def normalize_lnf(lnf: str) -> str:
    """Turn a MODS authority-lnf name into a comparable surname key.

    'Roth Jr., William V.' -> 'ROTH'.  The suffix lives in the metadata but not
    in the rendered speaker header, so it is stripped from the metadata side.
    """
    surname = lnf.split(",")[0].strip()
    return _SUFFIX_RE.sub("", surname).upper()


def split_turns(text: str) -> list[tuple[str, str]]:
    """Split granule text into (SURNAME, segment) pairs, in document order.

    Text before the first header is NOT returned here - it belongs to the
    carry-in speaker and is handled by attribute_granule.
    """
    hits = list(SPEAKER_RE.finditer(text))
    turns: list[tuple[str, str]] = []
    for i, match in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        turns.append((match.group(1).upper(), text[match.end() : end]))
    return turns


def attribute_granule(
    text: str,
    members: list[dict],
    carry_in: str | None,
) -> dict[str, str]:
    """Map bioGuideId -> the text that member spoke in this granule.

    `members` is the granule's congMember list; each dict needs 'lnf', 'bio',
    and 'role'. `carry_in` is the bioGuideId of the previous granule's last
    speaker, or None at the start of a day.

    Raises ValueError if any role=SPEAKING member cannot be accounted for.
    That guard is the whole point: without it, a missed header silently folds
    one senator's words into another's and every downstream count is wrong in a
    way no total-preserving check can detect.
    """
    speaking = {normalize_lnf(m["lnf"]): m["bio"] for m in members if m["role"] == "SPEAKING"}
    attributed: dict[str, list[str]] = {}

    turns = split_turns(text)

    # Rule: sole speaking member and no header at all - the whole granule is
    # theirs, the header lives in a prior granule.
    if not turns and len(speaking) == 1:
        only_bio = next(iter(speaking.values()))
        return {only_bio: text}

    # Rule: text before the first header belongs to the carry-in speaker.
    if turns:
        head = text[: SPEAKER_RE.search(text).start()]
        if head.strip() and carry_in:
            attributed.setdefault(carry_in, []).append(head)

    for surname, segment in turns:
        bio = speaking.get(surname)
        if bio is None:
            # A header for someone not in this granule's metadata. Rare, and
            # not safe to guess at - drop the segment rather than misfile it.
            continue
        attributed.setdefault(bio, []).append(segment)

    matched_bios = set(attributed)
    missing = sorted(
        bio for bio in speaking.values() if bio not in matched_bios and bio != carry_in
    )
    if missing:
        raise ValueError(
            f"unaccounted role=SPEAKING member(s): {', '.join(missing)}; "
            f"headers found: {sorted({s for s, _ in turns})}"
        )

    return {bio: "\n".join(parts) for bio, parts in attributed.items()}


def last_speaker(text: str, members: list[dict]) -> str | None:
    """The bioGuideId of the last member to speak, for carry-in to the next granule."""
    speaking = {normalize_lnf(m["lnf"]): m["bio"] for m in members if m["role"] == "SPEAKING"}
    turns = split_turns(text)
    if turns:
        return speaking.get(turns[-1][0])
    if len(speaking) == 1:
        return next(iter(speaking.values()))
    return None
