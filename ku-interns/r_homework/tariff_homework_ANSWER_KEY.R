# =============================================================================
# KU Trade War Lab: R homework  (ANSWER KEY - do not distribute)
#
# Expected values (must match the Python answer key):
#   Task 1: BA +9.7%, SOYB -11.8%   (2018-01-02 to 2019-12-31)
#   Task 2: FXI -2.61%  (Fri 2019-05-03 close 44.91 -> Mon 2019-05-06 close 43.74)
#   Task 3: depends on the pair's pick; see the day-0 table printed at the end.
# =============================================================================

library(tidyverse)

data_url <- "https://raw.githubusercontent.com/heagenb03/twl-hs-interns-notebooks/main/ku-interns/data/tariff_prices.csv"
prices <- read_csv(data_url, show_col_types = FALSE) |>
  arrange(date)                       # make sure rows are in date order

head(prices)
glimpse(prices)                       # `date` should be <date>, the rest <dbl>


# --- TASK 1 ------------------------------------------------------------------
rebased <- prices |>
  filter(date >= as.Date("2018-01-01"), date <= as.Date("2019-12-31")) |>
  select(date, BA, SOYB) |>
  mutate(across(c(BA, SOYB), \(x) x / first(x) * 100))   # 100 = first day

rebased_long <- rebased |>
  pivot_longer(c(BA, SOYB), names_to = "ticker", values_to = "index")

chart <- ggplot(rebased_long, aes(x = date, y = index, color = ticker)) +
  geom_line() +
  geom_hline(yintercept = 100, linetype = "dotted", color = "gray40") +
  labs(title = "BA vs SOYB, rebased to 100",
       x = NULL, y = "index (100 = Jan 2, 2018)") +
  theme_minimal()
print(chart)
ggsave("tariff_chart.png", chart, width = 8, height = 5)

rebased |>
  slice_tail(n = 1) |>
  mutate(across(c(BA, SOYB), \(x) round(x - 100, 1))) |>
  print()                             # BA 9.7, SOYB -11.8


# --- TASK 2 ------------------------------------------------------------------
tweet_date <- as.Date("2019-05-05")
before <- prices |> filter(date <  tweet_date) |> slice_tail(n = 1)   # Fri May 3
after  <- prices |> filter(date >= tweet_date) |> slice_head(n = 1)   # Mon May 6
fxi_move <- (after$FXI / before$FXI - 1) * 100
cat(sprintf("FXI: %s close %.2f -> %s close %.2f, move %.2f%%\n",
            before$date, before$FXI, after$date, after$FXI, fxi_move))
# Common student bug: filter(date == as.Date("2019-05-05")) returns 0 rows,
# and dividing by an empty value gives numeric(0) instead of an error.


# --- TASK 3 (reference table for grading) ------------------------------------
events <- as.Date(c("2018-03-22", "2018-06-15", "2018-12-03",
                    "2019-05-06", "2019-08-23", "2020-01-15"))
day0 <- prices |>
  mutate(across(-date, \(x) round((x / lag(x) - 1) * 100, 2))) |>
  filter(date %in% events)
print(day0)
