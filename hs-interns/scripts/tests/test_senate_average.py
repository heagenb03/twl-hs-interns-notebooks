# scripts/tests/test_senate_average.py
"""Tests for I2 (Senate average must include zero-mention serving senators)
and I6 (build()'s coverage gate must cover the full SENATOR_YEARS span, not
just the post-splice years).

I2, verbatim from the review ledger: govinfo_senator_counts only writes a row
when a senator's china count is non-zero, so the published "Senate average"
line was silently the average among senators who mentioned China AT LEAST
ONCE, not the average among all serving senators -- and the validator could
never catch it because it recomputes the mean from the same non-zero rows.

Heagen's decision (2026-07-20): every senator known to be serving in a year
gets a mentions=0 row for that year if they have no counted china mentions,
so the average is over the full serving population. "Serving" is PROXIED by
presence in GovInfo congMember metadata for that year -- see
govinfo_bioguide_roster's docstring for exactly what that proxy misses (a
senator who served but never surfaced as a SPEAKING congMember on any cached
day that year is missed, not fabricated).

I6: the old gate validated GovInfo coverage only for 2017-2024 (the
post-splice half), but govinfo_bioguide_roster -- and now the serving-set
this file's I2 fix depends on -- walks the FULL 2010-2024 SENATOR_YEARS span.
A 2017+-only cache passed the old gate while every pre-2017 senator's roster
entry (and now serving flag) silently went missing.

Updated for Task 3b: the 1994-2016 Gentzkow/GovInfo overlap calibrated to
`govinfo_only` on 2026-07-21 and the splice was abandoned (see twl_common.
GOVINFO_ERA_START). SENATOR_YEARS is already entirely within GovInfo
coverage, so build_congress_senators no longer reads the Gentzkow cache at
all, `govinfo_bioguide_roster` no longer returns a name->bioguide roster (it
existed only to resolve Gentzkow's name-only records), and the I6 gate lives
in build() itself (govinfo_range_usable over the whole SENATOR_YEARS span)
rather than in a separate main()-level check -- the same shape Task 2/3a
already established for mentions/companions.
"""
from __future__ import annotations

import json

import build_congress_senators
from build_congress_senators import build_senators_frame, govinfo_bioguide_roster
from congress_cache import write_manifest

# --------------------------------------------------------------- build_senators_frame


def test_zero_mention_serving_senator_gets_a_zero_row():
    counts = {("A001", 2020): 6}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}
    serving = {2020: {"A001", "A002"}}
    df = build_senators_frame(counts, names, serving)
    bob = df[(df.senator == "Bob Brown") & (df.year == 2020)]
    assert len(bob) == 1
    assert bob.mentions.iloc[0] == 0


def test_average_is_over_all_serving_senators_not_just_nonzero():
    # 3 serving senators, china counts 6/0/0 -> average must be 2, not 6.
    counts = {("A001", 2020): 6}
    names = {
        "A001": "Alice Adams",
        "A002": "Bob Brown",
        "A003": "Carol Chen",
    }
    serving = {2020: {"A001", "A002", "A003"}}
    df = build_senators_frame(counts, names, serving)
    avg = df[(df.senator == "Senate average") & (df.year == 2020)].mentions.iloc[0]
    assert avg == 2
    assert avg != 6


def test_average_changes_when_a_zero_mention_serving_senator_is_added():
    # This is the test that would have caught the original bug: adding a
    # serving senator who never says "china" must move the average, because
    # govinfo_senator_counts previously never wrote a row for that senator at
    # all (its `if n:` guard) and the mean silently skipped them.
    counts = {("A001", 2020): 6}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}

    df_without = build_senators_frame(counts, names, {2020: {"A001"}})
    avg_without = df_without[
        (df_without.senator == "Senate average") & (df_without.year == 2020)
    ].mentions.iloc[0]

    df_with = build_senators_frame(counts, names, {2020: {"A001", "A002"}})
    avg_with = df_with[
        (df_with.senator == "Senate average") & (df_with.year == 2020)
    ].mentions.iloc[0]

    assert avg_without == 6
    assert avg_with == 3
    assert avg_without != avg_with


def test_senator_absent_from_serving_set_gets_no_zero_row():
    # The roster/serving set is a PROXY, not an assertion that all 100 seats
    # are accounted for. A senator who never surfaces in any captured
    # GovInfo congMember list for a year must not get a fabricated zero row
    # -- that would silently invent a "serving" claim from nothing.
    counts = {("A001", 2020): 6}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}
    serving = {2020: {"A001"}}  # A002 never appears in any congMember list
    df = build_senators_frame(counts, names, serving)
    assert len(df[df.senator == "Bob Brown"]) == 0


def test_sentinel_row_is_emitted_exactly_once_per_year():
    counts = {("A001", 2020): 6, ("A001", 2021): 4}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}
    serving = {2020: {"A001", "A002"}, 2021: {"A001"}}
    df = build_senators_frame(counts, names, serving)
    sentinel = df[df.senator == build_congress_senators.SENTINEL]
    assert sorted(sentinel.year) == [2020, 2021]
    assert len(sentinel) == 2


def test_empty_serving_adds_no_zero_rows():
    """`serving` is REQUIRED but may be empty. This was briefly an OPTIONAL
    parameter that fell back to the speech-only population when omitted -- a
    silent reproduction of the I2 bug, available by forgetting an argument, in
    the fix for that very bug. Passing {} is now an explicit statement that no
    serving data is available, not something a caller does by accident.
    """
    counts = {("A001", 2020): 10, ("A002", 2020): 20}
    names = {"A001": "Alice Adams", "A002": "Bob Brown"}
    df = build_senators_frame(counts, names, {})
    avg = df[(df.senator == "Senate average") & (df.year == 2020)].mentions.iloc[0]
    assert avg == 15
    assert len(df[df.senator != "Senate average"]) == 2  # no zero rows invented


# --------------------------------------------------------------- govinfo_bioguide_roster


def test_roster_serving_by_year_matches_congmember_presence():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        year_dir = root / "2020"
        year_dir.mkdir(parents=True)
        (year_dir / "CREC-2020-01-03.json").write_text(
            json.dumps(
                {
                    "package": "CREC-2020-01-03",
                    "granules": [
                        {
                            "text": "Mr. ADAMS. china.",
                            "members": [
                                {
                                    "role": "SPEAKING",
                                    "bio": "A001",
                                    "lnf": "Adams, Alice",
                                    "state": "OH",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        bio_to_lnf, serving_by_year, skips = govinfo_bioguide_roster(root, 2020, 2020)
        assert serving_by_year[2020] == {"A001"}
        assert skips == {"bad_json": 0, "phantom_marker": 0}


def test_roster_counts_bad_json_and_phantom_without_crashing():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        year_dir = root / "2020"
        year_dir.mkdir(parents=True)
        (year_dir / "CREC-2020-01-01.json").write_text("{not json", encoding="utf-8")
        (year_dir / "CREC-2020-01-02.phantom.json").write_text(
            json.dumps({"package": "CREC-2020-01-02", "reason": "not found"}),
            encoding="utf-8",
        )
        bio_to_lnf, serving_by_year, skips = govinfo_bioguide_roster(root, 2020, 2020)
        assert skips == {"bad_json": 1, "phantom_marker": 1}
        assert serving_by_year[2020] == set()


# --------------------------------------------------------------- coverage gate (I6)


def _write_govinfo_year(root, year, n=25):
    # Every real day carries one resolvable speaker turn so that, in the test
    # that lets main() run all the way through build(), attribute_granule has
    # someone to credit and govinfo_bioguide_roster has a SPEAKING member to
    # harvest -- a fully memberless fixture would leave both `counts` and
    # `serving_by_year` empty and crash on the empty-frame edge case, which
    # is not what either test here is checking.
    packages = [f"CREC-{year}-{i:03d}" for i in range(n)]
    write_manifest(root, year, packages)
    year_dir = root / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    for pkg in packages:
        (year_dir / f"{pkg}.json").write_text(
            json.dumps(
                {
                    "package": pkg,
                    "granules": [
                        {
                            "text": "Mr. ADAMS. china trade.",
                            "members": [
                                {
                                    "role": "SPEAKING",
                                    "bio": "A001",
                                    "lnf": "Adams, Alice",
                                    "state": "OH",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )


def test_main_refuses_when_govinfo_cache_does_not_cover_2010_2016(tmp_path, monkeypatch):
    govinfo = tmp_path / "congress_govinfo"
    govinfo.mkdir()
    # Fully cover only the post-splice years -- the old (I6-buggy) gate only
    # checked 2017-2024, so this exact cache would previously have passed
    # even though govinfo_bioguide_roster (and, now, the china-count walk
    # itself -- GovInfo alone supplies every year) needs 2010-2016 too.
    for year in range(2017, 2025):
        _write_govinfo_year(govinfo, year)

    monkeypatch.setattr(
        build_congress_senators, "CONGRESS_RAW_GOVINFO", govinfo, raising=False
    )

    assert build_congress_senators.main() == 1


def test_main_succeeds_when_the_full_2010_2024_span_is_covered(
    tmp_path, monkeypatch, capsys
):
    """Task 3b: with the splice gone, a fully-covered 2010-2024 GovInfo cache
    is now sufficient on its own -- no Gentzkow cache, no overlap calibration.
    This replaces the old test that asserted main() stopped on
    OverlapIncompleteError once the I6 cache gate passed; that next gate
    (calibrate_splice.resolve_strategy) no longer exists in this module at
    all (see build_congress_senators's module docstring), so the same
    2010-2024 GovInfo cache that used to only clear the FIRST of two gates
    now clears the only gate and main() succeeds outright.
    """
    govinfo = tmp_path / "congress_govinfo"
    govinfo.mkdir()
    for year in range(2010, 2025):
        _write_govinfo_year(govinfo, year)

    monkeypatch.setattr(
        build_congress_senators, "CONGRESS_RAW_GOVINFO", govinfo, raising=False
    )

    out_path = tmp_path / "congress_senators.csv"
    monkeypatch.setattr(build_congress_senators, "OUT_PATH", out_path, raising=False)

    assert build_congress_senators.main() == 0
    assert out_path.exists()
    assert "Cannot build congress_senators.csv" not in capsys.readouterr().out
