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
