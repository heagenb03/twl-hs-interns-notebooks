# Run Sheet: Intro to Python + AI (Thu 4:30 to 5:30)

Keep this and the answer key notebook open on your own screen.

## Before the session

- [ ] `tariff_intro.ipynb` is in the interns' OneDrive folder. `tariff_intro_ANSWER_KEY.ipynb` and the R answer key are somewhere they **can't** see.
- [ ] `r_homework/README.md` and `tariff_homework.R` are in OneDrive. Put the due date in the README (it currently says `[DUE DATE]`).
- [ ] Run the answer key top to bottom in Colab once (Runtime > Run all) to confirm the data URL loads and Gemini works on your account.
- [ ] Have the hook chart (first code cell of the answer key) ready on the projector.
- [ ] Interns know to bring laptops and be signed into a Google account.

## Minute by minute

| Time | Segment | What you do |
|---|---|---|
| 4:30 | **Hook** (5 min) | Show the 2019-08-23 chart. "You'll build this yourself and prove it's right." Then: download the notebook from OneDrive, upload it to Colab (File > Upload notebook). |
| 4:35 | **Part 1: read before you write** (10 min) | Everyone runs the load cell and asks Gemini to explain it line by line. Cold-call 2 to 3 people for the four questions. Stress "weekends are missing" (it comes back in Task 2). |
| 4:45 | **Part 2: how to ask** (5 min) | Live demo: weak prompt, then strong prompt (script below). |
| 4:50 | **Task 1, together** (10 min) | You drive on the projector while they follow. Hit the raw-price problem, fix it by rebasing. Answer: BA +9.7%, SOYB -11.8%. |
| 5:00 | **Task 2, in pairs** (12 min) | Pairs write their plan *before* prompting. Walk the room. Reveal **FXI -2.6%** only after every pair has written an answer. |
| 5:12 | **Task 3, in pairs** (10 min) | Pick an event and ticker, one finding plus how they checked it. |
| 5:22 | **Share-out** (5 min) | 2 to 3 pairs present. Push on "how do you know?" |
| 5:27 | **R handoff** (3 min) | Script below. |

If you run behind, cut Task 3 to 5 minutes and make it "pick a row of the table and explain it." Don't cut the pair work in Task 2; it's the core of the session.

## Prompt demo script (Part 2)

1. In a new cell, type the weak prompt: **"make a graph of the stocks"**. Run what it gives you.
2. Ask the room: "Is this useful? What did it have to guess?" (It guessed which stocks, which dates, maybe even the column names.)
3. Send the strong prompt from the notebook. Run it.
4. Ask: "What did the second prompt tell it that the first didn't?" Get them to name **context, goal, constraints**.
5. Point at "add a comment on every line": "That part isn't for the AI, it's for you. You're the one who has to check it."

## Traps, and what to say

**Task 1**
- *Raw-price chart, SOYB flat:* "Did soybeans not move at all, or is something wrong with the chart?" Let them work out the scale problem.
- *Someone reports a dollar change instead of a percent:* "Is \$29 a lot for a \$300 stock? For an \$18 one?"
- *Bonus if asked why BA fell in 2019:* the 737 MAX grounding (March 2019), not the trade war. A chart shows what happened, not why.

**Task 2** (expect these roughly in order)
- *`KeyError: '2019-05-05'`:* don't fix it for them. "Ask Gemini what the error means. Then look at your Part 1 answers."
- *The code quietly used some other date:* "Which date did your code actually use? Print it."
- *"-0.026%":* "Is that a 2.6% drop or a 0.026% drop? How would you know?"
- *A pair used SPY:* -0.41% on Monday, then another -1.67% on Tuesday. Good follow-up: how long does "the reaction" take?

**Task 3**
- *"It dropped, so it reacted":* "Compared to what? Is 1% a big day for this stock?"
- *Phase One (2020-01-15) barely moved:* this is the "priced in" lesson. Everyone knew the date for weeks.
- *BA rose (+0.45%) on 2019-08-23 while the market fell 2.6%:* ask them why before you suggest anything.

## Common technical problems

- **`NameError: name 'prices' is not defined`:** they skipped the load cell or the runtime restarted. Runtime > Run before.
- **Gemini button missing:** refresh the page, and make sure they're signed in. As a fallback, pair them with a neighbor.
- **Pasted code fails on a column name:** the AI made it up. Good moment: "What does your prompt tell it about the columns?"

## R handoff script (5:27)

"Homework: same three questions, in R with RStudio. Instructions are in the README in OneDrive. Install R and RStudio **tonight**, not the night before it's due; installing is the part most likely to go wrong. The rule is that your R numbers have to match your Python numbers. Turn in your `.R` file and your chart PNG to OneDrive by [DUE DATE]. And download your Colab notebook before you close the tab."
