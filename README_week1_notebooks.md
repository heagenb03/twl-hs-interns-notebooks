# Week 1 Notebooks: Full Handoff

## The set
| Notebook | Data files | Pip installs in Colab | Anchor numbers |
|---|---|---|---|
| `bill_classifier.ipynb` | `bills_china.csv` | sentence-transformers | **Estimates, recapture** |
| `congress_mentions.ipynb` | `congress_mentions.csv`, `congress_companions.csv`, `congress_senators.csv` | none | **Real** (deterministic data) |
| `tariff_event_study.ipynb` | `tariff_prices.csv` | none | **Real** (deterministic data) |
| `media_framing.ipynb` | `headlines.csv` | sentence-transformers, vaderSentiment | Beat 1 sentiment: **real**. Beat 2/3 classifier: **estimates, recapture** |

All four follow the approved template: personal-copy intro (Drive distribution model),
▶️ JUST RUN vs ✏️ YOUR TURN cells, anchor block + likely-error hint + Ctrl+Z recovery
under every edit cell, "Things to try" ladders, stretch goal, Week 2 bridge in the
wrap-up. All intern edits are strings, numbers, or lists; all `def`s live in JUST RUN
cells. All helpers forgive the common typos (quoted numbers, bare strings instead of
lists, unknown names → friendly message listing valid options; weekend dates roll to
the next trading day).

## Repo layout
```
twl-hs-interns-notebooks/
├── notebooks/  (4 .ipynb)
├── scripts/    (4 make_data_*.py)
└── data/       (6 .csv)
```
All notebooks read data from `raw.githubusercontent.com` URLs regardless of where the
notebook file itself lives (GitHub master vs. named Drive copies).

## TODOs before freeze, in order
1. **Set the URL placeholder** — search all four notebooks for `YOUR-ORG` (one
   occurrence each) and point at the real repo path.
2. **One full Colab run per notebook.** Non-negotiable for async. While you're in
   there:
   - Bill classifier: replace all 7 "What you should see" numbers with actual outputs;
     verify Beat 3 race lands near ML 11/12 vs keyword 6/12.
   - Media framing: replace the Beat 2 accuracy anchor (currently "60–85%") and spot-check
     that `guess_outlet` on the starting WSJ-style headline actually leads WSJ. If the
     4-class classifier lands below ~55% with real embeddings, tell me — the fix is more
     headlines per outlet, and I can extend the generator.
   - Congress + tariff: anchors are captured from the actual data and should match as-is;
     just eyeball the charts.
3. **Named Drive copies** after form results: copy each intern's assigned notebook into
   the shared folder, rename with their name, share per-file (not folder-level).
4. **Real data swaps** (all optional for launch; schemas documented in each `make_data_*.py`):
   - `bills_china.csv` — real bill snippets when ready.
   - Congress CSVs — currently synthetic with plausible shapes (PNTR bump, post-2017
     surge, early-90s Japan, 2022 Russia). Real counts need your Congressional Record
     pull. **Per-senator counts are synthetic numbers attached to real names** — the
     names and general pattern match the public record of who leads on China rhetoric,
     but replace with real counts before anything leaves the program context.
   - `tariff_prices.csv` — synthetic walks with plausibly-sized injected moves at six
     real announcement dates. Swap for actual yfinance pulls (frozen to CSV) when ready;
     the six dates and event labels are real and can stay.
   - `headlines.csv` — 72 synthetic headlines written in outlet styles (intentionally so:
     avoids copyright and gives clean signal). The notebook discloses this to interns.
     Could stay synthetic permanently, or swap for a real curated set later.

## Verified in sandbox
Every code cell of all four notebooks executes top-to-bottom; every intern edit path
and typo-forgiveness path tested (see `test_nb.py`, `test_three.py`). NOT verifiable
in sandbox: real embedding quality (HuggingFace unreachable: tests used a
non-semantic stand-in, which is why classifier scores in test logs look weak).
VADER sentiment WAS tested for real: all Beat 1 media numbers are genuine.

## Design decisions worth remembering
- Media Beat 1 defaults to Phase One because it carries the best story: Fox (+0.05)
  and Xinhua (+0.48) — the two government-adjacent outlets — both spin positive on the
  deal their side signed, while NYT (−0.21) and WSJ (−0.11) stay skeptical.
- Media Beat 1 "Things to try" deliberately walks interns into VADER's failure on the
  Hong Kong event ("freedom"/"security"/"stability" score positive in crackdown
  headlines) as the motivation for the embedding classifier in Beat 2.
- Congress notebook includes the 2000 PNTR bump in the synthetic data so Beat 1 has
  two stories (2000 bump + 2017 surge), and the Japan early-90s arc as the comparison
  that raises the "will China's line ever fade?" question.
- Tariff Beat 3 (Phase One flatline vs. Sunday-tweet cliff) is the notebook's real
  wow — "priced in" lands harder than the speed beat, which is why it comes last.
- Media stretch is a held-out-event test (style vs. vocabulary memorization) — the
  most research-flavored moment across all four notebooks, good stretch for Nikita
  if she ends up there.
