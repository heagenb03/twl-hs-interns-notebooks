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

---

## congress_mentions.csv · congress_companions.csv · congress_senators.csv

> **STATUS: MIXED — read this before trusting any of the three.**
>
> | File | State |
> |---|---|
> | `congress_mentions.csv` | ✅ **REAL.** Rebuilt from the GovInfo cache, 2010–2024, 120 rows (`b8f3330`). |
> | `congress_companions.csv` | ❌ **STILL SYNTHETIC.** Byte-identical to the initial commit (blob `731a37fc`). |
> | `congress_senators.csv` | ❌ **STILL SYNTHETIC.** Byte-identical to the initial commit (blob `c72f59b0`). |
>
> The bulk pull **has** been run (3,536 GovInfo day files, ~10 h) and the
> mentions build succeeded. The other two builds were run against the same real
> cache on 2026-07-21 and **neither produced usable output**:
>
> - **companions** exited 0 and wrote a validator-clean CSV whose top words were
>   pure legislative boilerplate (`shall, section, under, such, states, united,
>   secretary…`). CREC interleaves verbatim bill text with speech *inside* a
>   granule, and the stopword list carries no statutory vocabulary. The output
>   was discarded, not committed. See `logs/build_companions.log`.
> - **senators** exited 1 on the first day it touched (`CREC-2010-01-22`) on the
>   `role=SPEAKING` attribution guard, and wrote nothing. Measured over the full
>   cache the guard fires on 0.55% of granules (816 of 149,169), spread evenly
>   across all 15 years. See `logs/build_senators.log`.
>
> `scripts/validate_data.py` therefore still reports `FAIL congress_*.csv`. Its
> only complaints are the stale synthetic `Senate average` rows; the failure
> clears when the senators build lands, and not before.
>
> **Consequence for the notebook:** Beat 1 (frequency) and the Crossover run on
> real data. Beat 2 (`compare_eras`) and Beat 3 (`leaderboard` / `plot_senator`),
> and the recap's "*trade, WTO* → *CCP, threat, genocide*" line, are still
> teaching invented numbers while the surrounding prose describes them as
> Congressional Record data. Resolve before release.
>
> Sections below describe what the pipeline produces, which for two of the three
> files is not what currently ships.

- **Source: one, GovInfo alone, 2010–2024.** GovInfo Congressional Record
  (CREC), Senate granules, via the unauthenticated
  `/metadata/pkg/{PKG}/mods.xml` and `/content/pkg/{PKG}/html/{GRANULE}.htm`
  endpoints. **No API key is needed**; `DEMO_KEY` is unusable anyway (it 429s
  after four requests).
  - The Gentzkow–Shapiro–Taddy corpus (`hein-daily`, 11.4 GB unpacked,
    `data.stanford.edu/congress_text`) was extracted (1,298,145 Senate speeches,
    congresses 101–114) and used **only** to calibrate the splice. The splice
    calibrated to `govinfo_only`, so no Gentzkow data reaches any shipped CSV.
- **Chamber:** Senate only, both eras. Gentzkow must be filtered to the Senate
  or the post-2017 climb is partly an artifact of dropping the House.
- **Senators:** all 100, not a fixed list. Attribution is metadata-driven, so
  100 costs the same as 7, and it is what makes "Senate average" true.

### Pull range as actually executed

The pull ran on 2026-07-21, ~10 h at 4-way concurrency, and produced **3,536
GovInfo day files across 19 years**: the contiguous block 2010–2024 plus the
sparse calibration probes 1994, 1998, 2002 and 2006. Every pulled year matches
its sitemap manifest exactly; 18 phantom markers total (0.5%, against a 10%
ceiling). Gentzkow extraction produced 1,298,145 Senate speeches with no
MemoryError; 60 no-descr-match records, all confined to congress 101 (0.02%).

Only the contiguous 2010–2024 block feeds the shipped CSVs. The four probe years
calibrated the splice and supply no published data.

"Complete" is enforced against a per-year manifest (`_manifests/{year}.json`)
that `fetch_congress_govinfo.py` writes from the sitemap **before** downloading
that year. A year counts as covered only when every expected day is accounted
for as either fetched or provably phantom. A flat day-count floor is **not**
sufficient here, and the reason is the most dangerous failure in this pipeline:

> A partially-fetched overlap does not fail the stability gate. It **passes**
> it. A complete Gentzkow half against GovInfo fetched at 25 days/year (a real
> Senate year is ~150) gives `mean_ratio 0.00125`, `cv 0.00000` — maximum
> confidence — and `choose_strategy` certifies a `scale` join. The build then
> multiplies every pre-2017 count by that factor and concatenates the
> full-resolution 2017+ half, manufacturing a step change at exactly 2017 that
> is **indistinguishable from Beat 1's headline finding**. An interrupted
> download is the likeliest outcome of an unattended six-figure-request job.

A truncated Gentzkow extract produces the same shape with the opposite sign, so
both sides are gated.

### The splice verdict: `govinfo_only` (measured 2026-07-21)

`scripts/calibrate_splice.py` compares china mentions per year across the
1994–2016 overlap and returns one of `concatenate` (series agree within 5%),
`scale` (they differ by a stable ratio, cv ≤ 10%), or `govinfo_only` (they
diverge unstably — abandon the splice, lose 1990–1993, re-anchor the Japan
beat). All three builds resolve the verdict before doing any work and refuse on
`govinfo_only`; a guessed verdict is the most damaging thing this project could
ship, because 2017 is exactly where Beat 1's taught finding lives.

**Run against real data on 2026-07-21, on a complete 11-year overlap:**

| year | gentzkow | govinfo | ratio |
|---|---|---|---|
| 1994 | 1274 | 2720 | 2.135 |
| 1998 | 2131 | 4233 | 1.986 |
| 2002 | 552 | 1146 | 2.076 |
| 2006 | 740 | 1272 | 1.719 |
| 2010 | 980 | 1615 | 1.648 |
| 2011 | 1793 | 2926 | 1.632 |
| 2012 | 671 | 1325 | 1.975 |
| 2013 | 422 | 935 | 2.216 |
| 2014 | 502 | 1261 | 2.512 |
| 2015 | 977 | 1574 | 1.611 |
| 2016 | 401 | 914 | 2.279 |

`mean_rel_diff 0.9808` · `mean_ratio 1.9808` · `cv 0.1442` → **`govinfo_only`**.

GovInfo counts a consistent ~2× Gentzkow in every overlap year (1.61–2.51). Both
sides call the same `count_term(..., TERM)` (`calibrate_splice.py:176` and `:204`),
so this is a difference in what the two corpora *contain*, not in how they are
counted. An independent regex recount over the same GovInfo day files reproduced
the cv-driving years (2013 = 935 exact; 2014 = 1270 vs 1261; 2015 = 1576 vs 1574,
the excess being metadata strings the script does not read).

cv 0.1442 sits near the 0.10 `scale` threshold. **Do not lower `STABLE_CV` to reach
`scale`** — the consistent-2× pattern is a corpus-definition gap that a scalar would
paper over, and the script's refusal text forbids relaxing floors to pass a gate.

**How it was resolved.** `govinfo_only` meant every year had to come from
GovInfo, and only 19 of the 31 years 1994–2024 were ever pulled — the
1994/1998/2002/2006 probes existed to calibrate, not to supply data. Backfilling
the 12 missing years (1995–1997, 1999–2001, 2003–2005, 2007–2009; ≈1,900 day
files, ≈5 h) was rejected in favour of **narrowing the published series to the
contiguous fully-pulled window, 2010–2024**:

- `MENTIONS_YEARS` and `SENATOR_YEARS` are `range(2010, 2025)`
  (`twl_common.py:103-104`); `CONGRESS_ERAS` is `("2010s", "2020s")`.
- The splice is **gone from all three builds**, not merely gated. Each build now
  walks GovInfo alone; the coverage gate remains and is unrelated to the splice.
- 1990–2009 is dropped, which retires the Japan beat rather than re-anchoring it.

The 2010–2024 window still carries Beat 1: measured on this single corpus with a
single definition, china per Senate day runs flat and noisy 2010–2016 (mean ~8.3)
then climbs to **34.5 in 2021, 7× the 2016 level of 4.9**. Because there is no
splice anywhere in the series, that climb cannot be a splice artifact. Note the
rise begins in **2018**, not 2017 — 2017 sits at 6.7, inside the earlier noise
band, so prose saying "after 2017" is off by a year.

The `scale` branch and its open question — whether a uniform factor should be
applied to per-senator counts — are now unreachable and moot.

### Definitions

- **A mention** is a true term occurrence, not a document that matches.
  Case-insensitive; possessives count ("China's"); adjectival forms do not
  ("Chinese"); substrings do not ("Indochina"); "tariffs" folds to "tariff" and
  no other plural is folded.
- **A companion word** is any non-stopword in a segment that mentions China.
  **The window is ONE SPEECH SEGMENT — a single senator's single turn.** This
  matters: a GovInfo granule is a whole multi-speaker section (one committed
  2021 fixture is 19 turns across 10 senators), so counting per granule let a
  single China mention donate every word in a day's section, and the 2020s
  vocabulary came back as procedural boilerplate and senator surnames
  (`presiding, officer, yeas, nays, … cantwell`) instead of vocabulary
  (`competition, research, semiconductors, supply`). Granules are split into
  turns before counting, so both eras use the same window.
  - A hyphen at a line break is rejoined before tokenizing — CREC hard-wraps at
    a fixed column, which would otherwise split `most-favored-nation` into two
    tokens and silently cost a Beat 2 anchor. Single hyphens stay inside tokens.
  - `--` (CREC's aside marker) becomes a space.
  - Possessives fold to the base form on every token, corpus-wide, so the
    companions axis and the mentions axis agree.
- **"Senate average"** is the mean over every senator **known to be serving**
  that year, including those with zero China mentions. It is *not* the mean
  among senators who mentioned China — that was a defect, and a load-bearing
  one, since the label is what Beat 3 teaches interns to read distance from.
  The validator could not catch it, because it recomputes the mean from the
  same rows the build wrote.
  **Serving is a proxy, and the denominator must be read as such:** a senator
  counts as serving in year Y if they appear as a `role=SPEAKING` congMember on
  at least one cached day in Y. It can miss a senator who served but never
  surfaced on a captured day; it can never over-count. It is **not** an
  assertion that all 100 seats are represented.
- **Raggedness is deliberate and means tenure.** No rows before a senator takes
  office — Beat 3 teaches that directly. Zero rows are added only for years a
  senator was serving.

### Known gaps at the time of writing

- Display names will be **formal** (`Durbin, Richard J.` → `Richard J. Durbin`),
  while the notebook hardcodes colloquial ones (`Chuck Schumer`).
  `congress_anchors()` emits `ABSENT FROM DATA - prose must change` rather than
  mis-matching. **Do not "fix" this with fuzzy matching or an alias map** — that
  converts a loud correct failure into a silent wrong one. Whether to add an
  alias map or change the prose is a pedagogical decision, not a technical one.
- The notebook markdown still tells interns the co-occurrence window is "the
  same sentence as China". The computed window is one speaker's turn. The prose
  has not been updated; notebook edits are out of scope for this pass.
