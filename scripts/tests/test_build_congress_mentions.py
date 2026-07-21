# scripts/tests/test_build_congress_mentions.py
"""build_congress_mentions is GovInfo-only: no splice, coverage gate stays.

The 1994-2016 Gentzkow/GovInfo overlap was calibrated on 2026-07-21 and
returned `govinfo_only` (see twl_common.GOVINFO_ERA_START). The Gentzkow half
is abandoned, so build() must never touch the Gentzkow cache. The GovInfo
coverage gate is unrelated to the splice and must still stop an incomplete
cache from shipping validator-clean wrong output.
"""
import json
from pathlib import Path

import pytest

from congress_cache import MIN_REAL_DAYS_PER_YEAR, write_manifest

# A little above the floor so a synthetic year clears govinfo_range_usable
# with margin.
_DAYS_PER_YEAR = MIN_REAL_DAYS_PER_YEAR + 5

# All eight notebook terms, so build_mentions_frame's japan>0 guard (and any
# future guard on another term) is satisfied without special-casing japan.
_ALL_TERMS_TEXT = "china japan russia taiwan tariffs trade terrorism climate"


def _write_complete_govinfo_cache(root: Path, years: range) -> None:
    """A synthetic GovInfo cache that clears govinfo_range_usable for `years`.

    Built entirely under `root` (a tmp_path), independent of whatever this
    repo's real data/_raw/congress_govinfo cache happens to contain right
    now. That is what makes test_build_reads_no_gentzkow_data hermetic: it
    must not be able to fail on the coverage gate before it ever reaches its
    own assertions, on a machine where the real cache is partial or absent.
    """
    for year in years:
        packages = [f"CREC-{year}-{i:03d}" for i in range(_DAYS_PER_YEAR)]
        write_manifest(root, year, packages)
        year_dir = root / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        for pkg in packages:
            (year_dir / f"{pkg}.json").write_text(
                json.dumps({"package": pkg, "granules": [{"text": _ALL_TERMS_TEXT}]}),
                encoding="utf-8",
            )


def test_build_reads_no_gentzkow_data(tmp_path, monkeypatch):
    """The mentions build must not touch the Gentzkow cache at all.

    Three independent checks, per the Task 2 review's finding that patching
    only `builtins.open` proved nothing on Python 3.13: pathlib reads
    (`Path.read_text`, `Path.open`) go through the `io` module, not through
    `builtins.open`, so a spy on `builtins.open` alone observes zero of the
    real read calls here and the old version of this test passed vacuously
    even with a live Gentzkow read spliced into build().

      1. A structural check independent of any interception: the module must
         not even import CONGRESS_RAW_GENTZKOW.
      2. Spies on `builtins.open`, `Path.open`, AND `Path.read_text` --
         congress_cache.iter_govinfo_days reads via `Path.read_text`, and the
         deleted Gentzkow reader used `Path.open`, so both must be covered.
      3. The spies are asserted to have actually fired (`opened` non-empty).
         A spy that observes nothing must fail loudly, not pass vacuously.

    Runs against a synthetic, fully-covered GovInfo cache built under
    tmp_path (see _write_complete_govinfo_cache) rather than the real repo
    cache, so an incomplete real cache cannot make this error out on the
    coverage gate before the Gentzkow assertion ever executes.
    """
    import build_congress_mentions as bcm

    # (1) Structural: no functional reference to the Gentzkow cache remains,
    # independent of whether the spies below intercept anything at all.
    assert not hasattr(bcm, "CONGRESS_RAW_GENTZKOW")

    govinfo_root = tmp_path / "congress_govinfo"
    _write_complete_govinfo_cache(govinfo_root, bcm.MENTIONS_YEARS)
    monkeypatch.setattr(bcm, "CONGRESS_RAW_GOVINFO", govinfo_root)
    monkeypatch.setattr(bcm, "OUT_PATH", tmp_path / "congress_mentions.csv")

    opened: list[str] = []
    real_open = open
    real_path_open = Path.open
    real_path_read_text = Path.read_text

    def spy_open(path, *a, **kw):
        opened.append(str(path))
        return real_open(path, *a, **kw)

    def spy_path_open(self, *a, **kw):
        opened.append(str(self))
        return real_path_open(self, *a, **kw)

    def spy_path_read_text(self, *a, **kw):
        opened.append(str(self))
        return real_path_read_text(self, *a, **kw)

    monkeypatch.setattr("builtins.open", spy_open)
    monkeypatch.setattr(Path, "open", spy_path_open)
    monkeypatch.setattr(Path, "read_text", spy_path_read_text)

    bcm.build()

    # (3) The spy must actually have observed real reads -- otherwise this
    # test is the vacuous pass the review found: a build that opened nothing
    # at all also satisfies "no Gentzkow file was opened".
    assert opened, "the open()/read_text() spies never fired during build()"
    assert not any("congress_gentzkow" in p for p in opened), (
        f"build() read Gentzkow files: "
        f"{[p for p in opened if 'congress_gentzkow' in p]}"
    )


def test_build_still_refuses_an_incomplete_govinfo_range(tmp_path, monkeypatch):
    """Removing the splice gate must not remove the coverage gate."""
    import build_congress_mentions as bcm
    from twl_common import CongressDataRefusalError

    monkeypatch.setattr(bcm, "CONGRESS_RAW_GOVINFO", tmp_path)  # empty cache
    with pytest.raises(CongressDataRefusalError):
        bcm.build()
