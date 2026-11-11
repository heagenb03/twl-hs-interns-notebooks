# =============================================================================
# KU Trade War Lab: R homework
# Name:
#
# Same three questions as the Colab session, now in R.
# Rule: your R numbers must match your Python numbers.
# Run a line with Ctrl+Enter (Windows) or Cmd+Enter (Mac).
# =============================================================================

library(tidyverse)

# --- Load the data (already done for you) ------------------------------------
data_url <- "https://raw.githubusercontent.com/heagenb03/twl-hs-interns-notebooks/main/ku-interns/data/tariff_prices.csv"
prices <- read_csv(data_url, show_col_types = FALSE)

# Look at it before doing anything else. What is one row? What type is `date`?
head(prices)
glimpse(prices)


# =============================================================================
# TASK 1: Boeing vs. soybeans
# -----------------------------------------------------------------------------
# a) Keep only dates from 2018-01-01 to 2019-12-31 and the BA and SOYB columns.
# b) Rebase each one to 100 on the first day (divide by its first value, x 100).
# c) Plot both on one ggplot line chart. Label the axes and add a title.
#    Hint: ggplot works best with "long" data, one row per date per ticker.
#    Ask your chatbot about pivot_longer().
# d) Save the chart:  ggsave("tariff_chart.png", width = 8, height = 5)
# e) Print each one's % change over the whole period.
# =============================================================================




# =============================================================================
# TASK 2: The Sunday tweet
# -----------------------------------------------------------------------------
# The tweet came on Sunday, 2019-05-05. Markets were closed.
# Compute FXI's % move: first trading day AFTER the tweet vs. last close BEFORE it.
# Print both dates you used, so you can see which ones your code picked.
# =============================================================================




# =============================================================================
# TASK 3: Your own question
# -----------------------------------------------------------------------------
# Use the same event and ticker you picked in the Colab session.
# Compute the same number you reported there.
# =============================================================================




# =============================================================================
# YOUR ANSWERS (fill these in)
# -----------------------------------------------------------------------------
# Task 1:  BA changed ____%,  SOYB changed ____%
# Task 2:  FXI moved ____% on ____ (date)
# Task 3:  Event ________  Ticker ____  Result ________
#
# Did all three match your Python numbers? If one didn't at first, what was wrong?
#
# =============================================================================
