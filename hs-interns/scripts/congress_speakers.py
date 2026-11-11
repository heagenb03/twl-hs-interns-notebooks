"""Attribute Congressional Record text to the senator who said it.

Granule metadata (congMember) gives the SET of members who spoke in a granule,
but not which of them said any given word. Multi-speaker granules must be split
on speaker headers.

Four rendering facts make this harder than it looks, all verified against real
granules (see docs/superpowers/specs/2026-07-19-congress-spike-findings.md):

  1. A speaker turn is set in ALL CAPS ('Mr. CORNYN.'). A citation of another
     member inside a speech is set in mixed case ('Mr. Cornyn.'). The pattern
     MUST stay case-sensitive; a case-insensitive one splits at citations and
     misattributes the rest of the current speaker's words.
  2. Mc/Mac/O' names keep their lowercase letter ('Mr. McCAIN.'), so an
     all-caps character class misses every one of their turns.
  3. Same-last-name senators are disambiguated by a qualifier that moves the
     period ('Mr. SCOTT of Florida.').
  4. Surnames can carry accents ('Mr. LUJAN.' is rendered with an acute), and
     'Miss' takes no period where 'Mr.'/'Ms.'/'Mrs.' do.

And turns span granule boundaries: a continuation is not re-headed, so text
before the first header belongs to the previous granule's last speaker.

Same-surname disambiguation
---------------------------
The header qualifier is a spelled-out state name; congMember carries a
two-letter `state` code. `_STATE_CODES` bridges the two.

  * One speaking member with a given surname -> the qualifier is not required
    and is ignored. Most turns carry no qualifier, so this is the common path.
  * Two or more speaking members share a surname -> the qualifier decides.
    A bare, unqualified header is then genuinely ambiguous and is NOT guessed
    at; it is routed to the unresolved list and the guard raises. Five
    same-surname Senate pairs served concurrently in 2010-2024 (Nelson, Brown,
    Johnson, Udall, Scott), so this is a routine case, not an edge case.

Accents are FOLDED ON BOTH SIDES: `normalize_lnf` strips combining marks from
the metadata surname and `split_turns` strips them from the header, so
'Luján, Ben Ray' and 'Mr. LUJÁN.' both key on 'LUJAN'. The regex character
class still has to accept accented uppercase in order to match in the first
place; folding only makes the two sides comparable, and is robust to GovInfo
and the record body disagreeing about the accent.

Guard behaviour
---------------
`attribute_granule` raises ValueError on either kind of accounting failure:

  * a role=SPEAKING member who received no text (a header the parser missed);
  * a header that could not be resolved to a member - unknown surname, or an
    ambiguous same-surname turn. The old code dropped those segments silently,
    which destroyed text without failing any total-preserving check.

`carry_in` is exempt from the first check only when it ACTUALLY received text
(i.e. only when it appears in the result). Exempting it unconditionally
disabled the guard for whichever member happened to be the carry-in.
"""
from __future__ import annotations

import re
import unicodedata

# A surname token: mostly caps, tolerating the Mc/Mac/O' prefixes CREC renders
# in mixed case, plus accented uppercase (Latin-1 supplement). The {2,} floor
# is what keeps mixed-case citations from matching.
_UPPER = r"A-ZÀ-ÖØ-Þ"
_TOKEN = rf"(?:Mc|Mac|O')?[{_UPPER}]{{2,}}"

# 'Mr.', 'Ms.', 'Mrs.' take a period; 'Miss' is a whole word and takes none.
SPEAKER_RE: re.Pattern[str] = re.compile(
    r"\b(?:(?:Mr|Ms|Mrs)\.|Miss)\s+"
    rf"({_TOKEN}(?:[ '\-]{_TOKEN})*)"
    r"(?:\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*))?"
    r"\."
)

_SUFFIX_RE = re.compile(r"\s*,?\s*(JR|SR|II|III|IV)\.?$", re.IGNORECASE)

_STATE_CODES: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}


def _fold(text: str) -> str:
    """Strip combining marks so 'LUJÁN' and 'Lujan' compare equal.

    Case is untouched: folding must not defeat the case-sensitivity that
    separates real turns from mixed-case citations.
    """
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def normalize_lnf(lnf: str) -> str:
    """Turn a MODS authority-lnf name into a comparable surname key.

    'Roth Jr., William V.' -> 'ROTH'.  The suffix lives in the metadata but not
    in the rendered speaker header, so it is stripped from the metadata side.
    Accents are folded ('Luján, Ben Ray' -> 'LUJAN') to match the header side.
    """
    surname = lnf.split(",")[0].strip()
    return _fold(_SUFFIX_RE.sub("", surname)).upper()


def _iter_turns(text: str) -> list[tuple[str, str | None, str]]:
    """Split granule text into (SURNAME, state name or None, segment) triples.

    Internal: `split_turns` is the public view that drops the qualifier.
    """
    hits = list(SPEAKER_RE.finditer(text))
    turns: list[tuple[str, str | None, str]] = []
    for i, match in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        turns.append(
            (_fold(match.group(1)).upper(), match.group(2), text[match.end() : end])
        )
    return turns


def split_turns(text: str) -> list[tuple[str, str]]:
    """Split granule text into (SURNAME, segment) pairs, in document order.

    Text before the first header is NOT returned here - it belongs to the
    carry-in speaker and is handled by attribute_granule. The 'of <State>'
    qualifier is not part of the surname; see `_iter_turns` if you need it.
    """
    return [(surname, segment) for surname, _, segment in _iter_turns(text)]


def _speaking_by_surname(members: list[dict]) -> dict[str, list[dict]]:
    """Group role=SPEAKING members by surname key.

    A list, not a single member: two senators can share a surname, and keying
    by surname alone silently evicts one of them.
    """
    by_surname: dict[str, list[dict]] = {}
    for member in members:
        if member["role"] == "SPEAKING":
            by_surname.setdefault(normalize_lnf(member["lnf"]), []).append(member)
    return by_surname


def _resolve_speaker(
    surname: str,
    state_name: str | None,
    speaking: dict[str, list[dict]],
) -> str | None:
    """The bioGuideId for one header, or None when it cannot be resolved.

    Returns None rather than guessing when the surname is unknown, when two
    members share it and the header carries no qualifier, or when the
    qualifier matches no candidate. Callers must treat None as an error.
    """
    candidates = speaking.get(surname, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]["bio"]
    if state_name is None:
        return None
    code = _STATE_CODES.get(state_name)
    if code is None:
        return None
    matches = [c for c in candidates if (c.get("state") or "").upper() == code]
    return matches[0]["bio"] if len(matches) == 1 else None


def attribute_granule(
    text: str,
    members: list[dict],
    carry_in: str | None,
) -> dict[str, str]:
    """Map bioGuideId -> the text that member spoke in this granule.

    `members` is the granule's congMember list; each dict needs 'lnf', 'bio',
    and 'role', plus 'state' (two-letter code) for same-surname members.
    `carry_in` is the bioGuideId of the previous granule's last speaker, or
    None at the start of a day.

    Raises ValueError if any role=SPEAKING member cannot be accounted for, or
    if any speaker header cannot be resolved to a member. Both guards are the
    whole point: without them a missed header silently folds one senator's
    words into another's, or drops them entirely, and every downstream count is
    wrong in a way no total-preserving check can detect.
    """
    speaking = _speaking_by_surname(members)
    speaking_bios = [m["bio"] for group in speaking.values() for m in group]
    attributed: dict[str, list[str]] = {}

    turns = _iter_turns(text)

    # Rule: sole speaking member and no header at all - the whole granule is
    # theirs, the header lives in a prior granule.
    if not turns and len(speaking_bios) == 1:
        return {speaking_bios[0]: text}

    # Rule: text before the first header belongs to the carry-in speaker.
    if turns:
        head = text[: SPEAKER_RE.search(text).start()]
        if head.strip() and carry_in:
            attributed.setdefault(carry_in, []).append(head)

    unresolved: list[str] = []
    for surname, state_name, segment in turns:
        bio = _resolve_speaker(surname, state_name, speaking)
        if bio is None:
            label = f"{surname} of {state_name}" if state_name else surname
            if label not in unresolved:
                unresolved.append(label)
            continue
        attributed.setdefault(bio, []).append(segment)

    if unresolved:
        raise ValueError(
            f"unresolved speaker header(s): {', '.join(unresolved)}; "
            f"their text would be dropped. Known speaking surnames: "
            f"{sorted(speaking)}"
        )

    missing = sorted(bio for bio in speaking_bios if bio not in attributed)
    if missing:
        raise ValueError(
            f"unaccounted role=SPEAKING member(s): {', '.join(missing)}; "
            f"headers found: {sorted({s for s, _, _ in turns})}"
        )

    return {bio: "\n".join(parts) for bio, parts in attributed.items()}


def last_speaker(text: str, members: list[dict]) -> str | None:
    """The bioGuideId of the last member to speak, for carry-in to the next granule.

    None when the last header cannot be resolved; the same-surname qualifier is
    honoured here too, since a wrong carry-in misfiles the head of the NEXT
    granule.
    """
    speaking = _speaking_by_surname(members)
    turns = _iter_turns(text)
    if turns:
        surname, state_name, _ = turns[-1]
        return _resolve_speaker(surname, state_name, speaking)
    speaking_bios = [m["bio"] for group in speaking.values() for m in group]
    if len(speaking_bios) == 1:
        return speaking_bios[0]
    return None
