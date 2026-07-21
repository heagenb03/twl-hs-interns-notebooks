# scripts/tests/test_build_congress_mentions.py
"""build_congress_mentions is GovInfo-only: no splice, coverage gate stays.

The 1994-2016 Gentzkow/GovInfo overlap was calibrated on 2026-07-21 and
returned `govinfo_only` (see twl_common.GOVINFO_ERA_START). The Gentzkow half
is abandoned, so build() must never touch the Gentzkow cache. The GovInfo
coverage gate is unrelated to the splice and must still stop an incomplete
cache from shipping validator-clean wrong output.
"""
import pytest


def test_build_reads_no_gentzkow_data(tmp_path, monkeypatch):
    """The mentions build must not touch the Gentzkow cache at all.

    Runs build() against the real GovInfo cache (there is no synthetic
    substitute for "did this touch a real Gentzkow file"), but OUT_PATH is
    redirected into tmp_path first: this test's job is to observe every
    `open()` call, not to (re)write the tracked data/congress_mentions.csv as
    a side effect of running the suite. Rebuilding that CSV for real is a
    separate, deliberate step, not something pytest should do implicitly.
    """
    import build_congress_mentions as bcm
    monkeypatch.setattr(bcm, "OUT_PATH", tmp_path / "congress_mentions.csv")
    opened = []
    real_open = open

    def spy(path, *a, **kw):
        opened.append(str(path))
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", spy)
    bcm.build()
    assert not any("congress_gentzkow" in p for p in opened), (
        f"build() read Gentzkow files: "
        f"{[p for p in opened if 'congress_gentzkow' in p]}"
    )


def test_build_still_refuses_an_incomplete_govinfo_range(tmp_path, monkeypatch):
    """Removing the splice gate must not remove the coverage gate."""
    import build_congress_mentions as bcm
    monkeypatch.setattr(bcm, "CONGRESS_RAW_GOVINFO", tmp_path)  # empty cache
    with pytest.raises(SystemExit):
        bcm.build()
