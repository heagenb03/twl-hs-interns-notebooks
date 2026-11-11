# R Homework: The Trade War, Again

In the Colab session you answered three questions about the trade war in Python.
Now answer the same three in **R**, using **RStudio**.

**The rule: your R numbers must match your Python numbers.** If they don't, one
of them has a bug. Finding it is part of the assignment.

**Due:** [DUE DATE]

---

## 1. Install R and RStudio (do this first)

You need both: **R** is the language, **RStudio** is the program you write it in.
Install R first.

1. **R:** go to <https://cran.r-project.org>, pick your operating system, and
   install the latest version.
   - Mac: choose the `.pkg` that matches your chip (Apple silicon = `arm64`,
     older Intel Macs = `x86_64`). Not sure? Apple menu > About This Mac.
   - Windows: "Download R for Windows" > "base" > the download link at the top.
2. **RStudio Desktop:** go to <https://posit.co/download/rstudio-desktop/> and
   install it.
3. Open **RStudio** (not R). In the **Console** pane (bottom left), type this
   and press Enter. It takes a few minutes:

   ```r
   install.packages("tidyverse")
   ```

4. Test it. In the Console, run `library(tidyverse)`. A list of package names
   with check marks means it worked. A red `Error` means it didn't (see below).

### If installation fails

- **"there is no package called 'tidyverse'"**: step 3 didn't finish. Run it again
  and wait for the `>` prompt to come back.
- **Mac asks to install "command line developer tools":** click Install, wait, then
  redo step 3.
- **Windows warning about "Rtools":** you can ignore it for this assignment.
- **Still stuck:** copy the full red error into a chatbot along with "I'm installing
  R and RStudio on [Mac/Windows] for the first time." If that doesn't fix it, message
  me with a screenshot. Don't lose an evening to it.

---

## 2. Get the starter script

Download `tariff_homework.R` from the OneDrive folder and open it in RStudio
(File > Open File). Rename it to `tariff_homework_YOURNAME.R`.

The script already loads the data. Each task is written as comments, with space
for your code underneath.

**To run code:** put your cursor on a line and press **Ctrl+Enter** (Windows) or
**Cmd+Enter** (Mac). Output shows up in the Console; charts show up in the Plots
pane (bottom right).

---

## 3. Using AI for this

RStudio doesn't have a free AI assistant built in, so keep a chatbot (Gemini,
ChatGPT, Claude, whatever you like) open in a browser tab. Same habits as the
Colab session:

- **Give it context.** It can't see your screen. Start prompts with:

  ```
  I'm using R with the tidyverse. I have a tibble called `prices` with a `date`
  column and columns SPY, FXI, BA, CAT, SOYB, AAPL holding daily closing prices
  in dollars. [WHAT YOU WANT]. Add a comment on every line.
  ```

- **Read before you run.** Copy code into the script one piece at a time, and
  make sure you can say what each line does.
- **Ask it to translate, then check.** "Here's my Python code, write the R
  version" is a fine prompt. But the numbers decide if it's right, not the AI.

---

## 4. The tasks

| Task | What to do | Your Python answer to match |
|---|---|---|
| **1** | Chart BA and SOYB from 2018-01-01 to 2019-12-31, **rebased to 100**, using `ggplot2`. Save it with `ggsave()`. Print each one's % change over the period. | Task 1, Step 3 |
| **2** | FXI's move after the Sunday, May 5, 2019 tweet: first trading day after vs. last close before. | Task 2 |
| **3** | Same event and ticker you picked in Task 3. Compute the same number your pair reported. | Task 3 |

---

## 5. What to turn in

Upload to your folder in OneDrive:

1. **`tariff_homework_YOURNAME.R`** with your code, and your three answers filled
   in at the bottom of the script.
2. **`tariff_chart.png`**, the chart from Task 1 (created by `ggsave()`).

Make sure the script runs from top to bottom without errors: in RStudio, click
**Source** (top right of the script pane). If it reaches the end without red
errors, you're good.

---

You'll see **R Markdown** / **Quarto** (`.Rmd` / `.qmd` files) in your econ and
poli sci courses. They combine code, output, and writing in one document. Same
R, different file type. A plain script is enough for now.
