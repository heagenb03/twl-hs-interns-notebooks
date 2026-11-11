# scripts/tests/test_splice_completeness.py
"""C2: a partially-fetched overlap must never yield a verdict.

The failure this guards is not "the gate fails to fire". It is that the gate
AFFIRMATIVELY CERTIFIES the join with maximum confidence. A uniformly partial
GovInfo cache -- an interrupted download, the single likeliest outcome of a
110k-request unattended job -- produces a perfectly STABLE ratio, which is the
exact signature choose_strategy reads as safe:

    Gentzkow complete = 1000/yr, GovInfo interrupted = 102/yr
    -> mean_ratio 0.1020, cv 0.0000, VERDICT 'scale'

build() then multiplies all 8 terms 1990-2016 by 0.102 and concatenates the
full-resolution 2017+ half: a 9.8x step at exactly the splice year, 280 rows,
validator-clean, and indistinguishable from Beat 1's headline finding.

The d36f627 gate fix does not cover this. That fix stopped a bad `concatenate`.
This is a bad `scale`, and `scale` is the one branch that actively rewrites the
numbers. "No correct verdict moves" held only under an assumption of complete
caches that nothing in build() checked.

The remedy cannot live in choose_strategy: the ratios really are stable, and
the counts really are what the cache contains. Completeness has to be asserted
about the CACHE, before any comparison is computed.
"""
import json

import pytest

import calibrate_splice
from calibrate_splice import (
    OVERLAP_END_YEAR,
    OVERLAP_START_YEAR,
    OverlapIncompleteError,
    choose_strategy,
    compare_overlap,
    require_complete_overlap,
)
from congress_cache import MIN_REAL_DAYS_PER_YEAR, write_manifest

OVERLAP_YEARS = range(OVERLAP_START_YEAR, OVERLAP_END_YEAR + 1)


SESSION_DAYS = 30  # stands in for a full Senate year (~150); kept small for test speed


def _fill_govinfo(root, years, days_per_year=SESSION_DAYS, expected=SESSION_DAYS):
    for year in years:
        year_dir = root / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        packages = [f"CREC-{year}-{i:03d}" for i in range(expected)]
        write_manifest(root, year, packages)
        for pkg in packages[:days_per_year]:
            (year_dir / f"{pkg}.json").write_text(
                json.dumps({"package": pkg, "granules": [{"text": "china trade"}]}),
                encoding="utf-8",
            )


def _fill_gentzkow(root, years, speeches_per_year):
    root.mkdir(parents=True, exist_ok=True)
    with (root / "speeches_senate_100.jsonl").open("w", encoding="utf-8") as fh:
        for year in years:
            for i in range(speeches_per_year):
                fh.write(json.dumps(
                    {"date": f"{year}0104", "text": "china trade", "speech_id": f"{year}{i}"}
                ) + "\n")


def test_the_uniformly_partial_cache_produces_a_confident_scale_verdict(tmp_path):
    """The trap itself, reproduced. This is what the gate has to catch, and it
    proves the gate cannot be built out of the comparison statistics."""
    comparison = compare_overlap(
        {y: 1000 for y in OVERLAP_YEARS},
        {y: 102 for y in OVERLAP_YEARS},
    )
    assert comparison["cv"] == pytest.approx(0.0, abs=1e-12)
    assert choose_strategy(comparison) == "scale"
    assert comparison["mean_ratio"] == pytest.approx(0.102)


def test_complete_overlap_passes(tmp_path):
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    _fill_govinfo(govinfo, OVERLAP_YEARS)
    _fill_gentzkow(gentzkow, OVERLAP_YEARS, calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR)
    require_complete_overlap(gentzkow, govinfo)


def test_a_short_govinfo_year_blocks_the_verdict(tmp_path):
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    _fill_govinfo(govinfo, [y for y in OVERLAP_YEARS if y != 2005])
    _fill_govinfo(govinfo, [2005], days_per_year=25)
    _fill_gentzkow(gentzkow, OVERLAP_YEARS, calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR)
    with pytest.raises(OverlapIncompleteError) as exc:
        require_complete_overlap(gentzkow, govinfo)
    assert "2005" in str(exc.value)


def test_a_uniformly_partial_govinfo_cache_blocks_the_verdict(tmp_path):
    """Every overlap year present, every one short. Presence checks pass this."""
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    _fill_govinfo(govinfo, OVERLAP_YEARS, days_per_year=25)
    _fill_gentzkow(gentzkow, OVERLAP_YEARS, calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR)
    with pytest.raises(OverlapIncompleteError):
        require_complete_overlap(gentzkow, govinfo)


def test_a_truncated_gentzkow_half_blocks_the_verdict(tmp_path):
    """The same trap from the other side, opposite sign. A truncated Gentzkow
    half makes GovInfo look uniformly LARGER, which is equally stable and
    equally certifiable."""
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    _fill_govinfo(govinfo, OVERLAP_YEARS)
    _fill_gentzkow(gentzkow, OVERLAP_YEARS, 1)
    with pytest.raises(OverlapIncompleteError) as exc:
        require_complete_overlap(gentzkow, govinfo)
    assert "gentzkow" in str(exc.value).lower()


def test_a_missing_gentzkow_year_blocks_the_verdict(tmp_path):
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    _fill_govinfo(govinfo, OVERLAP_YEARS)
    _fill_gentzkow(gentzkow, [y for y in OVERLAP_YEARS if y != 2011],
                   calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR)
    with pytest.raises(OverlapIncompleteError) as exc:
        require_complete_overlap(gentzkow, govinfo)
    assert "2011" in str(exc.value)


def test_the_error_names_the_offending_years_not_just_a_count(tmp_path):
    """After hours of downloading, "the cache is incomplete" is not actionable."""
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    _fill_govinfo(govinfo, [y for y in OVERLAP_YEARS if y not in (1998, 2003)])
    _fill_gentzkow(gentzkow, OVERLAP_YEARS, calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR)
    with pytest.raises(OverlapIncompleteError) as exc:
        require_complete_overlap(gentzkow, govinfo)
    message = str(exc.value)
    assert "1998" in message and "2003" in message


def test_an_empty_cache_blocks_the_verdict(tmp_path):
    govinfo, gentzkow = tmp_path / "gov", tmp_path / "gen"
    govinfo.mkdir()
    gentzkow.mkdir()
    with pytest.raises(OverlapIncompleteError):
        require_complete_overlap(gentzkow, govinfo)


def test_the_gentzkow_floor_is_not_silently_zero():
    assert calibrate_splice.MIN_GENTZKOW_SPEECHES_PER_YEAR > 0
