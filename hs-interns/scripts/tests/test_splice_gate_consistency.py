# scripts/tests/test_splice_gate_consistency.py
"""I1 (updated for the govinfo_only world): all three congress builds must
refuse identically under a pre-coverage year range.

Originally this asserted all three builds consulted calibrate_splice.
resolve_strategy and raised on a `govinfo_only` verdict -- the machinery that
existed to prevent one build (mentions) from refusing a Gentzkow/GovInfo
splice while the other two (companions, senators) ran to completion on the
very years mentions had just declared untrustworthy. Two of the three
published CSVs would have shipped built on data the third rejected.

That machinery is gone: the 1994-2016 overlap calibrated to `govinfo_only` on
2026-07-21, the splice was abandoned rather than scaled or concatenated, and
no build resolves a strategy any more (see twl_common.GOVINFO_ERA_START).
`resolve_strategy` itself no longer exists as an attribute on any of these
three modules, so the old test would not even monkeypatch cleanly.

The invariant it protected is still real, just re-expressed: every build's
year range is anchored to GOVINFO_ERA_START now, via a static floor guard in
build() (`start_year < GOVINFO_ERA_START`) that fires before any cache is
touched. If that guard were ever missing or miscoded on exactly one module,
that module would silently build a truncated-looking-complete, or outright
empty, series for years no source actually covers for it -- the same
"two of three ship on data the third rejects" shape, just triggered by a
widened year range instead of a bad splice verdict. So this asserts, in the
same three-build parametrized shape as before, that every build() raises
CongressDataRefusalError rather than quietly producing pre-coverage output
when its year range dips below the floor.

Asserted at build() (not per-module, and not via main()): the defect this
guards against is exactly one build knowing the floor and the others not, so
a per-module test of the one build that already had a correct guard would
have passed throughout the entire time the other two had none -- it is only
meaningful run identically across all three. build() specifically, rather
than main(), because main() on every module is a thin try/except around
build() (see e.g. build_congress_mentions.main()) -- testing build() directly
proves the gate cannot be bypassed by a caller that skips main(), the same
property the module docstrings already claim.

Non-vacuity note: a bare `pytest.raises(CongressDataRefusalError)` would also
pass with the floor guard DELETED, because build()'s other gate -- the
GovInfo coverage check -- raises the very same exception type against a cache
that (on this machine, in this repo) has no real pre-2010 data either. The
`match=` below pins the floor guard's own wording ("before GovInfo coverage"),
which the coverage gate's message never contains, so removing the floor guard
makes this test fail via the coverage gate's different message rather than
passing by accident. Verified directly (guard removed -> RED via the coverage
gate's message failing the match; guard restored -> GREEN) as part of Task 3b.
"""
import pytest

import build_congress_companions
import build_congress_mentions
import build_congress_senators
from twl_common import CongressDataRefusalError, GOVINFO_ERA_START

# Each module binds its own year-range constant under a different name
# (MENTIONS_YEARS for the corpus-level builds, SENATOR_YEARS for the
# per-senator build) -- see twl_common. The floor guard message is asserted
# identically across all three specifically so a per-module divergence in
# floor wording (which would defeat the shared `match=` below) cannot creep
# in unnoticed.
CASES = [
    (build_congress_companions, "MENTIONS_YEARS"),
    (build_congress_mentions, "MENTIONS_YEARS"),
    (build_congress_senators, "SENATOR_YEARS"),
]
IDS = ["companions", "mentions", "senators"]

# Below GOVINFO_ERA_START on both ends, so the floor guard fires on the
# range's minimum without needing any cache fixture -- the guard is checked
# before any file is touched (see each build()'s docstring/ordering).
BELOW_FLOOR_YEARS = range(GOVINFO_ERA_START - 5, GOVINFO_ERA_START)


@pytest.mark.parametrize("module,years_attr", CASES, ids=IDS)
def test_every_build_refuses_below_the_govinfo_floor(module, years_attr, monkeypatch):
    """No build may quietly ship pre-coverage output while another refuses."""
    monkeypatch.setattr(module, years_attr, BELOW_FLOOR_YEARS, raising=True)
    with pytest.raises(CongressDataRefusalError, match="before GovInfo coverage"):
        module.build()
