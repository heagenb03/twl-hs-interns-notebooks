# scripts/tests/test_build_congress_senators.py
"""Task 3b: build_congress_senators is GovInfo-only, like mentions/companions.

The 1994-2016 Gentzkow/GovInfo overlap calibrated to `govinfo_only` on
2026-07-21 (see twl_common.GOVINFO_ERA_START). SENATOR_YEARS is already
2010-2024 -- entirely within GovInfo coverage -- so unlike mentions/companions
this build previously read Gentzkow for NONE of a discontinued pre-coverage
range, but for its own primary 2010-2016 half. That half, the whole
Gentzkow-name-to-bioguide reconciliation, and the `scale`-verdict
NotImplementedError are all gone now: no splice strategy is resolved any more,
so a branch guarding a decision about how to apply one is unreachable code
that would mislead the next reader into thinking a decision is still pending.
"""


def test_senators_has_no_unreachable_scale_branch():
    """The `scale` NotImplementedError implied a live decision. No strategy is
    resolved any more, so leaving it would mislead the next reader.

    The literal `assert "govinfo_only" not in src` from the original brief
    would collide with the explanatory comment Heagen asked to keep recording
    *why* the splice is gone (which legitimately contains that string), so
    this checks for the actual machinery instead: no more calls into
    calibrate_splice.resolve_strategy anywhere in the module.
    """
    src = open("scripts/build_congress_senators.py", encoding="utf-8").read()
    assert "NotImplementedError" not in src
    assert "resolve_strategy" not in src
