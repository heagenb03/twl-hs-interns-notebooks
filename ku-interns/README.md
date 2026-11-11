# KU Interns: Intro to Python + AI, then R

A one-hour live session for econ and poli sci interns with little or no coding
background. Interns don't memorize syntax: they direct Gemini in Colab, read the
code it writes, and check whether the answers are right. The R homework repeats
the same three questions in RStudio, with one rule: the R numbers must match the
Python numbers.

## Contents

| Path | Who it's for | What it is |
|---|---|---|
| `notebooks/tariff_intro.ipynb` | Interns | The session notebook. Distributed via OneDrive; interns upload it to Colab. |
| `notebooks/tariff_intro_ANSWER_KEY.ipynb` | Instructor | Filled-in notebook with expected values, instructor notes, and the hook chart. |
| `RUN_SHEET.md` | Instructor | Minute-by-minute plan, prompt demo script, traps and what to say. |
| `r_homework/README.md` | Interns | Install steps, tasks, and what to turn in. |
| `r_homework/tariff_homework.R` | Interns | Starter script with the tasks as comments. |
| `r_homework/tariff_homework_ANSWER_KEY.R` | Instructor | Working solution; matches the Python key. |
| `data/tariff_prices.csv` | Both | Daily closes for SPY, FXI, BA, CAT, SOYB, AAPL, 2017-01-03 to 2020-06-30. Copy of `hs-interns/data/tariff_prices.csv`; provenance in `hs-interns/data/PROVENANCE.md`. |
| `scripts/make_notebooks.py` | Maintainer | Generates both notebooks from one source so the student and answer-key versions never drift. |

## Expected values

| Question | Answer |
|---|---|
| Hook: SPY on 2019-08-23 | -2.6% |
| Task 1: BA vs SOYB, 2018-01-02 to 2019-12-31 | BA +9.7%, SOYB -11.8% |
| Task 2: FXI after the Sunday 2019-05-05 tweet | -2.61% (Fri 5/3 close 44.91 to Mon 5/6 close 43.74) |
| Task 3 | Day-0 table for all six events in the answer key |

## Regenerating the notebooks

Edit `scripts/make_notebooks.py`, then from the repo root:

```bash
python3 ku-interns/scripts/make_notebooks.py ku-interns/notebooks
```
