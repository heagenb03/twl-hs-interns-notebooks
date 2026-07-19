# STATUS — twl-hs-interns-notebooks

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-07-19

---

## ✅ Done

<!-- Move items here from "🚀 Next phase" when finished. Group by area. -->

### Specs
- **Notebook prose cleanup design** — `docs/superpowers/specs/2026-07-19-notebook-prose-cleanup-design.md`
  (approved by Heagen 2026-07-19, commits a01166a → dc1c62a)

---

## 🚀 Next phase

**Goal:** Execute the approved prose cleanup across the four Week 1 notebooks, the
`scripts/make_data_*.py` comments, and `README_week1_notebooks.md`.

### Acceptance criteria
1. Voice tells removed: "sit with", "in one breath/sitting", rhetorical setups,
   "Welcome!" openers, emoji in headers.
2. General em-dash density reduced across prose (Heagen-approved wider scope).
3. Three redundancy cases fixed (bill_classifier cell 3, wrap-up bullets, tariff
   Beat 3 fake self-correction).
4. Zero code-cell changes; numeric-literal multiset in markdown identical before/after.
5. Anchor flag list delivered for Heagen's separate Colab pass.

### Files to create / edit
| Type | File | Content |
|---|---|---|
| edit | `notebooks/*.ipynb` (4) | markdown cells only |
| edit | `scripts/make_data*.py` (4) | comments/docstrings only |
| edit | `README_week1_notebooks.md` | prose only; TODO + design-decisions sections untouched |

### Closed decisions
- Sacred: template markers, "What you should see" boxes, all numbers, `YOUR-ORG`
  placeholder, repeated intro blocks, `data/*.csv`.
- Anchor numbers are flagged, not fixed — no Colab access here.
- Em-dash pass = general density reduction, not just triads.

### Open decisions
- (none — spec approved)

---

## 📁 Active architecture

- **Stack:** _<frameworks, libraries, runtime>_
- **Key tables / modules:** _<list>_
- **Patterns:** _<conventions enforced project-wide>_

---

## ⚠️ External blockers (don't block coding)

- _<env vars, secrets, external accounts, manual steps>_

---

## 🔧 Useful commands

```bash
# add the most-used commands here so the next session has them ready
```

---

## 📚 References (read IF needed)

- `.wolf/cerebrum.md` — User Preferences + Do-Not-Repeat + Decision Log
- `.wolf/anatomy.md` — token-efficient file index
- `.wolf/buglog.json` — known bugs + fixes
