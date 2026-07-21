# scripts/build_congress_senators.py
"""Pure transform: attributed speech -> data/congress_senators.csv.

Every senator who served in 2010-2024, not a fixed list of seven. Attribution
is cheap because granule metadata already names the speakers, so restricting the
file would throw away work the "Senate average" needs anyway.

The file is intentionally RAGGED - no rows before a senator takes office. Beat 3
teaches that directly.

One raw cache feeds build() now: GovInfo CREC granules,
data/_raw/congress_govinfo/{year}/{pkg}.json, across the whole of
SENATOR_YEARS (2010-2024).

This used to also read a Gentzkow-Shapiro-Taddy Senate-speeches cache for
2010-2016, splicing it against GovInfo's 2017-2024 half at the same boundary
build_congress_mentions.py and build_congress_companions.py used. calibrate_
splice's own walk of the 1994-2016 overlap returned `govinfo_only` on
2026-07-21 -- GovInfo counts a consistent ~2x Gentzkow because the
Congressional Record interleaves verbatim legislative text with floor speech
inside the same granule, and Gentzkow extracts only the spoken portions. The
splice was abandoned rather than scaled; see twl_common.GOVINFO_ERA_START.
Because SENATOR_YEARS already starts at GOVINFO_ERA_START (2010), the whole
series -- not just a widened prefix, as for mentions/companions -- now comes
from GovInfo alone, and this module never reads the Gentzkow cache at all: the
Gentzkow name -> bioguide reconciliation, `match_gentzkow_speaker`, and the
2010-2016 Gentzkow counting half described lower in this docstring no longer
exist. The GovInfo coverage gate in build() is unrelated to that decision and
stays: an interrupted GovInfo pull still produces validator-clean,
plausible-looking, wrong output.

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

Fix: `govinfo_bioguide_roster` also returns `serving_by_year`, a
year -> {bioguide ids} map built from the exact same congMember walk that
already produces the bioguide -> display-name map (see that function's
docstring for precisely what "serving" means here and what it misses).
`build()` passes that map into `build_senators_frame` as `serving`; for every (bio, year)
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

I6 -- the coverage gate must cover the FULL SENATOR_YEARS span, not just 2017+
-----------------------------------------------------------------------------
`govinfo_bioguide_roster` -- and now `serving_by_year` -- reads GovInfo
congMember metadata across all of SENATOR_YEARS (2010-2024), not just the
post-splice years GovInfo alone used to supply china counts for. The old gate
only validated 2017-2024 coverage, so a 2017+-only cache passed the gate
while every 2010-2016 senator's roster/serving entry was silently absent.
That was already a real gap before Task 3b, and it matters even more now:
since the splice is gone and GovInfo alone supplies EVERY year (see the
module docstring's top section), a 2017+-only cache would also silently
produce a truncated CHINA-COUNT series for 2010-2016, not just a missing
roster/serving entry. build()'s coverage gate calls
`congress_cache.govinfo_range_usable` over `min(SENATOR_YEARS)` through
`max(SENATOR_YEARS)` -- the same span the roster walk and the counting walk
both need -- so one gate now protects both.

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

from congress_cache import (
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
    CONGRESS_RAW_GOVINFO,
    CongressDataRefusalError,
    DATA_DIR,
    GOVINFO_ERA_START,
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
) -> tuple[dict[str, str], dict[int, set[str]], dict[str, int]]:
    """Harvest a bioguide -> display-name map and a serving-by-year proxy from
    GovInfo congMember metadata.

    Reads ONLY each granule's `members` list, never `text`, so this can never
    contribute to (or double-count) a china mention -- it exists purely to
    resolve display names for build_senators_frame, and (I2) to give it a
    serving population for the "Senate average" denominator. Walks the shared
    congress_cache.iter_govinfo_days walker over the full [start_year,
    end_year] span, since the GovInfo coverage gate (I6) is what guarantees
    that full span is actually cached.

    This used to also build a surname -> bioguide-candidates roster, so that
    Gentzkow's name-only speech records could be resolved to a bioguide id
    (see match_gentzkow_speaker, removed in Task 3b along with the Gentzkow
    half of this build -- see the module docstring). Every senator now comes
    from GovInfo's own congMember metadata, which already carries a bioguide
    id directly, so that surname bridge has nothing left to resolve.

    Returns (bio_to_lnf, serving_by_year, skips).
      * `bio_to_lnf` maps every bioguide id seen to its most recently
        observed lnf string, for display-name lookup.
      * `serving_by_year` maps every year in [start_year, end_year] -> the
        set of bioguide ids proxied as "serving that year" by appearing as a
        role=SPEAKING congMember on at least one CACHED day within it. THIS
        IS A PROXY, NOT AN ASSERTION OF THE FULL CHAMBER:
          - it can only ever UNDER-count: a senator who served the entire
            year but whose speaking days were never captured by the cache
            (a gap day, a phantom-marked day, a manifest-complete year that
            is still missing this one senator's specific days) is still
            silently absent from the set for that year, and
            build_senators_frame will not give them a zero row -- the same
            silent narrowing the original I2 bug caused, just scoped to one
            senator-year instead of every never-speaking senator.
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
                bio_to_lnf[bio] = lnf
                serving_by_year[day.year].add(bio)
    return bio_to_lnf, serving_by_year, skips


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


def build() -> pd.DataFrame:
    """Walk the GovInfo cache, attribute china mentions per senator per year,
    and write OUT_PATH. No splice: see module docstring.

    See the module docstring for the R1 (carry_in-is-None) policy and the R2
    (state-qualifier contradiction) check -- both are GovInfo attribution
    mechanics, unrelated to the splice question, and both still apply exactly
    as before.

    Two gates guard this, and they are not the same gate. Both raise
    CongressDataRefusalError -- one domain exception for "this build must not
    run against this data" -- rather than two different refusal idioms:

      * The floor guard below is static -- it checks SENATOR_YEARS itself,
        not the cache. It exists so that if SENATOR_YEARS is ever widened
        back below GOVINFO_ERA_START, this fails loudly instead of silently
        building a truncated or empty series for the pre-coverage years.
      * The coverage gate (govinfo_range_usable) is the one that survives
        from before the splice was dropped: an interrupted GovInfo pull is
        still the likeliest failure, and it still produces validator-clean,
        plausible-looking, wrong output -- the exact failure this project
        keeps naming. It has to live here in build(), not only in main(), so
        that calling build() directly never bypasses it. It also subsumes
        the old I6 gate: since GovInfo alone now supplies every year (not
        just the roster/serving signal), this single gate covers both the
        counting walk and the roster walk over the same SENATOR_YEARS span.
        main() below catches CongressDataRefusalError and turns it into a
        return code, so its own contract (return 1, never propagate) matches
        build_congress_mentions and test_build_cache_gates.py's expectations.

    Every skipped/dropped item is counted by reason and printed, per this
    project's rule that dropped data must be reported, never silently
    discarded.
    """
    start_year, end_year = min(SENATOR_YEARS), max(SENATOR_YEARS)

    # No splice: the 1994-2016 overlap calibrated to `govinfo_only` on
    # 2026-07-21, so the Gentzkow half is not read. See twl_common.
    # GOVINFO_ERA_START. The COVERAGE gate below is unrelated to the splice
    # and must stay: an interrupted GovInfo pull still yields validator-clean
    # wrong output.
    if start_year < GOVINFO_ERA_START:
        raise CongressDataRefusalError(
            f"SENATOR_YEARS starts at {start_year}, before GovInfo coverage "
            f"({GOVINFO_ERA_START}). Pre-{GOVINFO_ERA_START} years need a "
            f"Gentzkow splice, which was abandoned. Restore the splice or "
            f"raise the range floor -- do not let these years build empty."
        )

    usable, bad_years = govinfo_range_usable(CONGRESS_RAW_GOVINFO, start_year, end_year)
    if not usable:
        raise CongressDataRefusalError(
            "Cannot build congress_senators.csv: GovInfo cache incomplete "
            f"for {start_year}-{end_year}. Missing or short: {bad_years}\n"
            f"    Cache: {CONGRESS_RAW_GOVINFO}\n"
            "    Produce it with: python scripts/fetch_congress_govinfo.py "
            f"--start-year {start_year} --end-year {end_year}"
        )

    bio_to_lnf, serving_by_year, roster_skips = govinfo_bioguide_roster(
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
        CONGRESS_RAW_GOVINFO, start_year, end_year
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

    names = {bio: _display_name(lnf) for bio, lnf in bio_to_lnf.items()}
    missing_names = sorted({bio for bio, _ in govinfo_counts if bio not in names})
    if missing_names:
        raise ValueError(
            f"counts reference bioguide id(s) with no known display name: "
            f"{missing_names}; govinfo_bioguide_roster should have covered "
            "every bio that can appear here"
        )

    df = build_senators_frame(govinfo_counts, names, serving_by_year)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    return df


def main() -> int:
    # build() raises CongressDataRefusalError itself for both refusals (an
    # incomplete GovInfo cache and a pre-coverage year range) -- so calling
    # build() directly cannot bypass either gate; see its docstring. Caught
    # and translated back into a return code here so main()'s own contract --
    # return 1, never propagate -- matches every other build's main() and
    # test_build_cache_gates.py's expectations.
    try:
        build()
    except CongressDataRefusalError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
