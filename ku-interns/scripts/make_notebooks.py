"""Generate the student notebook and the answer key notebook.

Usage (from the repo root): python3 ku-interns/scripts/make_notebooks.py ku-interns/notebooks
"""
import sys
from pathlib import Path

import nbformat as nbf

OUT = Path(sys.argv[1])
DATA_URL = "https://raw.githubusercontent.com/heagenb03/twl-hs-interns-notebooks/main/ku-interns/data/tariff_prices.csv"


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s):
    return nbf.v4.new_code_cell(s.strip("\n"))


def answer(student_text, key_text, key):
    """A markdown cell interns fill in. Student gets the blank, key gets the filled version."""
    return md(key_text if key else student_text)


def note(text, key):
    """Instructor note: only appears in the answer key."""
    return [md("> **INSTRUCTOR NOTE:** " + text.strip().replace("\n", "\n> "))] if key else []


def task_code(student_placeholder, key_code, key):
    return code(key_code if key else student_placeholder)


EMPTY = "# Your AI-assisted code goes here.\n# Read every line before you run it."


def build(key: bool):
    cells = []

    title = "How Did Markets React to the Trade War?"
    if key:
        title += " (ANSWER KEY)"
    cells.append(md(f"""
# {title}

**KU Trade War Lab: intro to Python with AI**

For the next hour you'll analyze real daily stock prices from the US-China trade war
(2017 to mid-2020). You won't memorize any code. An AI assistant (Gemini, built into
Colab) will write it. Your job is the part the AI can't do for you:

1. **Tell it exactly what you want.** Vague requests get vague code.
2. **Read what it gives you.** Never run a cell you can't explain in one sentence.
3. **Check the answer.** Before you trust a number, say why it's believable.

If you get stuck, ask the AI to *explain* what went wrong, not just to fix it.

### How to open Gemini in Colab
- Click the **Gemini** button near the top right of Colab to open the chat panel, or
- In an empty code cell, click the **generate** link and type your request.

Either works. The chat panel is better for questions like "what does this line do?"
"""))

    if key:
        cells += note("""
**Hook (minutes 0 to 5).** Run the cell below and show this chart before anyone opens
their own notebook. Line to use: "By the end of the hour you'll be able to build this
yourself, and more importantly, prove it's right." The printed number is the answer:
SPY fell **-2.6%** on 2019-08-23.
""", key)
        cells.append(code(f"""
# HOOK CHART (instructor only): SPY around 2019-08-23
import pandas as pd
import matplotlib.pyplot as plt

_p = pd.read_csv("{DATA_URL}", index_col="date", parse_dates=True)
_i = _p.index.get_loc(pd.Timestamp("2019-08-23"))
_chunk = _p["SPY"].iloc[_i - 10:_i + 11] / _p["SPY"].iloc[_i - 1] * 100
plt.figure(figsize=(10, 5))
plt.plot(range(-10, 11), _chunk.values, marker="o")
plt.axvline(0, color="red", linestyle="--", label="Aug 23, 2019: China retaliates")
plt.title("S&P 500 around the Aug 23, 2019 announcement (100 = day before)")
plt.xlabel("trading days from announcement"); plt.ylabel("price index")
plt.legend(); plt.grid(alpha=0.3); plt.show()
print(f"SPY day-0 move: {{(_p['SPY'].iloc[_i] / _p['SPY'].iloc[_i - 1] - 1) * 100:+.1f}}%")
"""))

    # ---------------- Part 1
    cells.append(md("""
---
## Part 1: Read before you write

**RUN THIS CELL.** It loads the data. You don't need to understand it yet; that's the
next step.
"""))
    cells.append(code(f"""
import pandas as pd
import matplotlib.pyplot as plt

DATA_URL = "{DATA_URL}"
prices = pd.read_csv(DATA_URL, index_col="date", parse_dates=True)

prices.head()
"""))
    cells.append(md("""
### Meet the data

| Column | What it is |
|---|---|
| **SPY** | The S&P 500, i.e. "the market" |
| **FXI** | A fund of large Chinese companies |
| **BA** | Boeing (China was a major buyer of its planes) |
| **CAT** | Caterpillar (heavy machinery, big China exposure) |
| **SOYB** | A soybean fund (soybeans were China's main retaliation target) |
| **AAPL** | Apple (built in China, sold in China) |

**YOUR TURN.** Open Gemini and ask it to **explain the cell above line by line**.
Then answer these in the cell below, in your own words:

1. What does one row of `prices` represent?
2. What is down the left side (the "index")?
3. What unit are the numbers in?
4. How many rows are there? (Ask Gemini how to check, then check.)
"""))
    cells.append(task_code(
        "# Use this cell to check things, like how many rows there are.",
        "print(prices.shape)        # (rows, columns)\nprint(prices.index.min(), prices.index.max())",
        key))
    cells.append(answer(
        """
**Our answers:**
1.
2.
3.
4.
""",
        """
**Answers:**
1. One trading day.
2. The date.
3. Dollars: each number is that day's closing price for one share (or fund unit).
4. 879 rows (trading days), 2017-01-03 to 2020-06-30. Weekends and holidays are missing because markets were closed.
""", key))
    cells += note("""
Point at answer 4's last sentence now: "weekends are missing." It's the trap in Task 2.
If anyone says the numbers are percentages or returns, good catch-and-correct moment.
""", key)

    # ---------------- Part 2
    cells.append(md("""
---
## Part 2: How to ask

Compare these two requests for the same chart:

> **Weak:** make a graph of the stocks

> **Strong:** I have a pandas DataFrame called `prices`. Its index is dates and its
> columns are ticker symbols (SPY, FXI, BA, CAT, SOYB, AAPL) holding daily closing
> prices in dollars. Plot SPY from 2018-01-01 to 2018-12-31 as a line chart with
> matplotlib. Label the axes. Keep it short and add a comment on every line.

The strong version gives the AI three things:

- **Context:** what your data is called and what's in it. The AI can't see your screen.
- **Goal:** exactly what you want, including dates and tickers.
- **Constraints:** which tools, and "comment every line" so *you* can read the result.

Copy this template into your prompts for the rest of the session:

```
I have a pandas DataFrame called `prices`. Its index is dates and its columns are
ticker symbols (SPY, FXI, BA, CAT, SOYB, AAPL) holding daily closing prices in dollars.
[WHAT YOU WANT]. Keep it short and add a comment on every line.
```
"""))
    cells += note("""
Demo live on the projector: send the weak prompt first and run whatever comes back
(it usually plots all six tickers on one axis, unreadable, or invents column names).
Then send the strong prompt. Ask the room: "what did the second prompt tell it that
the first didn't?"
""", key)

    # ---------------- Task 1
    cells.append(md("""
---
## Task 1 (together): Boeing vs. soybeans

China's retaliation targeted American soybeans directly, while Boeing was a bargaining
chip in negotiations. **Over 2018 and 2019, which did worse: BA or SOYB?**

**Step 1. YOUR TURN.** Using the template, ask for a line chart of **BA and SOYB from
2018-01-01 to 2019-12-31** on the same chart. Read the code, then run it.
"""))
    cells.append(task_code(EMPTY, """
# Step 1: raw prices on one chart (this is the misleading version)
window = prices.loc["2018-01-01":"2019-12-31", ["BA", "SOYB"]]   # rows in date range, two columns
window.plot(figsize=(10, 5))                                       # one line per column
plt.ylabel("closing price ($)")
plt.title("BA vs SOYB, raw prices")
plt.show()
""", key))
    cells.append(md("""
**Step 2.** Look at the chart. Can you tell what happened to SOYB? Why or why not?
"""))
    cells.append(answer(
        "**Our answer:**",
        "**Answer:** No. BA trades around \\$300 to \\$440 and SOYB around \\$15 to \\$18, so SOYB is a flat line at the bottom. A 10% move in SOYB is less than \\$2, invisible on this scale.",
        key))
    cells.append(md("""
**Step 3. YOUR TURN.** Ask Gemini how to put both on the same scale so you can compare
*percentage* changes. (Hint: start both lines at 100 on the first day.) Then answer the
question: over the two years, what was each one's percentage change?
"""))
    cells.append(task_code(EMPTY, """
# Step 3: rebase each series to 100 on the first day, so lines show % change
window = prices.loc["2018-01-01":"2019-12-31", ["BA", "SOYB"]]
rebased = window / window.iloc[0] * 100          # divide every row by the first row
rebased.plot(figsize=(10, 5))
plt.axhline(100, color="gray", linestyle=":")    # reference line = starting value
plt.ylabel("index (100 = Jan 2, 2018)")
plt.title("BA vs SOYB, rebased to 100")
plt.show()

pct_change = (rebased.iloc[-1] - 100).round(1)   # last value minus 100 = % change
print(pct_change)
""", key))
    cells.append(answer(
        """
**Our answer:** BA changed ___%, SOYB changed ___%.

**Why we believe it:**
""",
        """
**Answer:** BA **+9.7%**, SOYB **-11.8%** (2018-01-02 to 2019-12-31).

**Sanity check:** BA went from \\$296.84 to \\$325.76, about 10% up; SOYB from \\$17.95 to \\$15.83, about 12% down. Both match the raw prices in `prices`.
""", key))
    cells += note("""
Two discussion points if time allows:
- **BA peaked at 148 (Mar 1, 2019), then fell hard.** That fall is mostly the 737 MAX
  grounding after the March 2019 crashes, not the trade war. Good lesson: a chart shows
  *what* happened, not *why*. The AI will happily tell a trade-war story about it if asked.
- **SOYB falls off a cliff in June 2018**, right as the \\$50B tariff list landed
  (June 15) and China named soybeans in its retaliation. That's the clearest
  trade-war fingerprint on this chart.
- **SOYB bottoms at about 80 in May 2019**, right after the Sunday tweet (Task 2).
""", key)

    # ---------------- Task 2
    cells.append(md("""
---
## Task 2 (in pairs): The Sunday tweet

On **Sunday, May 5, 2019**, with trade talks thought to be nearly finished, the
president tweeted that tariffs on \\$200 billion of Chinese goods would rise from 10%
to 25% that Friday. Nobody saw it coming.

**Question: how much did FXI (Chinese companies) move in reaction?**

**Before you prompt,** decide as a pair and write down:
- Which date's price shows the reaction, and why?
- The move compared to *what*?
"""))
    cells.append(answer(
        "**Our plan:**",
        "**Plan:** Markets were closed on Sunday, so the first reaction is Monday 2019-05-06's close. Compare it to the last close *before* the news: Friday 2019-05-03.",
        key))
    cells.append(md("**YOUR TURN.** Now ask Gemini, read the code, and run it."))
    cells.append(task_code(EMPTY, """
# Close on the first trading day after the tweet vs. the last close before it
before = prices.loc[:"2019-05-04", "FXI"].iloc[-1]   # last close on or before Saturday -> Fri May 3
after  = prices.loc["2019-05-05":, "FXI"].iloc[0]    # first close on or after Sunday   -> Mon May 6
move = (after / before - 1) * 100                    # percent change
print(f"FXI: {before} -> {after}, move {move:.2f}%")
""", key))
    cells.append(answer(
        """
**Our answer:** FXI moved ___% on ___ (date).

**Why we believe it:**
""",
        """
**Answer:** FXI moved **-2.6%** (\\$44.91 on Fri May 3 to \\$43.74 on Mon May 6).

**Sanity check:** \\$44.91 x 0.974 is about \\$43.74. The drop is negative (bad news) and a few percent, which is big for one day but not absurd.
""", key))
    cells += note("""
Traps you should see in the room, roughly in this order:
1. **`KeyError: '2019-05-05'`**: they asked for Sunday's price. Let them ask Gemini why. The
   fix is the next trading day, which leads to the "what does day 0 mean" discussion.
2. **The AI silently picks a date.** Some code uses `.loc["2019-05-05":]` and quietly
   returns Monday. Ask the pair: "Which date did your code actually use? Show me."
3. **"-0.026%"**: `pct_change()` returns fractions. -0.026 is -2.6%, not -0.026%.
4. **Compared to Monday's open, or to Sunday?** We only have closing prices, so
   close-to-close is the only option. Good thing to make them say out loud.

Reveal **-2.6%** only after each pair has written their answer. If someone used SPY by
mistake, theirs is -0.41%; follow-up: SPY fell another -1.67% on Tuesday May 7, so
"the reaction" for the broad market took two days.
""", key)

    # ---------------- Task 3
    cells.append(md("""
---
## Task 3 (in pairs): Your own question

**RUN THIS CELL** to see six real trade-war announcement dates. Every date is a trading day.
"""))
    cells.append(code("""
EVENTS = {
    "2018-03-22": "Tariff memo signed (escalation, surprise)",
    "2018-06-15": "25% tariffs on $50B announced (escalation, expected)",
    "2018-12-03": "Buenos Aires truce (de-escalation)",
    "2019-05-06": "First trading day after the Sunday tweet (escalation, surprise)",
    "2019-08-23": "China retaliates; companies 'ordered' out (escalation, surprise)",
    "2020-01-15": "Phase One deal signed (de-escalation, fully expected)",
}
for date, label in EVENTS.items():
    print(date, " ", label)
"""))
    cells.append(md("""
**YOUR TURN.** Pick one event and one ticker. Use the AI to answer: **did that stock
react to that announcement?** You decide what "react" means. Then write one sentence
of findings and one sentence on how you checked it. Be ready to share.
"""))
    cells.append(task_code(EMPTY, """
# Day-0 move for every event and every ticker (close vs. previous trading day's close)
daily_pct = prices.pct_change() * 100              # daily % change for every ticker
table = daily_pct.loc[list(EVENTS)].round(2)       # keep only the six event dates
table.index = [f"{d}  {EVENTS[d][:30]}" for d in EVENTS]
table
""", key))
    cells.append(answer(
        """
**Our finding:**

**How we checked it:**
""",
        """
**Reference values** (day-0 % move, close vs. previous close):

| Event | SPY | FXI | BA | CAT | SOYB | AAPL |
|---|---|---|---|---|---|---|
| 2018-03-22 memo | -2.50 | -3.84 | -5.19 | -5.71 | +0.11 | -1.42 |
| 2018-06-15 \\$50B | -0.57 | -0.55 | -1.25 | -2.04 | -2.07 | -1.03 |
| 2018-12-03 truce | +1.32 | +1.50 | +3.81 | +2.42 | +1.28 | +3.49 |
| 2019-05-06 tweet | -0.41 | -2.61 | -1.29 | -1.65 | -0.94 | -1.55 |
| 2019-08-23 retaliation | -2.57 | -1.82 | +0.45 | -3.25 | -1.20 | -4.63 |
| 2020-01-15 Phase One | +0.23 | -0.56 | -0.77 | -0.76 | -1.34 | -0.43 |
""", key))
    cells += note("""
Good things to draw out during the share-out:
- **Surprise beats importance.** Phase One was the biggest deal of the trade war and
  SPY moved +0.23%. Everyone knew the signing date for weeks, so it was "priced in."
- **"React" needs a baseline.** A -1% day means little if the stock moves 1% on a
  normal day. Ask any pair that says "it dropped" how they know that's unusual.
- **BA on 2019-08-23 rose (+0.45%)** while the market fell 2.6%. Ask: does that mean
  Boeing benefited, or something else was going on?
""", key)

    # ---------------- Wrap-up
    cells.append(md("""
---
## What you just did

- Read AI-written code before running it, and asked it to explain itself.
- Wrote prompts with context, a goal, and constraints.
- Caught a misleading chart (raw prices) and fixed it (rebasing to 100).
- Hit the "markets are closed on Sunday" problem and decided what "the reaction" means.
- Turned a number into a claim you can defend.

## Homework: do it again in R

Next you'll repeat Tasks 1 to 3 in **R using RStudio**. The rule: **your R numbers must
match your Python numbers.** If they don't, one of them has a bug, and finding it is the
assignment. Instructions are in the R homework README.

**Save this notebook before you leave:** File > Download > Download .ipynb, then put it
back in your OneDrive folder.
"""))

    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}
    nb.metadata["colab"] = {"provenance": []}
    return nb


OUT.mkdir(parents=True, exist_ok=True)
nbf.write(build(False), OUT / "tariff_intro.ipynb")
nbf.write(build(True), OUT / "tariff_intro_ANSWER_KEY.ipynb")
print("wrote", OUT)
