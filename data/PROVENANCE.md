# Data Provenance

Where each dataset in `data/` comes from. The pipeline that produced them is
in `scripts/` and is committed — read it for the exact queries. This file
records what the code cannot: when each pull happened, what came back, and
what to distrust.

---

## tariff_prices.csv

- **Source:** Yahoo Finance, via the `yfinance` Python package (v1.5.1).
- **Pulled:** 2026-07-19
- **Query:** `yf.download(["SPY","FXI","BA","CAT","SOYB","AAPL"], start="2017-01-03", end="2020-07-01", auto_adjust=False)`, taking the `Close` column.
- **Rows:** 879 trading days, 2017-01-03 to 2020-06-30.
- **Price convention:** `auto_adjust=False` with `Close` gives **split-adjusted,
  non-dividend-adjusted** prices. Verification: AAPL's 2017-01-03 close is
  29.04, consistent with the 4:1 split in Aug 2020 (nominal was ~116 before
  the split).
- **Transform:** duplicate dates dropped first, keeping the first occurrence
  — done *before* sorting because pandas' `sort_index` is not stable across
  ties, so deduping first is what makes "keep first" deterministic. Then
  sorted ascending. Then columns reindexed to the canonical order
  `SPY, FXI, BA, CAT, SOYB, AAPL` *before* `dropna`, so a missing ticker
  drops all rows loudly (a highly visible signal) rather than silently
  leaving an all-NaN column undetected. Rows with any remaining null are
  dropped. Values rounded to 2dp. No interpolation — a filled price would be
  invented data.

### Caveats

- **SOYB is thin.** Median daily volume over the pull window is roughly
  30,300 shares versus SPY's roughly 73.0M (measured directly against Yahoo
  Finance's `Volume` column for 2017-01-03 to 2020-06-30; the pipeline itself
  only pulls `Close`, so this number is not reproducible from the committed
  scripts — it is a one-off spot check). Fine for daily directional
  event-study work; expect more idiosyncratic noise than a liquid name.
  `ZS=F` (front-month CBOT soybean futures) is a cleaner underlying if that
  ever matters.
- **The COVID crash is inside the window.** Data runs to 2020-06-30 and BA
  falls to 95.01 on 2020-03-20. Phase One (2020-01-15) sits 5.0 weeks before
  SPY's pre-crash peak (338.34 on 2020-02-19) and 9.3 weeks before BA's
  trough. Beat 3's "priced in" reading was verified to hold on a day-0 basis
  against the 2019-05-06 Sunday-tweet surprise escalation: Phase One moved
  SPY +0.23%, FXI -0.56%, BA -0.77%, versus SPY -0.41%, FXI -2.61%, BA -1.29%
  for the surprise. The reading holds for all three tickers. Longer windows
  around Phase One run into COVID and should not be read as trade-war
  effects.
- **The six event dates are real** and unchanged from the synthetic version.
  All six are trading days in the real calendar.

### Anchors

`scripts/print_anchors.py` emits the notebook's "What you should see" values
directly from `tariff_prices.csv`. It deliberately mirrors the notebook's own
formulas rather than reimplementing them independently, including the
cumulative-abnormal-return calculation (the running sum of daily excess
returns, ticker minus SPY) used by the notebook's `market_adjusted()` helper.
Run it after any data change to recapture the anchors:

```bash
python scripts/print_anchors.py
```
