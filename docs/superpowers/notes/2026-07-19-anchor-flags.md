# Anchor flags for Heagen's Colab pass (2026-07-19)

This note is a byproduct of the prose-cleanup pass, not a fix. "What you should see"
anchor blocks in these notebooks are supposed to show interns the actual output of a
real run. A handful of anchors still contain literal `...` placeholders or vague
percent ranges instead of a captured number. Those can only be filled in by actually
running the notebook end-to-end in Colab — out of scope for this cleanup branch, whose
job was tells/prose only. This list is what Heagen should look at first during his
manual Colab pass, before merging to `main`.

## How this list was derived

Regenerated fresh against the current state of `notebooks/*.ipynb` on this branch
(not copied from the design spec), using the grep script from the Task 7 brief:

```python
pat = re.compile(r"\.\.\.|\b\d+\s*[–-]\s*\d+\s*%")
# scans markdown cells, lines starting with ">" (anchor-box content) only
```

Raw output:

```
bill_classifier.ipynb [cell 10] > percentage — likely somewhere in the 80–95% range.
bill_classifier.ipynb [cell 23] > **What you should see:** a numbered table (rows 0, 1, 2, ...) of bill titles with
congress_mentions.ipynb [cell 9] > `'china': 210 mentions in 1990 → 1048 in 2024 (peak: ...)`
congress_mentions.ipynb [cell 17] > `Marco Rubio peaked at ... mentions in 20...`. The senator's line pulls away from
media_framing.ipynb [cell 14] > **What you should see:** an accuracy line — likely somewhere in the **60–85%**
```

**Sanity check beyond the script's regex:** the script only catches literal `...` and
`NN-NN%` ranges (the `%` is required by its pattern). I ran two follow-up sweeps over
blockquote lines to check what that pattern could miss:

1. Unicode ellipsis (`…`), `TBD`/`XX`/`N/A`, and hedge words (`somewhere`,
   `roughly`, `approximately`, `around`) — see correction below re: `to`-style
   ranges. This turned up three hits, all false positives on closer reading —
   each already contains a specific captured-looking number and the hedge word
   is just softening language, not marking an unfilled placeholder:
   - `bill_classifier.ipynb` cell 7 — "roughly half the bills are labeled `1`" —
     describes a fixed property of the input CSV, not a model output pending a run.
   - `media_framing.ipynb` cell 11 — "roughly `NYT: -0.21 WSJ: -0.11 Fox: +0.05
     Xinhua: +0.48`" — specific numbers present; per the README these Beat 1
     sentiment scores are VADER-computed and verified genuine (not estimates).
   - `tariff_event_study.ipynb` cell 12 — "roughly `-2.7%` versus `+1.2%`" —
     specific numbers present; per the README, congress/tariff anchors are captured
     from real deterministic data and "should match as-is."

   **Correction:** despite the label above, this sweep's actual regex did not
   match `to`-style ranges (no pattern here joins two numbers across the word
   `to`) — only the dash-joined and hedge-word cases were truly covered.
   `to`-style ranges were checked manually instead, and one genuine instance
   turned up: `tariff_event_study.ipynb` cell 15 — "day-0 moves around
   `-1.6%` to `-3%` depending on ticker" and "around `-0.3%` to `+0.1%`".
   Both are real captured spreads across tickers (not unfilled placeholders):
   per the README, tariff anchors come from real deterministic data, and a
   range across six tickers is the expected shape of that data, not a
   pending-run gap.

2. A number-range check with no `%` requirement (`\d+(\.\d+)?\s*[–-]\s*\d+(\.\d+)?`),
   to catch ranges on non-percent metrics that the original script's pattern would
   miss. This found one genuine addition and one false positive:
   - `bill_classifier.ipynb` cell 17 — "confidence scores hovering near `0.4–0.6`" —
     added to the flag table below.
   - `tariff_event_study.ipynb` cell 9 — "`\"2019-08-23\"`" — false positive, this is
     an ISO date string, not a numeric range.

No additional genuine flags beyond the six now in the table below.

## Flag table

| Notebook | Cell | Anchor text | Why it's suspect |
|---|---|---|---|
| `bill_classifier.ipynb` | 10 | "a progress bar, then two lines ending with an accuracy percentage — likely somewhere in the 80–95% range." | range instead of a captured value |
| `bill_classifier.ipynb` | 17 | "a 12-row table of bill titles with confidence scores hovering near `0.4–0.6`" | range instead of a captured value — **caveat:** this describes a spread across 12 different rows rather than one metric collapsing to a single number, so a real run may legitimately still show a range here. Still an estimate per the README (bill_classifier is "Estimates, needs recapture"), so worth Heagen's spot-check. |
| `bill_classifier.ipynb` | 23 | "a numbered table (rows 0, 1, 2, ...) of bill titles with their human labels." | literal ellipsis placeholder — **caveat:** likely a false positive; the `...` here reads as a generic "row 0, 1, 2, and so on" enumeration, not an unfilled data value. Flagged because it matches the pattern; Heagen should confirm during his pass whether it needs any change at all. |
| `congress_mentions.ipynb` | 9 | "`'china': 210 mentions in 1990 → 1048 in 2024 (peak: ...)`" | literal ellipsis placeholder — the peak value was never filled in |
| `congress_mentions.ipynb` | 17 | "`Marco Rubio peaked at ... mentions in 20...`" | literal ellipsis placeholder — both the peak count and peak year are unfilled |
| `media_framing.ipynb` | 14 | "an accuracy line — likely somewhere in the **60–85%** range." | range instead of a captured value |

Net: **5 genuine placeholder/range anchors** (bill_classifier cells 10 and 17,
congress_mentions cells 9 and 17, media_framing cell 14), plus **1 pattern match that
is probably not a real problem** (bill_classifier cell 23) included for completeness
since the script flags it.

## Broader context: bill_classifier's seven pending numbers

`README_week1_notebooks.md`'s TODO list (item 2, bullet 1) states:

> Bill classifier: replace all 7 "What you should see" numbers with actual outputs;
> verify Beat 3 race lands near ML 11/12 vs keyword 6/12.

I verified this line is present in the README verbatim — the claimed count is **7**.

This is a **different, broader** count than the flag table above. The flag-list script
only catches anchors that look overtly unfinished (literal `...` or a percent range).
The README's "7" refers to every anchor number in `bill_classifier.ipynb` that is a
model-produced estimate needing recapture from a real Colab run — including numbers
that already *look* like finished values (e.g. `Confidence: 3.1%` in cell 14, `46 of
90 bills` in cell 17, `24 of 27 bills` in cell 25, `Keyword model: 6/12 ML model:
11/12` in cell 20) but were computed in the sandbox against a non-semantic stand-in
embedding model rather than the real one. Per the README's "Verified in sandbox"
section: "real embedding quality (HuggingFace unreachable: tests used a non-semantic
stand-in, which is why classifier scores in test logs look weak)." Those numbers read
as legitimate output but are not trustworthy until Heagen's real run — they would not
be caught by a text-pattern grep, only by knowing which cells run inference.

I counted the `bill_classifier.ipynb` cells containing "What you should see" and found
**10** such blocks total (cells 0, 5, 7, 10, 14, 17, 20, 23, 25, 28 — cell 0 has no
anchor content). Of those, the ones carrying a genuine model-estimate number are cells
10, 14, 17, 20, 25, and 28 (28 asks about "a new accuracy number" without giving one) —
roughly six to seven depending on how cell 28's open-ended question is counted, which
is consistent with the README's "7." I am **not** overriding the README's figure; I'm
reporting that my independent count is in the same neighborhood (6-7) and does not
contradict it.

**Verdict: no discrepancy.** The README's claim of "7" matches the task framing's
"seven," and my independent recount lands in the same 6-7 neighborhood using a
different (broader, manual) method. Nothing here needs correcting.

## What this note does NOT do

- It does not edit any notebook. Fixing these requires running the notebook for real.
- It does not re-litigate the em-dash pass or blockquote content — those are covered
  by the final verification in the Task 7 report.
- Conflicts between this branch's anchor-box text and the eventual real-data-swap
  work should resolve in favor of the real-data-swap version.
