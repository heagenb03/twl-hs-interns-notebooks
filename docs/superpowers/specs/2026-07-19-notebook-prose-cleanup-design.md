# Notebook Prose Cleanup — Design

**Date:** 2026-07-19
**Status:** Approved
**Scope:** Voice and redundancy cleanup across the four Week 1 intern notebooks, the
data-generation scripts, and the week-1 README.

---

## Problem

The four Week 1 notebooks read as AI-generated in places. The narrative prose carries
recurring stylistic tells and restates its own points across three layers (beat intro →
"Things to try" item 3 → "What you just did" wrap-up). Heagen will do a manual editing
pass after this one, so this pass is deliberately conservative: it removes what is
clearly excess and leaves judgment calls for the human pass.

The central risk is over-correction. Much of what superficially reads as AI-generated
is the **approved pedagogical template** documented in `README_week1_notebooks.md`.
Removing it would destroy the deliverable. The sacred/target split below is the spine
of this spec.

---

## Sacred — must not change

Nothing in this list is touched, reworded, or reformatted.

**Code**
- All code-cell logic, in notebooks and in `scripts/*.py`
- The `# <-- EDIT` sentinel comments
- The `# ▶️ JUST RUN` / `# ✏️ YOUR TURN` cell-header comments inside code cells

**Template structure**
- Section headers: `## Setup`, `## Meet the data`, `## Beat N`, `## Bonus Beat`,
  `## Stretch goal (optional)`, `## What you just did`
- The `▶️ JUST RUN` and `✏️ YOUR TURN` markers in markdown cells
- "What you should see" blockquote boxes, including their `**If you get a red error:**`
  hints and Ctrl+Z recovery instructions
- "Things to try" numbered ladders (items may be tightened; the ladder stays)
- Week 2 bridge paragraphs and "Before you close" prompts

**Data and values**
- Every number, percentage, ticker, date, era name, and senator name
- All anchor values inside "What you should see" boxes
- `data/*.csv` — untouched entirely

**Known TODOs that are not this pass's job**
- The `YOUR-ORG` URL placeholder (one per notebook) — Heagen's repo-path TODO
- Anchor numbers requiring a real Colab run to verify — see "Anchor flag list" below
- The repeated "⚠️ Step zero — this is YOUR copy" and "How this notebook works" blocks.
  Each notebook is a standalone personal Drive copy handed to a different intern, so
  each must carry its own instructions. This is not redundancy.

---

## Target — four edit classes

### 1. Voice tells

Surgical phrase-level replacements. Four tell families, all confirmed:

| Tell family | Example (current) | Example (revised) |
|---|---|---|
| "sit with" | `**A question to sit with:** the model never gives you 0% or 100%` | `**One more question:** the model never gives you 0% or 100%` |
| | `Here's the thing worth sitting with: **no human read these speeches.**` | `Worth noticing: **no human read these speeches.**` |
| | `1. Sit with the weirdness: signing the deal that paused...` | `1. Signing the deal that paused...` |
| "in one breath/sitting" | `Here's the plan, in one breath: a *language model* turns...` | `Here's the plan: a *language model* turns...` |
| | `In one sitting, with about ten lines of edited Python, you:` | `With about ten lines of edited Python, you:` |
| rhetorical setup | `3. Now the fun part — **be sneaky.** Can you write...` | `3. **Be sneaky.** Can you write...` |
| | `Here's a fair question: do we even need machine learning for this?` | `Do we even need machine learning for this?` |
| | `Now the trap. Try "Hong Kong security law"` | `Now the trap: try "Hong Kong security law"` |
| emoji + "Welcome!" | `# Can a Computer Tell if a Bill is About China? 🏛️` | `# Can a Computer Tell if a Bill is About China?` |
| | `Welcome! In this notebook you'll work with a real...` | `In this notebook you'll work with a real...` |

**Emoji removal** applies to the four H1 titles and the stretch/bonus headers
(🧠 🔀 🧪 🔬 🎯 📰🔍 📉⚡ 🏛️📈). The ▶️ ✏️ ⚠️ ✅ markers are template and stay.

**Em-dash reduction** covers both the triad pattern *and* general density across all
prose. Heagen confirmed the wider scope on 2026-07-19, knowingly extending past the
otherwise-surgical posture: it is the one edit class permitted to touch most prose
cells. Everything else in this spec stays surgical.

Rules for the pass:
- Replace an em dash with a comma, colon, or sentence break wherever the sentence
  reads the same afterward.
- Keep em dashes that carry a genuine parenthetical (a clause that could sit in
  parentheses) or a sharp reversal where the break is doing real work.
- Never introduce a semicolon as a substitute — it reads more formal than these
  notebooks' register.
- Reduce, do not eliminate. A notebook with zero em dashes reads as over-corrected.
- Em dashes inside "What you should see" boxes, quoted headlines, quoted bill text,
  and code strings are sacred and excluded.

### 2. Redundancy

Three confirmed cases:

- **`bill_classifier` cell 3** re-explains the edit convention already covered in
  "How this notebook works" (cell 0). Trim the duplicate explanation.
- **"Things to try" item 3** in most beats restates the beat's thesis, which the
  "What you just did" wrap-up then restates a third time. Resolution: trim the
  **wrap-up bullets** to a plain factual list and let the beats carry the argument.
  Item 3 stays where it does real teaching work (e.g. the bill_classifier keyword
  vs. ML point, the media style-vs-vocabulary question).
  To be precise: "wrap-up bullets" means only the dashed list under
  `## What you just did`. The Week 2 bridge paragraph and "Before you close" prompt
  that follow it are sacred and stay as written.
- **`tariff_event_study` Beat 3 opener** contains a fake self-correction:
  `Two de-escalation... wait, no — two events, one lesson.` → `Two events, one lesson.`

### 3. Scripts and README

Same voice pass applied to **comments and docstrings only** in
`scripts/make_data.py`, `make_data_congress.py`, `make_data_media.py`,
`make_data_tariff.py`. No logic changes, no schema changes.

`README_week1_notebooks.md` prose is tightened. Its **TODO list** and **Design
decisions worth remembering** sections stay intact — they are working notes, not
intern-facing copy.

### 4. Anchor flag list

Delivered as a section of this document, not as notebook edits. These anchors look
like unverified placeholders and need a real Colab run to fix:

| Notebook | Cell | Anchor | Issue |
|---|---|---|---|
| `bill_classifier` | 10 | `likely somewhere in the 80–95% range` | Range, not a captured value |
| `media_framing` | 14 | `likely somewhere in the **60–85%** range` | README flags this explicitly as needing replacement |
| `congress_mentions` | 9 | `210 mentions in 1990 → 1048 in 2024 (peak: ...)` | Literal ellipsis placeholder |
| `congress_mentions` | 17 | `Marco Rubio peaked at ... mentions in 20...` | Two literal ellipsis placeholders |

Per `README_week1_notebooks.md`, the bill_classifier notebook has seven "What you
should see" numbers pending replacement from a real run. Verifying them requires
Colab, which is out of reach here — hence flag-only.

---

## Mechanics

**Editing method.** All notebook edits go through `NotebookEdit` or a Python JSON
round-trip using `json.load` / `json.dump` with `ensure_ascii=False` and explicit
`encoding="utf-8"`. Raw-text editing of `.ipynb` files with the Edit tool is
prohibited — JSON string escaping is error-prone and this repo's content triggers
cp1252 encoding failures on Windows.

**Preservation.** Cell outputs, cell metadata, execution counts, and notebook-level
metadata are preserved unchanged. Cell order and cell count do not change; no cells
are added or deleted.

**Lossless round-trip test — first step, before any prose edit.** Run the full
read/write cycle on one notebook making **zero** changes, then confirm `git diff` is
empty. A naive `json.load` → `json.dump` can silently reflow untouched cells (key
order, indent width, `source` array splitting, trailing newline, nbformat fields),
producing a large noisy diff that defeats human review even when no content changed.
If the diff is not empty, fix the round-trip or switch to `NotebookEdit` before
touching any prose.

**Order of work.** One notebook at a time, `git diff` reviewed after each, so a bad
pass is contained to one file.

---

## Verification

1. `git diff --stat` shows changes confined to `notebooks/*.ipynb`,
   `scripts/make_data*.py`, and `README_week1_notebooks.md`.
2. A script asserts, for each notebook: cell count unchanged, every code cell's
   `source` byte-identical to the pre-edit version, every `outputs` array unchanged,
   and every markdown cell **not on the intended edit list** byte-identical. The last
   clause is what guarantees the diff is confined to cells this spec named.
3. `json.load` succeeds on all four notebooks (valid JSON, valid nbformat), plus
   **structural assertions** on markdown content, run before and after and compared:
   - Count of `▶️ JUST RUN`, `✏️ YOUR TURN`, and `# <-- EDIT` markers is unchanged.
   - Count of `> **What you should see:**` blockquote boxes is unchanged.
   - Count of `**If you get a red error:**` hints is unchanged.
   - Every `## ` section header is present with the same text, minus stripped emoji.
   - The multiset of all numeric literals (integers, decimals, percentages, dates,
     year ranges) extracted from markdown is **identical** before and after. This is
     the strongest single check: it proves the em-dash pass did not disturb any
     anchor value, count, or date while rewriting the prose around it.
4. `git diff` on markdown cells reviewed by hand — every changed line is prose.
5. Anchor flag list in this document confirmed complete against a grep for
   ellipsis-in-anchor and range-in-anchor patterns.

Criterion 2 is the important one: it is a mechanical guarantee that no code changed,
which no amount of diff-reading provides on its own.

---

## Out of scope

- Running the notebooks in Colab or verifying any output value
- Replacing anchor numbers (flag only)
- Setting the `YOUR-ORG` URL
- Real-data swaps for any CSV
- Restructuring beats, adding or removing exercises, changing the template
- Any change to `data/*.csv`

---

## Estimated blast radius

~35–45 markdown cells across four notebooks (roughly 80–90% of all prose cells, driven
almost entirely by the general em-dash pass), plus comment blocks in four scripts and
prose in one README. Zero code-cell changes.

Because the em-dash pass touches most cells, the diff is large by design and criterion 2
cannot lean on "few cells changed" as a safety net. The real guarantees are criterion 2's
code-cell and outputs assertions plus criterion 3's structural assertions — those hold
regardless of how many prose cells move.
