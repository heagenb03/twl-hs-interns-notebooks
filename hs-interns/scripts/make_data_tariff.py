"""Placeholder daily prices for the tariff event-study notebook.
Six real trade-war announcement dates with SYNTHETIC but plausibly-sized
market reactions injected into a random walk. Sensitivities differ by ticker
so China-exposed names (FXI, BA, SOYB) move more than SPY."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(11)
dates = pd.bdate_range("2017-01-03", "2020-06-30")

# date: (day-0 SPY return, next-day follow-through, label)
EVENTS = {
    "2018-03-22": (-0.025, -0.019, "Tariff memo signed (escalation, surprise)"),
    "2018-06-15": (-0.009, -0.004, "25% tariffs on $50B announced (escalation, expected)"),
    "2018-12-03": (+0.011, +0.004, "Buenos Aires truce (de-escalation)"),
    "2019-05-06": (-0.017, -0.007, "Sunday tweet: tariffs to 25% (escalation, surprise)"),
    "2019-08-23": (-0.026, -0.011, "China retaliates; 'ordering' companies out (escalation, surprise)"),
    "2020-01-15": (-0.001, +0.002, "Phase One deal signed (de-escalation, fully expected)"),
}
SENSITIVITY = {"SPY": 1.0, "FXI": 1.6, "BA": 1.8, "CAT": 1.5, "SOYB": 1.3, "AAPL": 1.4}
VOL = {"SPY": 0.008, "FXI": 0.013, "BA": 0.016, "CAT": 0.013, "SOYB": 0.010, "AAPL": 0.015}
START = {"SPY": 227, "FXI": 35, "BA": 158, "CAT": 93, "SOYB": 19, "AAPL": 29}

event_idx = {pd.Timestamp(d): v for d, v in EVENTS.items()}
frames = {}
for tk in SENSITIVITY:
    rets = rng.normal(0.0004, VOL[tk], len(dates))
    for i, d in enumerate(dates):
        if d in event_idx:
            r0, r1, _ = event_idx[d]
            rets[i] = r0 * SENSITIVITY[tk] + rng.normal(0, 0.002)
            if i + 1 < len(rets):
                rets[i + 1] = r1 * SENSITIVITY[tk] + rng.normal(0, 0.003)
    frames[tk] = START[tk] * np.exp(np.cumsum(rets))

prices = pd.DataFrame(frames, index=dates).round(2)
prices.index.name = "date"
prices.to_csv("/home/claude/twl/data/tariff_prices.csv")

# print anchor numbers: day-0 returns for two key events
for d in ["2019-08-23", "2020-01-15"]:
    i = dates.get_loc(pd.Timestamp(d))
    print(d, {tk: f"{(frames[tk][i]/frames[tk][i-1]-1)*100:+.1f}%" for tk in ["SPY", "FXI", "BA"]})
