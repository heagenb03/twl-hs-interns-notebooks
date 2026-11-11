# scripts/tests/test_build_cache_gates.py
"""C1 at the main() level: a partial cache must not reach build().

The completeness logic itself is covered in test_congress_cache.py. What failed
here was the WIRING -- build_congress_senators already had a per-year floor and
its docstring named `_govinfo_years_present` as the false positive it defends
against, but nobody applied it back to the other two builds. Three builds, three
different completeness gates. So these tests exercise main(), not the helper.

The reproduction is the real one: a single leftover smoke-test day. With the old
presence check, build_congress_companions.main() ran to completion and wrote a
validator-clean 40-row congress_companions.csv whose 2020s row -- Beat 2's whole
2020s teaching claim -- was one day of Senate business.
"""
import json

import pytest

import build_congress_companions
import build_congress_mentions
import build_congress_senators
from congress_cache import MIN_REAL_DAYS_PER_YEAR

BUILDS = [
    (build_congress_companions, "congress_companions.csv"),
    (build_congress_mentions, "congress_mentions.csv"),
    (build_congress_senators, "congress_senators.csv"),
]


@pytest.fixture
def caches(tmp_path, monkeypatch):
    """Point every build at empty temp caches, and hand back the two dirs."""
    govinfo = tmp_path / "congress_govinfo"
    gentzkow = tmp_path / "congress_gentzkow"
    govinfo.mkdir()
    gentzkow.mkdir()
    for module, _ in BUILDS:
        monkeypatch.setattr(module, "CONGRESS_RAW_GOVINFO", govinfo, raising=False)
        monkeypatch.setattr(module, "CONGRESS_RAW_GENTZKOW", gentzkow, raising=False)
    return govinfo, gentzkow


def _write_days(govinfo, year, n):
    year_dir = govinfo / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (year_dir / f"CREC-{year}-{i:03d}.json").write_text(
            json.dumps({"package": f"CREC-{year}-{i:03d}",
                        "granules": [{"text": "china trade"}]}),
            encoding="utf-8",
        )


def _write_gentzkow(gentzkow):
    (gentzkow / "speeches_senate_100.jsonl").write_text(
        json.dumps({"date": "20150104", "text": "china trade", "speech_id": "1"}) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("module,csv_name", BUILDS, ids=lambda v: getattr(v, "__name__", v))
def test_one_cached_day_does_not_pass_as_a_corpus(module, csv_name, caches, capsys):
    """The exact artifact that defeated the old check: one real day, one phantom."""
    govinfo, gentzkow = caches
    _write_days(govinfo, 2023, 1)
    (govinfo / "2023" / "CREC-2023-01-03.phantom.json").write_text(
        json.dumps({"package": "CREC-2023-01-03", "reason": "not found"}),
        encoding="utf-8",
    )
    _write_gentzkow(gentzkow)

    assert module.main() == 1
    out = capsys.readouterr().out
    assert "incomplete" in out


@pytest.mark.parametrize("module,csv_name", BUILDS, ids=lambda v: getattr(v, "__name__", v))
def test_a_uniformly_partial_cache_does_not_pass_as_a_corpus(module, csv_name, caches):
    """Every expected year present, every one one day short of the floor.

    This is what an interrupted 110k-request job actually leaves behind, and it
    is invisible to any check that asks whether a year exists.
    """
    govinfo, gentzkow = caches
    for year in range(1994, 2025):
        _write_days(govinfo, year, MIN_REAL_DAYS_PER_YEAR - 1)
    _write_gentzkow(gentzkow)

    assert module.main() == 1


@pytest.mark.parametrize("module,csv_name", BUILDS, ids=lambda v: getattr(v, "__name__", v))
def test_the_failure_names_the_short_years(module, csv_name, caches, capsys):
    """After hours of downloading, 'incomplete' alone is not actionable."""
    govinfo, gentzkow = caches
    for year in range(1994, 2025):
        _write_days(govinfo, year, MIN_REAL_DAYS_PER_YEAR if year != 2021 else 3)
    _write_gentzkow(gentzkow)

    module.main()
    assert "2021" in capsys.readouterr().out


@pytest.mark.parametrize("module,csv_name", BUILDS, ids=lambda v: getattr(v, "__name__", v))
def test_an_empty_cache_never_writes_a_csv(module, csv_name, caches, tmp_path, monkeypatch):
    """A build that cannot run must exit 1, not ship an empty or partial CSV."""
    out_dir = tmp_path / "data"
    out_dir.mkdir()
    out_path = out_dir / csv_name
    monkeypatch.setattr(module, "OUT_PATH", out_path, raising=False)

    assert module.main() == 1
    assert not out_path.exists()
