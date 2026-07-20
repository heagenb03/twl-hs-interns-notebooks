# Notebook Prose Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove AI-voice tells and prose redundancy from the four Week 1 intern notebooks, the data-generation scripts, and the week-1 README, without altering a single code cell, anchor number, or template marker.

**Architecture:** A guard-rail script (`tools/nb_check.py`) captures a notebook's invariants before editing and asserts they are unchanged after. Prose edits are then applied one notebook at a time, each gated by that checker and committed separately. The checker is what makes a large prose diff safe to review — it mechanically proves nothing sacred moved, so human review only has to judge writing quality.

**Tech Stack:** Python 3.13 stdlib only (`json`, `re`, `argparse`, `pathlib`). No new dependencies. Git worktree `../twl-nb-prose-cleanup` on branch `prose-cleanup`.

**Spec:** `docs/superpowers/specs/2026-07-19-notebook-prose-cleanup-design.md`

## Global Constraints

These apply to **every** task. Violating any one is a failed task.

- **Never edit a code cell.** Not the logic, not the `# <-- EDIT` sentinels, not the `# ▶️ JUST RUN` / `# ✏️ YOUR TURN` header comments.
- **Never edit a line beginning with `>`.** Every such line in these notebooks is anchor-box content ("What you should see", the `**If you get a red error:**` hints, and their continuation lines). Verified: there are no other blockquotes. These lines must stay **byte-identical** — they are the merge conflict surface against the concurrent real-data-swap work.
- **Never invent a number.** No numeric literal may appear after editing that was not present before. Removing a number by deleting a whole redundant sentence is allowed; changing one is not.
- **Never add or remove cells.** Cell count, order, and `cell_type` sequence are fixed.
- **Never hand-edit `.ipynb` with the Edit tool.** Use the `read_nb` / `write_nb` helpers from Task 1. JSON string escaping is error-prone and these files contain emoji.
- **Exact serialization:** `json.dumps(nb, indent=1, ensure_ascii=False) + "\n"`, written with `newline="\r\n"`. The working tree is CRLF (`core.autocrlf=true`); the git blob is LF. Verified byte-identical during planning against **all four** notebooks (28144 / 18714 / 20840 / 20071 bytes). Task 1 Step 2 re-proves this before any editing.
- **Encoding:** always pass `encoding="utf-8"` explicitly, and set `PYTHONIOENCODING=utf-8` before any command that prints notebook text. Windows defaults to cp1252 and crashes on the emoji.
- **Do not touch:** `data/*.csv`, the `YOUR-ORG` URL placeholder, any anchor value, the repeated "Step zero" / "How this notebook works" intro blocks, `## ` section structure, "Things to try" ladder numbering, Week 2 bridge paragraphs, "Before you close" prompts.

### The four voice tells to remove

1. `sit with` / `sitting with`
2. `in one breath` / `in one sitting`
3. Rhetorical setups: `Now the fun part`, `Here's a fair question`, `Now the trap`, `Forget positive/negative`, and the fake self-correction in tariff Beat 3
4. `Welcome!` openers, and **decorative** emoji in `#` / `##` headers

**The emoji rule, stated explicitly** — the checker cannot enforce this (its header
guard strips all emoji before comparing, so it is deliberately blind to the
distinction). The words are the only specification:

- **Remove** decorative emoji: `🏛️` `📰🔍` `📉⚡` `🏛️📈` `🧠` `🔀` `🧪` `🔬` `🎯`
- **Keep** the template markers `✏️` and `▶️` even when they sit in a header, e.g.
  `## Beat 1 — Measuring the spin ✏️` and `## Beat 3 — Fool it ✏️` keep their `✏️`,
  because that marker tells the intern the section contains an edit cell.
- **Keep** `⚠️` on "Step zero", and `✅` / `❌` wherever they appear — all template.

### The em-dash rule

General density reduction across prose (Heagen approved this wider scope explicitly).

- Replace `—` with a comma, colon, or sentence break wherever the sentence reads the same afterward.
- **Keep** em dashes carrying a true parenthetical (a clause that could sit in parentheses) or a sharp reversal doing real work.
- **Never** substitute a semicolon — too formal for this register.
- **Reduce, don't eliminate.** Zero em dashes reads as over-corrected. Target roughly a 50–70% reduction in prose lines.
- Blockquote (`>`) lines are excluded entirely, per Global Constraints.

Baseline em-dash counts (prose lines only; blockquote counts in parentheses are sacred):

| Notebook | Prose | Blockquote (sacred) |
|---|---|---|
| `bill_classifier.ipynb` | 44 | 8 |
| `congress_mentions.ipynb` | 25 | 3 |
| `media_framing.ipynb` | 35 | 3 |
| `tariff_event_study.ipynb` | 35 | 7 |

---

### Task 1: Guard-rail checker

**Files:**
- Create: `tools/nb_check.py`
- Create: `tools/baseline/` (directory, holds pre-edit snapshots)

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `read_nb(path: str | Path) -> dict` — parse a notebook
  - `write_nb(path: str | Path, nb: dict) -> None` — serialize byte-identically
  - `snapshot(nb: dict) -> dict` — capture invariants
  - CLI: `python tools/nb_check.py snapshot <nb> <out.json>`
  - CLI: `python tools/nb_check.py check <nb> <baseline.json>` — exit 0 pass, 1 fail
  - CLI: `python tools/nb_check.py roundtrip <nb>` — exit 0 if read+write is byte-identical

- [ ] **Step 1: Write the checker**

Create `tools/nb_check.py`:

```python
"""Guard rails for the Week 1 notebook prose cleanup.

Captures a notebook's invariants before editing (`snapshot`) and asserts they
are unchanged afterward (`check`). The prose diff is large by design, so this
is what proves no code, anchor value, or template marker moved.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?%?")
EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # pictographs, symbols, emoticons
    "←-⇿"          # arrows (▶ is not here; see below)
    "─-➿"          # box drawing, misc symbols, dingbats (▶️ ✅ ✏️)
    "⬀-⯿"          # misc symbols and arrows
    "️"                 # variation selector-16
    "]"
)
MARKERS = (
    "▶️ JUST RUN",
    "✏️ YOUR TURN",
    "# <-- EDIT",
    "**What you should see",
    "**If you get a red error:**",
)


def read_nb(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_nb(path: str | Path, nb: dict[str, Any]) -> None:
    text = json.dumps(nb, indent=1, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)


def _src(cell: dict[str, Any]) -> str:
    return "".join(cell["source"])


def _markdown(nb: dict[str, Any]) -> str:
    return "\n".join(
        _src(c) for c in nb["cells"] if c["cell_type"] == "markdown"
    )


def _blockquotes(nb: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "markdown":
            continue
        for line in _src(cell).split("\n"):
            if line.lstrip().startswith(">"):
                out.append(f"{i}:{line}")
    return out


def _headers(nb: dict[str, Any]) -> list[str]:
    return [
        EMOJI_RE.sub("", line).strip()
        for line in _markdown(nb).split("\n")
        if line.startswith("#")
    ]


def _all_text(nb: dict[str, Any]) -> str:
    # Marker counts span both cell types: "▶️ JUST RUN" and "# <-- EDIT"
    # live in code cells too. Counting markdown alone would silently
    # report 0 for "# <-- EDIT" and never catch its removal.
    return "\n".join(_src(c) for c in nb["cells"])


def snapshot(nb: dict[str, Any]) -> dict[str, Any]:
    md = _markdown(nb)
    everything = _all_text(nb)
    return {
        "n_cells": len(nb["cells"]),
        "cell_types": [c["cell_type"] for c in nb["cells"]],
        "code": [_src(c) for c in nb["cells"] if c["cell_type"] == "code"],
        "outputs": [
            json.dumps(c.get("outputs", []), sort_keys=True)
            for c in nb["cells"]
            if c["cell_type"] == "code"
        ],
        "blockquotes": _blockquotes(nb),
        "markers": {m: everything.count(m) for m in MARKERS},
        "headers": _headers(nb),
        "numbers": sorted(NUM_RE.findall(md)),
    }


def check(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    errs: list[str] = []

    for key in ("n_cells", "cell_types", "code", "outputs", "markers", "headers"):
        if before[key] != after[key]:
            errs.append(f"{key} changed")

    if before["blockquotes"] != after["blockquotes"]:
        b, a = set(before["blockquotes"]), set(after["blockquotes"])
        for line in sorted(b - a):
            errs.append(f"blockquote line REMOVED/ALTERED: {line}")
        for line in sorted(a - b):
            errs.append(f"blockquote line ADDED: {line}")

    invented = sorted(set(after["numbers"]) - set(before["numbers"]))
    if invented:
        errs.append(f"invented numbers: {invented}")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["snapshot", "check", "roundtrip"])
    ap.add_argument("notebook")
    ap.add_argument("baseline", nargs="?")
    args = ap.parse_args()

    if args.mode == "roundtrip":
        raw = Path(args.notebook).read_bytes()
        write_nb(args.notebook, read_nb(args.notebook))
        if Path(args.notebook).read_bytes() == raw:
            print(f"OK roundtrip byte-identical: {args.notebook}")
            return 0
        print(f"FAIL roundtrip changed bytes: {args.notebook}")
        return 1

    if args.mode == "snapshot":
        if not args.baseline:
            ap.error("snapshot requires an output path")
        Path(args.baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(args.baseline).write_text(
            json.dumps(snapshot(read_nb(args.notebook)), indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"OK snapshot written: {args.baseline}")
        return 0

    if not args.baseline:
        ap.error("check requires a baseline path")
    before = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    errs = check(before, snapshot(read_nb(args.notebook)))
    if errs:
        print(f"FAIL {args.notebook}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"OK {args.notebook} — all invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Prove the round-trip is lossless**

This is the gate. If it fails, stop and fix `write_nb` before touching any prose.

Run:
```bash
cd ../twl-nb-prose-cleanup
for f in notebooks/*.ipynb; do PYTHONIOENCODING=utf-8 python tools/nb_check.py roundtrip "$f" || exit 1; done
git diff --stat
```

Expected: four `OK roundtrip byte-identical` lines, and **`git diff --stat` prints nothing**.

- [ ] **Step 3: Prove the checker passes on unmodified notebooks**

Run:
```bash
cd ../twl-nb-prose-cleanup
for f in notebooks/*.ipynb; do
  n=$(basename "$f" .ipynb)
  PYTHONIOENCODING=utf-8 python tools/nb_check.py snapshot "$f" "tools/baseline/$n.json"
  PYTHONIOENCODING=utf-8 python tools/nb_check.py check "$f" "tools/baseline/$n.json" || exit 1
done
```

Expected: four `OK snapshot written` then four `OK ... all invariants hold`.

- [ ] **Step 4: Prove the checker actually catches violations**

A checker that never fails is worthless. Verify each guard fires:

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python - <<'EOF'
import sys; sys.path.insert(0, "tools")
from nb_check import read_nb, snapshot, check

nb = read_nb("notebooks/bill_classifier.ipynb")
base = snapshot(nb)

def mutate(fn, label):
    import copy
    m = copy.deepcopy(nb)
    fn(m)
    errs = check(base, snapshot(m))
    print(f"{label}: {'CAUGHT ' + errs[0] if errs else 'NOT CAUGHT <-- BUG'}")

# 1. edited code cell
mutate(lambda m: m["cells"][11]["source"].insert(0, "x = 1\n"), "code edit")
# 2. altered anchor number inside a blockquote
def bust_anchor(m):
    c = m["cells"][14]
    c["source"] = [s.replace("3.1%", "9.9%") for s in c["source"]]
mutate(bust_anchor, "anchor number")
# 3. deleted a template marker
def bust_marker(m):
    c = m["cells"][1]
    c["source"] = [s.replace("▶️ JUST RUN", "run it") for s in c["source"]]
mutate(bust_marker, "marker removal")
# 4. invented a number in a prose (non-blockquote) line
#    Cell 20's "Things to try" sits below the anchor box, so this isolates
#    the numbers guard instead of tripping headers or blockquotes first.
def bust_number(m):
    c = m["cells"][20]
    c["source"] = [
        s.replace("How high can you push its score?",
                  "How high can you push its score toward 99?")
        for s in c["source"]
    ]
mutate(bust_number, "invented number")

# 5. POSITIVE CONTROL: these are legitimate edits and must NOT be caught.
def strip_header_emoji(m):
    c = m["cells"][0]
    c["source"] = [s.replace("About China? 🏛️", "About China?") for s in c["source"]]
mutate(strip_header_emoji, "emoji strip (must NOT be caught)")

def drop_wrapup_bullet(m):
    c = m["cells"][29]
    c["source"] = [s for s in c["source"] if "trained a text classifier" not in s]
mutate(drop_wrapup_bullet, "wrap-up bullet removal (must NOT be caught)")
EOF
```

Expected output:

```
code edit: CAUGHT code changed
anchor number: CAUGHT blockquote line REMOVED/ALTERED: ...
marker removal: CAUGHT markers changed
invented number: CAUGHT invented numbers: ['99']
emoji strip (must NOT be caught): NOT CAUGHT <-- BUG
wrap-up bullet removal (must NOT be caught): NOT CAUGHT <-- BUG
```

The last two are **expected and correct** despite the `<-- BUG` text the helper prints —
they prove the checker permits the edits this plan requires. Tests 1–4 must print
`CAUGHT`; if any prints `NOT CAUGHT`, fix the checker before proceeding.

All six behaviors above were verified against the real notebook during planning.

- [ ] **Step 5: Commit**

```bash
cd ../twl-nb-prose-cleanup
git add tools/nb_check.py tools/baseline/
git commit -m "test: add notebook invariant checker for prose cleanup

Captures code cells, outputs, blockquote anchor lines, template marker
counts, headers, and numeric literals before editing; asserts them
unchanged after. Round-trip verified byte-identical (indent=1, CRLF)."
```

---

### Task 2: Clean `bill_classifier.ipynb`

**Files:**
- Modify: `notebooks/bill_classifier.ipynb` (markdown cells only)
- Uses: `tools/nb_check.py`, `tools/baseline/bill_classifier.json`

**Interfaces:**
- Consumes: `read_nb`, `write_nb`, and the `check` CLI from Task 1
- Produces: nothing consumed by later tasks (notebook tasks are independent)

Editable markdown cells: `0, 1, 3, 8, 12, 15, 18, 21, 26, 29` (pure prose) and the
**non-blockquote portions** of `5, 7, 10, 14, 17, 20, 23, 25, 28`. Cells in the second
group contain an anchor box followed by "Things to try" — edit only the part after the
blockquote ends.

- [ ] **Step 1: Apply the named tell edits**

These are exact. Apply each by locating the cell, replacing the substring, and writing
back via `write_nb`.

| Cell | Before | After |
|---|---|---|
| 0 | `# Can a Computer Tell if a Bill is About China? 🏛️` | `# Can a Computer Tell if a Bill is About China?` |
| 0 | `Welcome! In this notebook you'll work with a real machine-learning model` | `In this notebook you'll work with a real machine-learning model` |
| 8 | `Here's the plan, in one breath: a *language model* turns` | `Here's the plan: a *language model* turns` |
| 14 | `3. Now the fun part — **be sneaky.** Can you write` | `3. **Be sneaky.** Can you write` |
| 14 | `**A question to sit with:** the model never gives you` | `**One more question:** the model never gives you` |
| 18 | `Here's a fair question: do we even need machine learning for this?` | `Do we even need machine learning for this?` |
| 26 | `## Stretch goal (optional) — swap the brain 🧠` | `## Stretch goal (optional) — swap the brain` |
| 29 | `In one sitting, with about ten lines of edited Python, you:` | `With about ten lines of edited Python, you:` |

- [ ] **Step 2: Trim the two redundancy cases**

**Cell 3** — drop the sentence that re-explains the label convention already stated in
cell 0's "How this notebook works" block. Keep the data description and the `▶️ JUST RUN` line.

**Cell 29** — the wrap-up bullets restate each beat's thesis a third time. Trim each
bullet to its factual claim, dropping the editorializing tail. Keep all five bullets,
keep the Week 2 bridge paragraph and "Before you close" prompt **verbatim** (sacred).

Worked example for the shape wanted — the last two bullets:

Before:
```
- proved why learned meaning beats keyword matching,
- and saw that the model's report card is only as trustworthy as its human labels.
```

After:
```
- compared learned meaning against keyword matching,
- and saw that the model's report card depends on its human labels.
```

The claims survive; "proved why", "beats", and "only as trustworthy as" are the
editorializing that goes. Apply the same shape to the other three bullets and to the
wrap-up cells in Tasks 3, 4, and 5.

- [ ] **Step 3: Apply the em-dash pass**

44 prose em-dashes. Target roughly 15–22 remaining. Worked examples:

| Before | After |
|---|---|
| `**No coding experience needed.** Almost everything is pre-written. In a few marked spots you'll edit a line of real Python — a sentence, a number, or a list — and watch what changes.` | keep — true parenthetical, both dashes doing work |
| `- Cells marked **▶️ JUST RUN** — run them, don't edit them.` | `- Cells marked **▶️ JUST RUN**: run them, don't edit them.` |
| `That percentage is nice, but it's just a number. The interesting question is *how* the model gets things right and wrong — and that's what the rest of this notebook is about.` | `... right and wrong, and that's what the rest of this notebook is about.` |
| `Score above it: "about China." Below: "not."` | unchanged (no em dash) |
| `Same model, same scores, different threshold — because the **cost of being wrong** is different in each direction.` | `... different threshold, because the **cost of being wrong** is different in each direction.` |

- [ ] **Step 4: Run the checker**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python tools/nb_check.py check \
  notebooks/bill_classifier.ipynb tools/baseline/bill_classifier.json
```

Expected: `OK notebooks/bill_classifier.ipynb — all invariants hold`

If it fails, **fix the notebook, not the checker or the baseline.** A failure means a
sacred invariant moved.

- [ ] **Step 5: Read the diff**

```bash
cd ../twl-nb-prose-cleanup && git diff notebooks/bill_classifier.ipynb
```

Confirm by eye that every changed line is prose. The checker proves nothing sacred
moved; this step judges whether the writing actually got better.

- [ ] **Step 6: Commit**

```bash
cd ../twl-nb-prose-cleanup
git add notebooks/bill_classifier.ipynb
git commit -m "docs: prose cleanup for bill_classifier notebook

Remove voice tells (sit with, in one breath, in one sitting, Welcome!
opener, header emoji, rhetorical setups), trim duplicated label-convention
explanation and wrap-up bullets, reduce em-dash density. Anchor boxes,
code cells, and template markers unchanged (verified by tools/nb_check.py)."
```

---

### Task 3: Clean `congress_mentions.ipynb`

**Files:**
- Modify: `notebooks/congress_mentions.ipynb` (markdown cells only)
- Uses: `tools/nb_check.py`, `tools/baseline/congress_mentions.json`

**Interfaces:**
- Consumes: `read_nb`, `write_nb`, and the `check` CLI from Task 1
- Produces: nothing consumed by later tasks

Editable markdown cells: `0, 1, 7, 10, 13, 18, 21` (pure prose) and the non-blockquote
portions of `3, 5, 9, 12, 15, 17, 20`.

- [ ] **Step 1: Apply the named tell edits**

| Cell | Before | After |
|---|---|---|
| 0 | `# When Did Congress Start Talking About China? 🏛️📈` | `# When Did Congress Start Talking About China?` |
| 0 | `Welcome! In this notebook you'll dig through **35 years**` | `In this notebook you'll dig through **35 years**` |
| 12 | `3. Here's the thing worth sitting with: **no human read these speeches.**` | `3. Worth noticing: **no human read these speeches.**` |
| 18 | `## Stretch goal (optional) — the crossover 🔀` | `## Stretch goal (optional) — the crossover` |

- [ ] **Step 2: Trim the wrap-up bullets**

**Cell 21** — trim the three bullets to their factual claims. The bullet
`watched the vocabulary around "China" shift from *trade, WTO, most-favored-nation* to
*CCP, threat, genocide* — a historical narrative produced by counting` restates Beat 2's
item 3, which you just edited; drop the trailing clause after the em dash and keep the
shift itself. Keep the Week 2 bridge and "Before you close" prompt **verbatim**.

Note: this cell contains the numbers `2000` and `2017`. Removing a whole bullet
containing them is permitted (the checker only blocks *invented* numbers), but prefer
keeping them — they're the notebook's two findings.

- [ ] **Step 3: Apply the em-dash pass**

25 prose em-dashes. Target roughly 8–12 remaining. Worked examples:

| Before | After |
|---|---|
| `Japan was the China of the '90s — trade fights, fear of being overtaken, all of it. Then it faded.` | keep — the dash introduces a genuine list gloss |
| `Its spikes are sharp and event-shaped (2014, 2022). Compare the *shape* of the Russia line to the China line — one spikes on events, the other climbs and stays.` | `... to the China line: one spikes on events, the other climbs and stays.` |
| `**Handoff:** the vocabulary changed. But an average hides individuals — did all of Congress change together, or did a few people drag the average? Beat 3.` | `... hides individuals. Did all of Congress change together, or did a few people drag the average? Beat 3.` |

- [ ] **Step 4: Run the checker**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python tools/nb_check.py check \
  notebooks/congress_mentions.ipynb tools/baseline/congress_mentions.json
```

Expected: `OK notebooks/congress_mentions.ipynb — all invariants hold`

- [ ] **Step 5: Read the diff**

```bash
cd ../twl-nb-prose-cleanup && git diff notebooks/congress_mentions.ipynb
```

Confirm every changed line is prose.

- [ ] **Step 6: Commit**

```bash
cd ../twl-nb-prose-cleanup
git add notebooks/congress_mentions.ipynb
git commit -m "docs: prose cleanup for congress_mentions notebook

Remove voice tells (worth sitting with, Welcome! opener, header emoji),
trim wrap-up bullets, reduce em-dash density. Anchor boxes, code cells,
and template markers unchanged (verified by tools/nb_check.py)."
```

---

### Task 4: Clean `media_framing.ipynb`

**Files:**
- Modify: `notebooks/media_framing.ipynb` (markdown cells only)
- Uses: `tools/nb_check.py`, `tools/baseline/media_framing.json`

**Interfaces:**
- Consumes: `read_nb`, `write_nb`, and the `check` CLI from Task 1
- Produces: nothing consumed by later tasks

Editable markdown cells: `0, 1, 9, 12, 19, 22, 25` (pure prose) and the non-blockquote
portions of `3, 5, 7, 11, 14, 16, 18, 21, 24`.

Cell 0 has the highest em-dash count in the repo (11).

- [ ] **Step 1: Apply the named tell edits**

| Cell | Before | After |
|---|---|---|
| 0 | `# Same Story, Different Headlines 📰🔍` | `# Same Story, Different Headlines` |
| 0 | `Welcome! In this notebook you'll compare how four very different outlets` | `In this notebook you'll compare how four very different outlets` |
| 11 | `3. Now the trap. Try `"Hong Kong security law"`` | ``3. Now the trap: try `"Hong Kong security law"``` |
| 12 | `Forget positive/negative. A harder question: can a model tell **who wrote it**` | `A harder question: can a model tell **who wrote it**` |
| 22 | `## Stretch goal (optional) — style or subject? 🧪` | `## Stretch goal (optional) — style or subject?` |
| 12 | `## Beat 2 — Guess the outlet 🎯` | `## Beat 2 — Guess the outlet` |

- [ ] **Step 2: Trim the wrap-up bullets**

**Cell 25** — five bullets, each restating a beat. Trim to factual claims. Keep the
Week 2 bridge and "Before you close" prompt **verbatim**.

Do **not** touch the synthetic-data disclosure in cell 0 (`**A note on the data:** the
headlines in this notebook are written *in the style of* each outlet...`). It is a
factual disclosure, not filler, and the concurrent real-data-swap work depends on it.

- [ ] **Step 3: Apply the em-dash pass**

35 prose em-dashes, 11 of them in cell 0. Target roughly 12–17 remaining. Worked examples:

| Before | After |
|---|---|
| `compare how four very different outlets — the New York Times, the Wall Street Journal, Fox News, and China's state agency Xinhua — headline the *same* US-China events` | keep — true parenthetical listing the four outlets |
| `they're not scraped real headlines. The framing patterns they carry are the real subject.` | unchanged (no em dash) |
| `- Cells run **top to bottom** — click a cell, press **Shift+Enter** (or ▶).` | `- Cells run **top to bottom**: click a cell, press **Shift+Enter** (or ▶).` |
| `negative at *the U.S.* ("overreaction," "poisons ties"). Sentiment tells you the emotional charge, but not the **target**.` | unchanged (no em dash) |
| `You're mapping the model's learned features by hand — this is a real research technique` | `You're mapping the model's learned features by hand. This is a real research technique` |

- [ ] **Step 4: Run the checker**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python tools/nb_check.py check \
  notebooks/media_framing.ipynb tools/baseline/media_framing.json
```

Expected: `OK notebooks/media_framing.ipynb — all invariants hold`

- [ ] **Step 5: Read the diff**

```bash
cd ../twl-nb-prose-cleanup && git diff notebooks/media_framing.ipynb
```

Confirm every changed line is prose, and that the synthetic-data disclosure survives intact.

- [ ] **Step 6: Commit**

```bash
cd ../twl-nb-prose-cleanup
git add notebooks/media_framing.ipynb
git commit -m "docs: prose cleanup for media_framing notebook

Remove voice tells (Now the trap, Forget positive/negative, Welcome!
opener, header emoji), trim wrap-up bullets, reduce em-dash density.
Synthetic-data disclosure, anchor boxes, code cells, and template markers
unchanged (verified by tools/nb_check.py)."
```

---

### Task 5: Clean `tariff_event_study.ipynb`

**Files:**
- Modify: `notebooks/tariff_event_study.ipynb` (markdown cells only)
- Uses: `tools/nb_check.py`, `tools/baseline/tariff_event_study.json`

**Interfaces:**
- Consumes: `read_nb`, `write_nb`, and the `check` CLI from Task 1
- Produces: nothing consumed by later tasks

Editable markdown cells: `0, 1, 5, 7, 10, 13, 18, 21` (pure prose) and the
non-blockquote portions of `3, 9, 12, 15, 17, 20`.

**Careful with cell 3:** it contains the "Meet the cast" markdown **table** of tickers.
Ticker rows are data — leave the table untouched.

- [ ] **Step 1: Apply the named tell edits**

| Cell | Before | After |
|---|---|---|
| 0 | `# How Fast Do Markets React to Trade Announcements? 📉⚡` | `# How Fast Do Markets React to Trade Announcements?` |
| 0 | `Welcome! In this notebook you'll replay the US-China trade war` | `In this notebook you'll replay the US-China trade war` |
| 13 | `Two de-escalation... wait, no — two events, one lesson.` | `Two events, one lesson.` |
| 15 | `1. Sit with the weirdness: signing the deal that paused the trade war moved markets *less* than one tweet.` | `1. Signing the deal that paused the trade war moved markets *less* than one tweet.` |
| 18 | `## Stretch goal (optional) — beyond the market 🔬` | `## Stretch goal (optional) — beyond the market` |

- [ ] **Step 2: Trim the wrap-up bullets**

**Cell 21** — four bullets. Trim to factual claims; the "priced in" bullet in particular
restates Beat 3 item 1 nearly verbatim. Keep the Week 2 bridge and "Before you close"
prompt **verbatim**.

- [ ] **Step 3: Apply the em-dash pass**

35 prose em-dashes. Target roughly 12–17 remaining. Worked examples:

| Before | After |
|---|---|
| `You'll pick real announcement dates — tariff threats, truces, a famous Sunday tweet — and watch exactly how prices responded` | keep — true parenthetical |
| `Professionals answer by subtracting the market's move — what's left is the stock's **abnormal return**.` | `Professionals answer by subtracting the market's move. What's left is the stock's **abnormal return**.` |
| `Markets don't slowly digest news over weeks; the reaction is concentrated in the first day` | unchanged (existing semicolon, not ours to add or remove) |
| `So what moves markets isn't news — it's **surprise**, the gap between what happened and what was expected.` | keep — sharp reversal, the dash earns its place |
| `Soybeans were China's chosen retaliation weapon — aimed at US farmers.` | `Soybeans were China's chosen retaliation weapon, aimed at US farmers.` |

- [ ] **Step 4: Run the checker**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python tools/nb_check.py check \
  notebooks/tariff_event_study.ipynb tools/baseline/tariff_event_study.json
```

Expected: `OK notebooks/tariff_event_study.ipynb — all invariants hold`

- [ ] **Step 5: Read the diff**

```bash
cd ../twl-nb-prose-cleanup && git diff notebooks/tariff_event_study.ipynb
```

Confirm every changed line is prose and the "Meet the cast" table is intact.

- [ ] **Step 6: Commit**

```bash
cd ../twl-nb-prose-cleanup
git add notebooks/tariff_event_study.ipynb
git commit -m "docs: prose cleanup for tariff_event_study notebook

Remove voice tells (fake self-correction in Beat 3, Sit with the
weirdness, Welcome! opener, header emoji), trim wrap-up bullets, reduce
em-dash density. Meet-the-cast table, anchor boxes, code cells, and
template markers unchanged (verified by tools/nb_check.py)."
```

---

### Task 6: Clean scripts and README

**Files:**
- Modify: `scripts/make_data_media.py` (comments only)
- Modify: `README_week1_notebooks.md` (prose only)
- Leave alone: `scripts/make_data.py`, `make_data_congress.py`, `make_data_tariff.py`, `README.md`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: nothing consumed by later tasks

**Scoping note — do not manufacture work here.** A scan found the scripts are already
clean: zero em dashes in three of four, zero voice tells, zero emoji across all four.
Only `make_data_media.py` has any (2 em dashes). `README.md` is two lines and needs
nothing. The spec approved scripts as in-scope, but the honest finding is that there is
almost nothing to do. Do not invent edits to justify the task.

The concurrent real-data-swap work plans to restructure these generators into a
fetch/build split, so keep changes minimal — anything that session rewrites wholesale
should take its version on merge.

- [ ] **Step 1: Fix the two em dashes in `make_data_media.py`**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 grep -n "—" scripts/make_data_media.py
```

Apply the em-dash rule to those two comment lines only. If both dashes are true
parentheticals, leave them and say so — no change is a valid outcome.

- [ ] **Step 2: Clean `README_week1_notebooks.md`**

16 em dashes and 6 emoji. Apply the em-dash rule to prose.

**Sacred in this file:** the `## TODOs before freeze, in order` list and the
`## Design decisions worth remembering` section are Heagen's working notes, not
intern-facing copy. Leave both **verbatim**, including their em dashes.

That leaves `## The set` (table + paragraph), `## Repo layout`, and
`## Verified in sandbox` as the editable prose.

Also correct one stale fact while here: the layout block says
`trade-war-lab-notebooks/ ├── notebooks/ └── data/`, but `scripts/` is now tracked
(commit `e3a8a5d`). Add it:

```
twl-hs-interns-notebooks/
├── notebooks/  (4 .ipynb)
├── scripts/    (4 make_data_*.py)
└── data/       (6 .csv)
```

- [ ] **Step 3: Verify nothing else changed**

```bash
cd ../twl-nb-prose-cleanup
git diff --stat
PYTHONIOENCODING=utf-8 python -c "import ast,glob; [ast.parse(open(f,encoding='utf-8').read()) for f in glob.glob('scripts/*.py')]; print('OK all scripts still parse')"
```

Expected: diff limited to `scripts/make_data_media.py` and `README_week1_notebooks.md`;
`OK all scripts still parse`.

- [ ] **Step 4: Commit**

```bash
cd ../twl-nb-prose-cleanup
git add scripts/make_data_media.py README_week1_notebooks.md
git commit -m "docs: prose cleanup for scripts and week-1 README

Reduce em-dash density in README prose and one generator's comments; add
scripts/ to the documented repo layout. TODO list and design-decisions
notes left verbatim as working notes."
```

---

### Task 7: Anchor flag list and final verification

**Files:**
- Create: `docs/superpowers/notes/2026-07-19-anchor-flags.md`

**Interfaces:**
- Consumes: `tools/nb_check.py` (for the final full-suite run)
- Produces: the flag list Heagen uses during his Colab pass

- [ ] **Step 1: Regenerate the flag list from the current notebooks**

Do not copy the list from the spec — derive it, so it reflects reality after editing.

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python - <<'EOF'
import glob, json, re, os
pat = re.compile(r"\.\.\.|\b\d+\s*[–-]\s*\d+\s*%")
for f in sorted(glob.glob("notebooks/*.ipynb")):
    nb = json.loads(open(f, encoding="utf-8").read())
    for i, c in enumerate(nb["cells"]):
        if c["cell_type"] != "markdown":
            continue
        for line in "".join(c["source"]).split("\n"):
            if line.lstrip().startswith(">") and pat.search(line):
                print(f"{os.path.basename(f)} [cell {i}] {line.strip()}")
EOF
```

- [ ] **Step 2: Write the note**

Create `docs/superpowers/notes/2026-07-19-anchor-flags.md` with a header explaining
these need a real Colab run, then a table of the grep output: notebook, cell, the
anchor text, and why it's suspect (`literal ellipsis placeholder` or
`range instead of a captured value`). Include the note from
`README_week1_notebooks.md` that `bill_classifier` has seven "What you should see"
numbers pending replacement.

- [ ] **Step 3: Run the full checker suite one final time**

```bash
cd ../twl-nb-prose-cleanup
for f in notebooks/*.ipynb; do
  n=$(basename "$f" .ipynb)
  PYTHONIOENCODING=utf-8 python tools/nb_check.py check "$f" "tools/baseline/$n.json" || exit 1
done
echo "ALL NOTEBOOKS PASS"
```

Expected: four `OK` lines then `ALL NOTEBOOKS PASS`.

- [ ] **Step 4: Confirm every notebook still opens as valid nbformat**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python -c "
import json, glob
for f in sorted(glob.glob('notebooks/*.ipynb')):
    nb = json.load(open(f, encoding='utf-8'))
    assert nb['nbformat'] == 4, f
    print(f, 'nbformat', nb['nbformat'], 'cells', len(nb['cells']))
print('OK')
"
```

Expected: four lines with unchanged cell counts (30, 22, 26, 22), then `OK`.

- [ ] **Step 5: Report remaining em-dash counts**

```bash
cd ../twl-nb-prose-cleanup
PYTHONIOENCODING=utf-8 python - <<'EOF'
import glob, json, os
for f in sorted(glob.glob("notebooks/*.ipynb")):
    nb = json.loads(open(f, encoding="utf-8").read())
    q = p = 0
    for c in nb["cells"]:
        if c["cell_type"] != "markdown":
            continue
        for line in "".join(c["source"]).split("\n"):
            if line.lstrip().startswith(">"):
                q += line.count("—")
            else:
                p += line.count("—")
    print(f"{os.path.basename(f):28} prose={p:3} blockquote={q:3}")
EOF
```

Expected: blockquote counts **exactly** 8, 3, 3, 7 (unchanged); prose counts reduced
from 44, 25, 35, 35 into the target bands.

- [ ] **Step 6: Commit**

**`docs/` is gitignored in this repo.** `git add` without `-f` would stage nothing and
this commit would silently create nothing, losing the task's only deliverable —
and `git status` would never show the file either, so the failure is invisible. The
`-f` below is required, not optional.

```bash
cd ../twl-nb-prose-cleanup
git add -f docs/superpowers/notes/2026-07-19-anchor-flags.md
git status --short   # must list the note as staged (A) before committing
git commit -m "docs: flag unverified notebook anchor values for Colab pass

Anchors that are literal ellipsis placeholders or ranges rather than
captured values. Cannot be fixed without running the notebooks."
```

- [ ] **Step 7: Report to Heagen**

Summarize: per-notebook em-dash before/after, which tells were removed, what the
checker verified, and that the branch is ready for his manual pass. Note that merging
to `main` should wait until the real-data-swap work lands, and that anchor-box
conflicts resolve in favor of the data-swap version.

---

## Notes for the implementer

**When the checker fails, the notebook is wrong.** Never edit the baseline or loosen
the checker to make a failure go away. The one exception: if Task 1 Step 4 shows a
guard is not firing, that's a checker bug and should be fixed then, before any prose
work begins.

**The em-dash pass is judgment work.** The tables above give worked examples, not an
exhaustive list — enumerating all 139 substitutions would be doing the task rather than
planning it. Apply the rule, keep the dashes that earn their place, and let the target
bands tell you if you have gone too far or not far enough.

**Heagen does a manual pass after this.** When a call is genuinely borderline, leave it
for him. That is the posture he asked for, and it is why every other edit class in this
plan stayed surgical.
