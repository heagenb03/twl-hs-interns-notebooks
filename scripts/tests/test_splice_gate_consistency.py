# scripts/tests/test_splice_gate_consistency.py
"""I1: all three congress builds must answer to the same splice verdict.

Only build_congress_mentions consulted calibrate_splice. companions and
senators never called it at all, so under a `govinfo_only` verdict -- the
Gentzkow and GovInfo china series diverge unstably over the overlap and must
not be joined -- mentions would refuse to build while the other two ran to
completion on the very Gentzkow years mentions had just declared untrustworthy.
Two of the three published CSVs would ship built on data the third rejected.

Task 9's docstring argued companions needs no verdict because "that split is
identical under every splice outcome". True for `concatenate` and `scale`;
false for `govinfo_only`, which is not a split at all but an abandonment.

These tests assert the invariant at the build() level rather than per module,
because the defect was that one build knew and two did not -- a per-module test
of the build that already knew would have passed throughout.
"""
import pytest

import build_congress_companions
import build_congress_mentions
import build_congress_senators

BUILDS = [
    build_congress_companions,
    build_congress_mentions,
    build_congress_senators,
]
IDS = ["companions", "mentions", "senators"]


@pytest.mark.parametrize("module", BUILDS, ids=IDS)
def test_every_build_refuses_under_a_govinfo_only_verdict(module, monkeypatch):
    """No build may quietly ship while another refuses on the same verdict."""
    monkeypatch.setattr(
        module, "resolve_strategy", lambda *a, **k: ("govinfo_only", {}), raising=True
    )
    with pytest.raises(RuntimeError, match="govinfo_only"):
        module.build()


@pytest.mark.parametrize("module", BUILDS, ids=IDS)
def test_every_build_names_heagen_and_stops_rather_than_applying_it(module, monkeypatch):
    """govinfo_only means dropping 1990-1993 and re-anchoring the Japan beat.
    That is a human decision, not something a build applies silently."""
    monkeypatch.setattr(
        module, "resolve_strategy", lambda *a, **k: ("govinfo_only", {}), raising=True
    )
    with pytest.raises(RuntimeError) as exc:
        module.build()
    assert "Heagen" in str(exc.value)


@pytest.mark.parametrize("module", BUILDS, ids=IDS)
def test_every_build_reaches_the_verdict_before_doing_any_work(module, monkeypatch):
    """The gate must sit ahead of the corpus walk, not after it.

    A gate that fires only after hours of walking still produces the right
    answer, but it is the difference between a fast refusal and one that
    arrives at the end of an unattended overnight job.
    """
    calls = []
    monkeypatch.setattr(
        module,
        "resolve_strategy",
        lambda *a, **k: (calls.append("verdict"), ("govinfo_only", {}))[1],
        raising=True,
    )
    with pytest.raises(RuntimeError):
        module.build()
    assert calls == ["verdict"]
