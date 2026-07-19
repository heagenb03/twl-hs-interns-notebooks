"""Placeholder data for the Congressional Record notebook. Three CSVs.
Shapes are historically plausible (PNTR bump ~2000, post-2017 China surge,
early-90s Japan trade fights, 2022 Russia spike) but values are SYNTHETIC."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
years = np.arange(1990, 2025)

def curve(base, bumps, growth=0.0):
    """base level + gaussian bumps [(center, height, width)] + optional late growth."""
    v = np.full(len(years), float(base))
    for c, h, w in bumps:
        v += h * np.exp(-0.5 * ((years - c) / w) ** 2)
    v *= (1 + growth) ** np.clip(years - 2016, 0, None)
    v += rng.normal(0, base * 0.08, len(years))
    return np.maximum(v, 5).round().astype(int)

term_curves = {
    "china":     curve(210, [(2000, 380, 1.2), (2008, 90, 3)], growth=0.22),
    "japan":     curve(180, [(1992, 340, 2.5)]) - np.clip((years - 1995) * 6, 0, 130),
    "russia":    curve(160, [(2014, 220, 1.5), (2017, 260, 1.5), (2022, 900, 1.5)]),
    "taiwan":    curve(60,  [(1996, 90, 1.5), (2000, 60, 1.5)], growth=0.28),
    "tariff":    curve(45,  [(2002, 60, 1.5)], growth=0.45),
    "trade":     curve(600, [(1993, 500, 1.5), (2000, 420, 1.8), (2018, 380, 2)]),
    "terrorism": curve(80,  [(2003, 900, 3.0)]),
    "climate":   curve(70,  [(2009, 260, 2), (2019, 200, 3)]),
}
rows = [(int(y), t, int(c)) for t, cs in term_curves.items() for y, c in zip(years, cs)]
pd.DataFrame(rows, columns=["year", "term", "mentions"]).to_csv(
    "/home/claude/twl/data/congress_mentions.csv", index=False)

companions = {
    "1990s": {"trade": 480, "most-favored-nation": 350, "human rights": 310, "WTO": 260,
              "Taiwan": 180, "Tiananmen": 160, "normalization": 140, "imports": 120,
              "prison labor": 90, "Hong Kong": 85},
    "2000s": {"WTO": 420, "trade deficit": 390, "currency": 330, "manufacturing": 300,
              "jobs": 280, "imports": 240, "outsourcing": 200, "intellectual property": 150,
              "Taiwan": 110, "human rights": 105},
    "2010s": {"currency manipulation": 340, "intellectual property": 320, "South China Sea": 290,
              "cyber": 270, "trade war": 250, "tariffs": 240, "jobs": 180,
              "North Korea": 150, "Taiwan": 140, "espionage": 120},
    "2020s": {"CCP": 620, "threat": 560, "Taiwan": 520, "competition": 470,
              "supply chains": 430, "genocide": 380, "TikTok": 340, "fentanyl": 310,
              "espionage": 280, "semiconductors": 260},
}
rows = [(era, w, c) for era, d in companions.items() for w, c in d.items()]
pd.DataFrame(rows, columns=["era", "word", "count"]).to_csv(
    "/home/claude/twl/data/congress_companions.csv", index=False)

sen_years = np.arange(2010, 2025)
def sen(base, surge_start=None, surge_rate=0.0, first_year=2010):
    out = []
    for y in sen_years:
        if y < first_year:
            out.append(0); continue
        v = base
        if surge_start and y >= surge_start:
            v = base * (1 + surge_rate) ** (y - surge_start)
        out.append(int(max(v + rng.normal(0, base * 0.15), 1)))
    return out

senators = {
    "Tom Cotton":       sen(14, 2018, 0.55, first_year=2015),
    "Marco Rubio":      sen(18, 2018, 0.45, first_year=2011),
    "Josh Hawley":      sen(55, 2019, 0.30, first_year=2019),
    "Chuck Schumer":    sen(35, 2018, 0.12),
    "Mitch McConnell":  sen(16, 2018, 0.18),
    "Elizabeth Warren": sen(10, 2018, 0.15, first_year=2013),
    "Sherrod Brown":    sen(24, 2018, 0.10),
    "Senate average":   sen(9,  2018, 0.28),
}
rows = [(name, int(y), v) for name, vals in senators.items()
        for y, v in zip(sen_years, vals) if v > 0]
pd.DataFrame(rows, columns=["senator", "year", "mentions"]).to_csv(
    "/home/claude/twl/data/congress_senators.csv", index=False)

m = pd.read_csv("/home/claude/twl/data/congress_mentions.csv")
c = m[m.term == "china"].set_index("year").mentions
print("china:", c[1990], c[2000], c[2017], c[2024], "| japan 1992:", 
      m[(m.term=='japan')&(m.year==1992)].mentions.iloc[0])
