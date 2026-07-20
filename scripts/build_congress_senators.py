# scripts/build_congress_senators.py
"""Pure transform: attributed speech -> data/congress_senators.csv.

Every senator who served in 2010-2024, not a fixed list of seven. Attribution
is cheap because granule metadata already names the speakers, so restricting the
file would throw away work the "Senate average" needs anyway.

The file is intentionally RAGGED - no rows before a senator takes office. Beat 3
teaches that directly.

Two raw caches feed build(), the same split point build_congress_mentions.py and
build_congress_companions.py both use: Gentzkow supplies every year through
calibrate_splice.OVERLAP_END_YEAR (2016), GovInfo supplies every year after it.
That boundary is matched here on purpose, so all three CSVs describe the same
years from the same sources.

R1 -- carry_in is None ("dropped head text") policy
----------------------------------------------------
congress_speakers.attribute_granule contains `if head.strip() and carry_in:`.
When `carry_in` is None, pre-header text is dropped with NO error raised.
`carry_in` is legitimately None at the start of every CREC day (title and
procedural text precede the first speaker), so that specific case cannot
simply raise -- it is the routine, expected shape of the first granule of
every single day. But the SAME code path also fires mid-day, whenever the
immediately preceding granule was memberless or procedural: that granule's
`last_speaker` returns None, so the NEXT granule's carry_in is None too, and
any real continuation text at its head vanishes exactly like day-start text
would.

Policy chosen here: drop-and-count, never drop-and-forget. build() detects
every occurrence by comparing count_term(text, "china") against the sum of
china mentions actually attributed for that granule. attribute_granule's own
guards (raising on an unresolved header or an unaccounted SPEAKING member)
guarantee any non-zero difference falls into exactly one of two buckets,
distinguished by whether the returned dict is non-empty:

  * `attributed` is non-empty (at least one header resolved) and some china
    is still missing -> the true R1 case: a resolved turn exists, so the
    only place text can have gone missing is the head before it, which
    means carry_in was None. Counted as
    'carry_in_none_granules'/'carry_in_none_china_lost'.
  * `attributed` is empty ({}) -> attribute_granule's own code shows this
    can ONLY happen when the granule has zero role=SPEAKING members at all
    (any other empty-turns shape either resolves via the sole-speaker rule
    or raises). This is NOT an R1 case and is unrelated to carry_in's
    value: a memberless granule (a bill-text insert, an executive
    communication list, a resolution title) legitimately has no speaker to
    credit, with or without a live carry_in. Counted separately as
    'memberless_granules_with_china'/'memberless_china_mentions' so it
    cannot inflate the real R1 signal.

Both buckets are printed by build(), never folded into one number.

Why drop-and-count instead of attributing the head to some other speaker:
this project's own resolution logic (congress_speakers._resolve_speaker)
already refuses to guess an ambiguous same-surname header rather than pick a
plausible-looking candidate -- attribute_granule raises instead. Silently
crediting a None-carry_in head to "whoever spoke last, however many granules
ago" would be the same kind of guess, just one that fails silently instead of
loudly. An honest, counted zero is preferable to a specific but unverifiable
guess. If the first real run shows this loss is large enough to matter, that
is a decision for Heagen to make with real numbers in hand, not something
build() should paper over by picking a speaker with no textual evidence
connecting them to the missing words.

R2 -- discarded same-surname state qualifier, detected not fixed
------------------------------------------------------------------
`_resolve_speaker` intentionally ignores the "of <State>" qualifier whenever
only one SPEAKING member in a granule shares that surname (see
congress_speakers.py's own module docstring: "the qualifier is not required
and is ignored" in that case). That is correct so long as GovInfo's
`congMember` list for a granule never under-reports who spoke in it. Whether
that assumption ever breaks in practice is unknowable without real cached
data -- it depends on a GovInfo rendering quirk this project has not
observed. `_state_qualifier_contradictions` below re-scans each granule's
headers with congress_speakers.SPEAKER_RE (the same public pattern
attribute_granule itself matches against) and flags every turn whose
qualifier names a state that disagrees with the sole same-surname
candidate's own `state` field. It does not change any attribution -- it only
counts and reports, converting an unanswerable question into a number the
first real run will produce.

Gentzkow name -> bioguide reconciliation (2010-2016)
-------------------------------------------------------
The Gentzkow cache carries no bioguide id, only `lastname`/`firstname`/
`state`. GovInfo's own MODS metadata is the one place in this project that
has both a name and a bioguide id for the same person, so
`govinfo_bioguide_roster` harvests a name -> bioguide bridge from GovInfo's
`congMember` lists ACROSS THE FULL CACHED RANGE (not just 2017+) -- reading
only the `members` field, never `text`, so this can never double-count a
china mention. Matching then follows the exact same no-guessing rule
`_resolve_speaker` uses for headers: a surname naming exactly one candidate
resolves outright; a surname shared by more than one candidate resolves only
when the Gentzkow record's `state` field disambiguates to exactly one match;
anything else is counted as unmatched and skipped, never guessed.

This reconciliation carries two irreducible risks, both counted rather than
hidden:
  1. fetch_congress_gentzkow.py's own docstring says the archive's exact
     column layout, including this `state` field's format, is UNVERIFIED --
     nobody who wrote this project has opened hein-daily.zip. Matching
     handles the two plausible formats (a bare 2-letter code or a full state
     name) and treats anything else as "no state information" rather than
     guessing at a third format.
  2. This bridge only knows about senators whose GovInfo congMember entries
     are present in the cache. A senator who served only in 2010-2016 and
     whose GovInfo years are not yet fetched will not be in the roster and
     will be reported as unmatched, not silently dropped -- but also not
     silently invented from partial information.

Display-name risk (flagged, not fixed here)
--------------------------------------------
`_display_name` turns MODS authority-lnf ("Schumer, Charles E.") into
"Charles E. Schumer" -- the formal name, not the commonly used one ("Chuck
Schumer"). Beat 3 and the Task 5 validator check for specific display names
("Chuck Schumer", "Josh Hawley", ...); a first real run is likely to produce
a `senator` column whose formal-name rows do not match those hardcoded
lookups. validate_data.py's congress_senators checks (sentinel presence,
per-year mean, sort order, no duplicates) do not catch this, since none of
them inspect specific names. This needs a nickname/middle-initial
reconciliation pass before the notebook's named lookups will resolve; it is
out of scope here because Step 5 (the only place it could be observed) is
not run.

I2 -- the "Senate average" denominator (fixed here, Heagen's decision 2026-07-20)
-----------------------------------------------------------------------------------
`govinfo_senator_counts` only ever writes a (bio, year) entry into `counts`
when that senator's china count for the year is non-zero (`if n:`). Left
alone, that means `build_senators_frame` -- which used to compute the
sentinel row as the mean of whatever rows happen to exist -- was silently
averaging over "senators who said china at least once that year", not over
"senators serving that year". The published line is labelled "Senate
average" and Beat 3 teaches interns to read the DISTANCE between one
senator's line and it; a mean taken over a self-selecting non-zero
population understates that distance for every senator who spoke about
China less often than the (already inflated) non-zero mean. The old
validator could never catch this because it recomputes the same mean from
the same rows -- build and validator shared one wrong definition.

Fix: `govinfo_bioguide_roster` now also returns `serving_by_year`, a
year -> {bioguide ids} map built from the exact same congMember walk that
already produces the name/bioguide roster (see that function's docstring for
precisely what "serving" means here and what it misses). `build()` passes
that map into `build_senators_frame` as `serving`; for every (bio, year)
pair where `bio` is in `serving[year]` but has no entry in `counts`,
`build_senators_frame` adds a mentions=0 row BEFORE computing the sentinel
average, so the average is the mean over every senator this build can prove
was serving that year -- not just the ones who happened to say "china".

This is deliberately NOT "assume all 100 senators are always covered": a
senator who served the whole year but whose speaking days were never
captured by the cache (a gap day, an under-fetched year that still clears
the manifest floor at the margins, a phantom-marked day) is still MISSED and
still silently narrows the denominator for that one senator-year -- the
proxy shrinks the blast radius of the original bug, it does not eliminate
every version of it. `serving_by_year` requires GovInfo congMember metadata
across the FULL 2010-2024 span (see I6 below), so this fix is only as good
as that coverage.

I6 -- main()'s gate must cover the FULL SENATOR_YEARS span, not just 2017+
-----------------------------------------------------------------------------
`govinfo_bioguide_roster` -- and now `serving_by_year` -- reads GovInfo
congMember metadata across all of SENATOR_YEARS (2010-2024), not just the
post-splice years GovInfo alone supplies china counts for. The old main()
gate only validated 2017-2024 coverage, so a 2017+-only cache passed the
gate while every 2010-2016 senator's roster/serving entry was silently
absent (that senator then resolves via Gentzkow's own name matching, or not
at all, but either way the "serving that year" signal for 2010-2016 was
missing without the gate ever saying so). main() now calls
`congress_cache.govinfo_range_usable` over `min(SENATOR_YEARS)` through
`max(SENATOR_YEARS)`.

I8 -- one cache walker, not four
------------------------------------
`govinfo_bioguide_roster` used to hand-roll its own walk over
`raw_dir/{year}/*.json`, with a bare `except json.JSONDecodeError: continue`
that dropped a malformed day file with NO counter at all -- a direct
violation of this project's counting-discipline rule (dropped data must
always be counted and reported). It now uses the shared
`congress_cache.iter_govinfo_days`, the same walker `govinfo_senator_counts`
already effectively duplicates by hand (that duplication is a known,
separate piece of drift this task does not resolve) and that
build_congress_mentions.py/build_congress_companions.py already use. Skips
are counted by reason ('bad_json', 'phantom_marker') and returned, never
swallowed.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

from calibrate_splice import OVERLAP_END_YEAR
from congress_cache import (
    MIN_REAL_DAYS_PER_YEAR,
    govinfo_range_usable,
    iter_govinfo_days,
)
from congress_speakers import (
    SPEAKER_RE,
    _STATE_CODES,  # single source of truth for the qualifier<->code table;
    # duplicating it here would risk the two tables drifting apart, which
    # is worse than depending on a name-mangled ("private") constant.
    attribute_granule,
    last_speaker,
    normalize_lnf,
)
from congress_tokenize import count_term
from twl_common import (
    CONGRESS_RAW_GENTZKOW,
    CONGRESS_RAW_GOVINFO,
    DATA_DIR,
    SENATOR_YEARS,
)

OUT_PATH = DATA_DIR / "congress_senators.csv"
SENTINEL = "Senate average"

# Cap on how many R2 contradiction examples build() keeps in memory/prints.
# The running count is exact regardless of this cap; only the printed sample
# is truncated.
MAX_CONTRADICTION_EXAMPLES = 20


def build_senators_frame(
    counts: dict[tuple[str, int], int],
    names: dict[str, str],
    serving: dict[int, set[str]],
) -> pd.DataFrame:
    """Turn {(bioguide, year): count} into the deliverable, with the sentinel row.

    `names` maps bioGuideId -> display name. A count for an unknown id raises,
    rather than shipping a chart labelled with a raw bioguide code.

    `serving` maps year -> the set of bioguide ids this build can prove were
    serving that year (see govinfo_bioguide_roster's serving_by_year for
    exactly what that proxy is and what it misses). For every (bio, year) pair
    where `bio` is in `serving[year]` but has no entry in `counts` -- a senator
    who served but never said "china" that year -- a mentions=0 row is added
    BEFORE the "Senate average" sentinel is computed (I2), so the average is
    the mean over every senator known to be serving, not just the ones who
    happened to speak the word. A bio with a zero row still must have a known
    display name in `names`, same as any other row -- an unresolvable name is a
    data problem, not something a zero-fill should paper over.

    `serving` is REQUIRED, deliberately, and pass `{}` if you genuinely have no
    serving data. It was briefly optional with a fallback to the old
    speech-only population, and that is the shape of the I2 bug itself: the
    published line is labelled "Senate average" while the mean is taken over
    the self-selecting subset of senators who happened to say the word. A
    caller that omitted the argument would have silently reproduced it, with no
    error, in the fix for that very defect -- the single most repeated failure
    signature in this project. A missing argument is now a TypeError at the
    call site instead.
    """
    rows = []
    seen: set[tuple[str, int]] = set()
    for (bio, year), count in counts.items():
        rows.append((names[bio], int(year), int(count)))
        seen.add((bio, year))

    if serving is not None:
        for year, bios in serving.items():
            for bio in bios:
                if (bio, year) in seen:
                    continue
                rows.append((names[bio], int(year), 0))

    df = pd.DataFrame(rows, columns=["senator", "year", "mentions"])

    averages = (
        df.groupby("year", as_index=False).mentions.mean().assign(senator=SENTINEL)
    )
    averages["mentions"] = averages.mentions.round().astype(int)

    out = pd.concat([df, averages[["senator", "year", "mentions"]]], ignore_index=True)
    return out.sort_values(["senator", "year"], ignore_index=True)


# --------------------------------------------------------------- helpers


def _fold(text: str) -> str:
    """Strip combining marks so 'LUJÁN' and 'LUJAN' compare equal.

    Mirrors congress_speakers._fold exactly. Duplicated rather than imported
    because it is a private, three-line, dependency-free string operation --
    not attribution logic -- and R2 detection needs to re-fold header text
    the same way congress_speakers does internally, using only the public
    SPEAKER_RE surface.
    """
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def _display_name(lnf: str) -> str:
    """'Rubio, Marco' -> 'Marco Rubio'.

    'Roth Jr., William V.' -> 'William V. Roth Jr.'.
    """
    if "," not in lnf:
        return lnf.strip()
    last, _, first = lnf.partition(",")
    return f"{first.strip()} {last.strip()}".strip()


def _normalize_state_token(raw: str) -> str | None:
    """Best-effort normalize a Gentzkow 'state' field to a 2-letter code.

    fetch_congress_gentzkow.py's own docstring says the archive's exact
    layout, including this field's format, is UNVERIFIED. Handles the two
    plausible formats (a bare 2-letter code, or a full state name) and
    returns None for anything else -- callers must treat None as "no usable
    state information", not guess at a third format.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if len(raw) == 2 and raw.upper() in _STATE_CODES.values():
        return raw.upper()
    return _STATE_CODES.get(raw.title())


def _state_qualifier_contradictions(text: str, members: list[dict]) -> list[str]:
    """R2: flag turns whose 'of <State>' qualifier disagrees with the sole
    same-surname SPEAKING member's own state field.

    Re-scans the granule with SPEAKER_RE (the same public pattern
    attribute_granule matches against) purely to recover the qualifier that
    congress_speakers.split_turns intentionally discards. Does not change
    any attribution: `_resolve_speaker` is correct to ignore the qualifier
    when only one candidate exists, PROVIDED congMember never under-reports
    who spoke. This function is the check for whether that proviso ever
    fails in real data. Returns one human-readable description per
    contradicting turn.
    """
    speaking_by_surname: dict[str, list[dict]] = {}
    for member in members:
        if member.get("role") == "SPEAKING":
            speaking_by_surname.setdefault(normalize_lnf(member["lnf"]), []).append(
                member
            )

    findings: list[str] = []
    for match in SPEAKER_RE.finditer(text):
        surname = _fold(match.group(1)).upper()
        state_name = match.group(2)
        if state_name is None:
            continue
        candidates = speaking_by_surname.get(surname, [])
        if len(candidates) != 1:
            continue  # ambiguous/unknown surnames are attribute_granule's problem
        member = candidates[0]
        code = _STATE_CODES.get(state_name)
        if code is None:
            continue
        actual = (member.get("state") or "").upper()
        if actual and actual != code:
            findings.append(
                f"header claims '{surname} of {state_name}' ({code}) but the "
                f"sole candidate {member.get('bio', '?')} has state={actual}"
            )
    return findings


def govinfo_bioguide_roster(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[
    dict[str, list[dict[str, str]]], dict[str, str], dict[int, set[str]], dict[str, int]
]:
    """Harvest a name -> bioguide bridge, and a serving-by-year proxy, from
    GovInfo congMember metadata.

    Reads ONLY each granule's `members` list, never `text`, so this can never
    contribute to (or double-count) a china mention -- it exists purely to
    give the Gentzkow half a way to resolve names to bioguide ids, and (I2)
    to give build_senators_frame a serving population for the "Senate
    average" denominator. Walks the shared congress_cache.iter_govinfo_days
    walker over the full [start_year, end_year] span (not just the
    post-splice years), since a senator who left office before the splice
    would otherwise never appear in any roster GovInfo could supply, and I6
    requires main() to guarantee that full span is actually cached.

    Returns (roster, bio_to_lnf, serving_by_year, skips).
      * `roster` maps normalize_lnf(lnf) -> a deduplicated list of
        {'bio', 'state', 'lnf'} for every SPEAKING member ever seen under
        that surname key.
      * `bio_to_lnf` maps every bioguide id seen to its most recently
        observed lnf string, for display-name lookup shared by both halves
        of build().
      * `serving_by_year` maps every year in [start_year, end_year] -> the
        set of bioguide ids proxied as "serving that year" by appearing as a
        role=SPEAKING congMember on at least one CACHED day within it. THIS
        IS A PROXY, NOT AN ASSERTION OF THE FULL CHAMBER:
          - it can only ever UNDER-count: a senator who served the entire
            year but whose speaking days were never captured by the cache
            (a gap day, a phantom-marked day, a manifest-complete year that
            is still missing this one senator's specific days) is silently
            absent from the set for that year, and build_senators_frame will
            not give them a zero row -- the same silent narrowing the
            original I2 bug caused, just scoped to one senator-year instead
            of every never-speaking senator.
          - it can never OVER-count: nobody is added without a real granule
            in the cache naming them as a SPEAKING member on a day within
            that year.
        The denominator this produces is therefore "senators this build can
        prove were active from the cache it actually has", not "the 100
        seated senators" -- state that explicitly rather than implying the
        stronger claim.
      * `skips` counts, by reason, every cached day this walk declined to
        use: 'bad_json' (day file failed to parse), 'phantom_marker' (no
        "granules" key) -- via the shared congress_cache walker, so a
        truncated day here is reported with the same discipline as every
        other cache walk in this project instead of being silently dropped
        (see the I8 section of the module docstring).
    """
    by_surname: dict[str, dict[str, dict[str, str]]] = {}
    bio_to_lnf: dict[str, str] = {}
    serving_by_year: dict[int, set[str]] = {
        year: set() for year in range(start_year, end_year + 1)
    }
    skips = {"bad_json": 0, "phantom_marker": 0}
    for day in iter_govinfo_days(raw_dir, start_year, end_year, skips):
        for granule in day.granules:
            for member in granule.get("members", []):
                if member.get("role") != "SPEAKING" or not member.get("bio"):
                    continue
                lnf = member.get("lnf", "")
                if not lnf:
                    continue
                bio = member["bio"]
                surname = normalize_lnf(lnf)
                by_surname.setdefault(surname, {})[bio] = {
                    "bio": bio,
                    "state": (member.get("state") or "").upper(),
                    "lnf": lnf,
                }
                bio_to_lnf[bio] = lnf
                serving_by_year[day.year].add(bio)
    roster = {surname: list(bios.values()) for surname, bios in by_surname.items()}
    return roster, bio_to_lnf, serving_by_year, skips


def match_gentzkow_speaker(
    lastname: str, state: str, roster: dict[str, list[dict[str, str]]]
) -> tuple[str | None, str]:
    """Resolve one Gentzkow record's (lastname, state) to a bioguide id.

    Returns (bio_or_None, reason). reason is one of 'matched',
    'unknown_surname', 'ambiguous_surname_no_state',
    'ambiguous_surname_unresolved_state'. Never guesses: a surname shared by
    more than one roster candidate resolves only when the (best-effort
    normalized) state field disambiguates it to exactly one -- mirroring
    congress_speakers._resolve_speaker's own same-surname policy.
    """
    surname = _fold(lastname).upper().strip()
    candidates = roster.get(surname, [])
    if not candidates:
        return None, "unknown_surname"
    if len(candidates) == 1:
        return candidates[0]["bio"], "matched"
    code = _normalize_state_token(state)
    if code is None:
        return None, "ambiguous_surname_no_state"
    matches = [c for c in candidates if c["state"] == code]
    if len(matches) == 1:
        return matches[0]["bio"], "matched"
    return None, "ambiguous_surname_unresolved_state"


def govinfo_senator_counts(
    raw_dir: Path, start_year: int, end_year: int
) -> tuple[dict[tuple[str, int], int], dict[str, int], list[str]]:
    """Walk GovInfo day-by-day, threading carry_in in page order, and sum
    china mentions per (bioguide, year).

    Reads data/_raw/congress_govinfo/{year}/{package}.json. Each year's
    directory also holds `{package}.phantom.json` marker files; those are
    excluded by checking for the "granules" key, NOT by filename pattern.
    `carry_in` resets to None at the start of every day (title/procedural
    text legitimately precedes the first speaker) and threads forward
    across granules within the day via congress_speakers.last_speaker, in
    the list order GovInfo's MODS file itself gives the granules.

    Returns (counts, skips, contradiction_examples). skips tracks, by
    reason, every day/granule this function declined to fully use:
    'bad_json', 'phantom_marker', 'granule_no_text', the R1 counters
    ('carry_in_none_granules', 'carry_in_none_china_lost'), the
    memberless-granule counters ('memberless_granules_with_china',
    'memberless_china_mentions' -- NOT an R1 case; see module docstring),
    and the R2 counter ('state_qualifier_contradictions'). Any
    attribute_granule ValueError (an unresolved header or an unaccounted
    SPEAKING member -- a real data-quality problem this project's regex has
    not yet seen) is re-raised with the offending package/granule named,
    rather than silently skipped, per this project's raise-don't-guess
    convention.
    """
    counts: dict[tuple[str, int], int] = {}
    skips = {
        "bad_json": 0,
        "phantom_marker": 0,
        "granule_no_text": 0,
        "carry_in_none_granules": 0,
        "carry_in_none_china_lost": 0,
        "memberless_granules_with_china": 0,
        "memberless_china_mentions": 0,
        "state_qualifier_contradictions": 0,
    }
    contradiction_examples: list[str] = []

    for year in range(start_year, end_year + 1):
        year_dir = raw_dir / str(year)
        if not year_dir.is_dir():
            continue
        for path in sorted(year_dir.glob("*.json")):
            try:
                day = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                skips["bad_json"] += 1
                continue
            if "granules" not in day:
                skips["phantom_marker"] += 1
                continue

            carry_in: str | None = None  # reset at the start of every day
            for granule in day["granules"]:
                text = granule.get("text") or ""
                members = granule.get("members", [])
                if not text.strip():
                    skips["granule_no_text"] += 1
                    carry_in = last_speaker(text, members)
                    continue

                try:
                    attributed = attribute_granule(text, members, carry_in)
                except ValueError as exc:
                    raise ValueError(
                        f"{day.get('package', path.stem)} granule "
                        f"{granule.get('granule_id', '?')} ({year}): {exc}"
                    ) from exc

                # attribute_granule's own guards (raise on an unresolved
                # header or an unaccounted SPEAKING member) guarantee any
                # non-zero `lost` below falls into exactly one of two
                # buckets, distinguished by whether `attributed` is empty --
                # see module docstring for the proof.
                total_china = count_term(text, "china")
                attributed_china = sum(
                    count_term(seg, "china") for seg in attributed.values()
                )
                lost = total_china - attributed_china
                if lost > 0:
                    if attributed:
                        # R1: a header resolved, so the only place text can
                        # have gone missing is the head before it -- i.e.
                        # carry_in was None.
                        skips["carry_in_none_granules"] += 1
                        skips["carry_in_none_china_lost"] += lost
                    else:
                        # Not R1: attribute_granule returns {} without
                        # raising ONLY when the granule has zero
                        # role=SPEAKING members at all. This text was never
                        # attributable to anyone, with or without a live
                        # carry_in -- a memberless bill-text insert,
                        # executive communication, or resolution title.
                        skips["memberless_granules_with_china"] += 1
                        skips["memberless_china_mentions"] += lost

                for finding in _state_qualifier_contradictions(text, members):
                    skips["state_qualifier_contradictions"] += 1
                    if len(contradiction_examples) < MAX_CONTRADICTION_EXAMPLES:
                        contradiction_examples.append(
                            f"{day.get('package', path.stem)}/"
                            f"{granule.get('granule_id', '?')}: {finding}"
                        )

                for bio, segment in attributed.items():
                    n = count_term(segment, "china")
                    if n:
                        counts[(bio, year)] = counts.get((bio, year), 0) + n

                carry_in = last_speaker(text, members)

    return counts, skips, contradiction_examples


def gentzkow_senator_counts(
    raw_dir: Path,
    start_year: int,
    end_year: int,
    roster: dict[str, list[dict[str, str]]],
) -> tuple[dict[tuple[str, int], int], dict[str, int]]:
    """Sum china mentions per (bioguide, year) over Gentzkow Senate speeches.

    Reads data/_raw/congress_gentzkow/speeches_senate_{congress}.jsonl. Each
    record's `date` field (YYYYMMDD) determines its year rather than the
    congress number in the filename. Every record is resolved to a bioguide
    id via match_gentzkow_speaker (see module docstring for the
    reconciliation policy and its risks); a record that cannot be resolved
    is counted and skipped, never guessed.

    Returns (counts, skips). skips tracks, by reason, every record this
    function declined to count: 'bad_json', 'bad_date', 'out_of_range', plus
    match_gentzkow_speaker's own failure reasons ('unknown_surname',
    'ambiguous_surname_no_state', 'ambiguous_surname_unresolved_state').
    """
    counts: dict[tuple[str, int], int] = {}
    skips = {
        "bad_json": 0,
        "bad_date": 0,
        "out_of_range": 0,
        "unknown_surname": 0,
        "ambiguous_surname_no_state": 0,
        "ambiguous_surname_unresolved_state": 0,
    }
    for path in sorted(raw_dir.glob("speeches_senate_*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    skips["bad_json"] += 1
                    continue
                date = record.get("date", "")
                if len(date) < 4 or not date[:4].isdigit():
                    skips["bad_date"] += 1
                    continue
                year = int(date[:4])
                if year < start_year or year > end_year:
                    skips["out_of_range"] += 1
                    continue
                n = count_term(record.get("text", ""), "china")
                if not n:
                    continue
                bio, reason = match_gentzkow_speaker(
                    record.get("lastname", ""), record.get("state", ""), roster
                )
                if bio is None:
                    skips[reason] = skips.get(reason, 0) + 1
                    continue
                counts[(bio, year)] = counts.get((bio, year), 0) + n
    return counts, skips


def build() -> pd.DataFrame:
    """Walk both raw caches, attribute china mentions per senator per year, and
    write OUT_PATH.

    The Gentzkow/GovInfo overlap is partitioned exactly the way
    build_congress_mentions.py's and build_congress_companions.py's build()
    functions partition it: Gentzkow supplies every year through
    calibrate_splice.OVERLAP_END_YEAR (2016), GovInfo supplies every year
    after it. See the module docstring for the R1 (carry_in-is-None) policy,
    the R2 (state-qualifier contradiction) check, and the Gentzkow name ->
    bioguide reconciliation and its risks.

    Every skipped/dropped/unmatched item is counted by reason and printed,
    per this project's rule that dropped data must be reported, never
    silently discarded.
    """
    start_year, end_year = min(SENATOR_YEARS), max(SENATOR_YEARS)

    roster, bio_to_lnf, serving_by_year, roster_skips = govinfo_bioguide_roster(
        CONGRESS_RAW_GOVINFO, start_year, end_year
    )
    print(
        f"GovInfo roster: {len(bio_to_lnf)} bioguide id(s) harvested from "
        "congMember metadata"
    )
    print(
        "GovInfo roster walk skipped: "
        f"{roster_skips['bad_json']} bad JSON day(s), "
        f"{roster_skips['phantom_marker']} phantom marker(s)"
    )

    govinfo_counts, govinfo_skips, contradictions = govinfo_senator_counts(
        CONGRESS_RAW_GOVINFO, OVERLAP_END_YEAR + 1, end_year
    )
    gentzkow_counts, gentzkow_skips = gentzkow_senator_counts(
        CONGRESS_RAW_GENTZKOW, start_year, OVERLAP_END_YEAR, roster
    )

    print(
        "GovInfo cache skipped: "
        f"{govinfo_skips['phantom_marker']} phantom marker(s), "
        f"{govinfo_skips['bad_json']} bad JSON day(s), "
        f"{govinfo_skips['granule_no_text']} granule(s) with no text"
    )
    print(
        "R1 (carry_in is None, head text dropped): "
        f"{govinfo_skips['carry_in_none_granules']} granule(s), "
        f"{govinfo_skips['carry_in_none_china_lost']} china mention(s) lost"
    )
    print(
        "Memberless granules (zero SPEAKING members, NOT an R1 case -- "
        "text with no speaker to credit either way): "
        f"{govinfo_skips['memberless_granules_with_china']} granule(s), "
        f"{govinfo_skips['memberless_china_mentions']} china mention(s) "
        "unattributable"
    )
    print(
        "R2 (same-surname state-qualifier contradictions): "
        f"{govinfo_skips['state_qualifier_contradictions']} turn(s)"
    )
    if contradictions:
        print("  examples:")
        for line in contradictions:
            print(f"    {line}")
    print(
        "Gentzkow cache skipped: "
        f"{gentzkow_skips['bad_json']} bad JSON line(s), "
        f"{gentzkow_skips['bad_date']} bad/missing date(s), "
        f"{gentzkow_skips['out_of_range']} record(s) outside "
        f"{start_year}-{OVERLAP_END_YEAR}, "
        f"{gentzkow_skips['unknown_surname']} unknown surname(s), "
        f"{gentzkow_skips['ambiguous_surname_no_state']} ambiguous surname(s) "
        "with no usable state field, "
        f"{gentzkow_skips['ambiguous_surname_unresolved_state']} ambiguous "
        "surname(s) whose state did not resolve to exactly one candidate"
    )

    counts: dict[tuple[str, int], int] = dict(govinfo_counts)
    for key, n in gentzkow_counts.items():
        counts[key] = counts.get(key, 0) + n

    names = {bio: _display_name(lnf) for bio, lnf in bio_to_lnf.items()}
    missing_names = sorted({bio for bio, _ in counts if bio not in names})
    if missing_names:
        raise ValueError(
            f"counts reference bioguide id(s) with no known display name: "
            f"{missing_names}; govinfo_bioguide_roster should have covered "
            "every bio that can appear here"
        )

    df = build_senators_frame(counts, names, serving_by_year)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    return df


def main() -> int:
    missing = []
    # I6: govinfo_bioguide_roster (and, via it, the I2 serving-by-year proxy)
    # reads GovInfo congMember metadata across the FULL SENATOR_YEARS span,
    # not just the post-splice years GovInfo supplies china counts for. The
    # gate used to check only OVERLAP_END_YEAR+1..max(SENATOR_YEARS)
    # (2017-2024), so a 2017+-only cache passed while every pre-2017
    # senator's roster/serving entry was silently absent. Gate on the whole
    # span the roster walk actually needs, using the shared manifest-based
    # completeness check (congress_cache.govinfo_range_usable) rather than a
    # flat day floor -- see that function's docstring for why presence is
    # not completeness.
    govinfo_start, govinfo_end = min(SENATOR_YEARS), max(SENATOR_YEARS)
    usable, bad_years = govinfo_range_usable(
        CONGRESS_RAW_GOVINFO, govinfo_start, govinfo_end
    )
    if not usable:
        missing.append(
            f"  - GovInfo cache missing or incomplete for {govinfo_start}-"
            f"{govinfo_end} (need >= {MIN_REAL_DAYS_PER_YEAR} real cached "
            f"days per year, verified against each year's fetch manifest; "
            f"short, absent, or unmanifested: {bad_years}): "
            f"{CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py "
            f"--start-year {govinfo_start} --end-year {govinfo_end}"
        )
    if not CONGRESS_RAW_GENTZKOW.exists() or not any(
        CONGRESS_RAW_GENTZKOW.glob("speeches_senate_*.jsonl")
    ):
        missing.append(
            f"  - Gentzkow cache missing or empty: {CONGRESS_RAW_GENTZKOW}\n"
            "    Produce it with: python scripts/fetch_congress_gentzkow.py"
        )
    if missing:
        print(
            "Cannot build congress_senators.csv: required raw cache(s) are "
            "absent.\n" + "\n".join(missing) + "\n\n"
            "These are long-running downloads (the GovInfo pull is roughly "
            "110k requests; the Gentzkow archive is 11.4 GB) and are not "
            "run automatically. See the scripts above for what each one "
            "produces and where."
        )
        return 1

    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
