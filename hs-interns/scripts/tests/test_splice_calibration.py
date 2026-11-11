from calibrate_splice import choose_strategy, compare_overlap


def test_close_agreement_selects_concatenate():
    g = {y: 100 for y in range(1994, 2017)}
    v = {y: 102 for y in range(1994, 2017)}
    assert choose_strategy(compare_overlap(g, v)) == "concatenate"


def test_stable_ratio_selects_scale():
    g = {y: 100 for y in range(1994, 2017)}
    v = {y: 150 for y in range(1994, 2017)}
    comparison = compare_overlap(g, v)
    assert choose_strategy(comparison) == "scale"
    assert 1.45 < comparison["mean_ratio"] < 1.55


def test_unstable_ratio_abandons_the_splice():
    g = {y: 100 for y in range(1994, 2017)}
    v = {1994 + i: 50 + i * 40 for i in range(23)}
    assert choose_strategy(compare_overlap(g, v)) == "govinfo_only"


def test_comparison_reports_per_year_detail():
    g = {y: 100 for y in range(1994, 2017)}
    v = {y: 110 for y in range(1994, 2017)}
    comparison = compare_overlap(g, v)
    assert len(comparison["per_year"]) == 23
    assert "cv" in comparison


def test_offsetting_outliers_do_not_slip_past_as_concatenate():
    """Two opposite outliers must not cancel into a false 'these agree'.

    mean_rel_diff alone reads 4.35% here (inside AGREE_TOLERANCE) while cv is
    14.7% (outside STABLE_CV): the mean says the series agree, the spread says
    they do not track each other. Short-circuiting on mean_rel_diff would
    return 'concatenate' and the stability gate would never run.

    This is the gate that protects Beat 1. Its headline claim is that china
    mentions climb steeply after 2017, and 2017 is the splice point, so a
    wrong 'concatenate' manufactures a step change indistinguishable from the
    real finding.
    """
    gentzkow = {y: 100 for y in range(1994, 2017)}
    govinfo = dict(gentzkow)
    govinfo[2000] = 150
    govinfo[2001] = 50

    comparison = compare_overlap(gentzkow, govinfo)
    assert comparison["mean_rel_diff"] <= 0.05, "fixture no longer exercises the artifact"
    assert comparison["cv"] > 0.10, "fixture no longer exercises the artifact"
    assert choose_strategy(comparison) == "govinfo_only"
