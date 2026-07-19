# anatomy.md

> Auto-maintained by OpenWolf. Last scanned: 2026-07-19T14:59:01.700Z
> Files: 23 tracked | Anatomy hits: 0 | Misses: 0

## ./

- `.gitignore` — Git ignore rules (~3 tok)
- `CLAUDE.md` — OpenWolf (~57 tok)
- `README_week1_notebooks.md` — Week 1 Notebooks — Full Handoff (~1259 tok)
- `README.md` — Project documentation (~20 tok)

## .claude/

- `settings.json` (~514 tok)

## .claude/commands/

- `reframe.md` — Mode: migrate [framework] (~551 tok)
- `security-audit.md` — Layer 1 — Dependencies (~510 tok)

## .claude/rules/

- `openwolf.md` (~328 tok)

## .cursor/rules/

- `openwolf.mdc` (~87 tok)

## data/

- `bills_china.csv` (~3803 tok)
- `congress_companions.csv` (~224 tok)
- `congress_mentions.csv` (~1185 tok)
- `congress_senators.csv` (~607 tok)
- `headlines.csv` (~1627 tok)
- `tariff_prices.csv` (~11807 tok)

## notebooks/

- `bill_classifier.ipynb` (~7262 tok)
- `congress_mentions.ipynb` (~4821 tok)
- `media_framing.ipynb` (~5361 tok)
- `tariff_event_study.ipynb` (~5176 tok)

## scripts/

- `make_data_congress.py` — Placeholder data for the Congressional Record notebook. Three CSVs. (~1148 tok)
  - fn `curve` L10-51 (~683 tok)
  - fn `sen` L52-82 (~372 tok)
- `make_data_media.py` — Synthetic headlines in the STYLE of four outlets across six US-China events. (~1721 tok)
  - fn `add` L8-123 (~1626 tok)
- `make_data_tariff.py` — Placeholder daily prices for the tariff event-study notebook. (~604 tok)
- `make_data.py` — Generate placeholder congressional bill snippets for the Week 1 bill classifier notebook. (~4547 tok)
