# Mirrored by hand in plot_ratio() (notebook cell 6, notebooks/congress_mentions.ipynb) - keep both in sync.
def durable_crossover(ratio: "pd.Series") -> int | None:
    """First year from which ratio stays above 1 through the end of the series."""
    above = ratio > 1
    if not above.iloc[-1]:
        return None
    last_below = above[~above]
    if last_below.empty:
        return int(ratio.index[0])
    return int(ratio.index[ratio.index.get_loc(last_below.index[-1]) + 1])


def test_durable_crossover_ignores_early_wobble():
    import pandas as pd
    ratio = pd.Series(
        [2.01, 1.67, 2.07, 0.65, 1.25, 0.82, 0.46, 1.13, 2.33, 3.08,
         7.27, 7.55, 5.38, 6.14, 3.43],
        index=range(2010, 2025),
    )
    assert durable_crossover(ratio) == 2017


def test_durable_crossover_returns_none_if_it_ends_below():
    import pandas as pd
    ratio = pd.Series([2.0, 0.5], index=[2010, 2011])
    assert durable_crossover(ratio) is None


def test_durable_crossover_returns_first_year_if_never_below():
    import pandas as pd
    ratio = pd.Series([1.5, 2.0, 3.0], index=[2010, 2011, 2012])
    assert durable_crossover(ratio) == 2010
