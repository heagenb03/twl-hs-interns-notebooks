# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-07-19

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

- [2026-07-19] Heagen does a **manual editing pass after** AI cleanup work on the
  notebooks. Default to conservative/surgical edits and leave judgment calls for him,
  unless he explicitly widens scope.
- [2026-07-19] On prose voice: he considers these AI tells and wants them gone —
  "sit with"/"worth sitting with", "in one breath"/"in one sitting", rhetorical setups
  ("Now the fun part", "Here's a fair question"), "Welcome!" openers, and emoji in
  headers. He also wants **general em-dash density reduction**, not just the triad
  pattern (he overrode a recommendation to narrow it).

## Key Learnings

- **Project:** twl-hs-interns-notebooks
- **Description:** Notebooks for the Summer of '26 HS Interns at TWL
- The `▶️ JUST RUN` / `✏️ YOUR TURN` markers, "What you should see" anchor boxes,
  "Things to try" ladders, and Week 2 bridges are an **approved pedagogical template**
  (documented in `README_week1_notebooks.md`), NOT AI slop. Never strip them.
- The near-identical "Step zero — this is YOUR copy" / "How this notebook works" intro
  blocks are intentional: each notebook is a standalone personal Drive copy for a
  different intern, so each must carry its own instructions. Not redundancy.
- Several anchor numbers are unverified placeholders pending a real Colab run
  (`80–95%`, `60–85%`, literal `...` ellipses). Cannot be fixed from here — flag only.
- The `YOUR-ORG` URL placeholder (one per notebook) is a tracked TODO, not a bug.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- [2026-07-19] Printing notebook markdown to stdout on Windows crashes with
  `UnicodeEncodeError` (cp1252) because of the emoji. Always set `PYTHONIOENCODING=utf-8`
  and pass `encoding="utf-8"` explicitly when reading/writing these files.
- [2026-07-19] Never hand-edit `.ipynb` files with the Edit tool. JSON string escaping
  is error-prone. Use `NotebookEdit` or a verified-lossless `json.load`/`json.dump`
  round-trip with `ensure_ascii=False`.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->
