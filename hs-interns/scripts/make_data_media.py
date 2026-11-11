"""Synthetic headlines in the STYLE of four outlets across six US-China events.
All headlines are invented (no real headlines reproduced), written to carry
each outlet's characteristic framing so both the sentiment beat and the
outlet-classifier beat have signal. 4 outlets x 6 events x 3 = 72 rows."""
import pandas as pd

H = []
def add(event, outlet, *headlines):
    for h in headlines:
        H.append((event, outlet, h))

E = "2018 tariff announcement"
add(E, "NYT",
    "U.S. Imposes Sweeping Tariffs on Chinese Goods, Deepening Trade Rift",
    "As Tariffs Take Effect, American Farmers Brace for Retaliation",
    "Trade War With China Enters New Phase, With No Exit in Sight")
add(E, "WSJ",
    "Stocks Slide as New China Tariffs Rattle Supply Chains",
    "Manufacturers Warn Tariffs Will Raise Costs for U.S. Consumers",
    "Companies Scramble to Reroute Sourcing Ahead of Tariff Deadline")
add(E, "Fox",
    "Trump Gets Tough on China After Decades of One-Sided Trade",
    "Finally, a President Willing to Stand Up to Beijing's Cheating",
    "China on Notice: America Won't Be Ripped Off Anymore")
add(E, "Xinhua",
    "China Urges U.S. to Correct Mistakes and Return to Dialogue",
    "U.S. Protectionism Harms Global Economy, Experts Say",
    "China Will Firmly Defend Its Legitimate Rights and Interests")

E = "Huawei CFO arrest"
add(E, "NYT",
    "Arrest of Huawei Executive Threatens Fragile U.S.-China Truce",
    "Huawei Case Puts Canada in the Middle of a Superpower Standoff",
    "Detention of Tech Executive Raises Stakes in Trade Negotiations")
add(E, "WSJ",
    "Huawei Arrest Sends Chill Through Global Tech Supply Chain",
    "Investors Weigh Fallout as Huawei Case Complicates Trade Talks",
    "Telecom Suppliers Reassess China Exposure After High-Profile Arrest")
add(E, "Fox",
    "Huawei Arrest Exposes China's Global Espionage Playbook",
    "Communist China's Tech Giant Finally Faces American Justice",
    "Why the Huawei Case Proves China Can't Be Trusted With 5G")
add(E, "Xinhua",
    "China Demands Immediate Release of Unlawfully Detained Citizen",
    "Huawei Case Reveals Political Motives Behind U.S. Tech Suppression",
    "International Community Questions U.S. Abuse of Judicial Process")

E = "Phase One deal"
add(E, "NYT",
    "U.S. and China Sign Initial Trade Deal, Leaving Hard Issues Unresolved",
    "Phase One Agreement Pauses Trade War but Settles Little",
    "A Truce, Not a Peace: What the Trade Deal Actually Changes")
add(E, "WSJ",
    "Markets Shrug as Long-Awaited Phase One Deal Is Signed",
    "Deal Commits China to Big Purchases, but Enforcement Questions Loom",
    "Tariffs Stay in Place as Both Sides Claim Victory in Trade Pact")
add(E, "Fox",
    "Historic Win: Trump Trade Deal Forces China to Buy American",
    "Trump Delivers Where Past Presidents Failed on China Trade",
    "America First Pays Off as Beijing Signs Landmark Deal")
add(E, "Xinhua",
    "China, U.S. Reach Win-Win Agreement Through Equal Dialogue",
    "Phase One Deal Shows Cooperation Benefits Both Peoples",
    "Agreement Proves Dialogue, Not Pressure, Resolves Differences")

E = "TikTok ban push"
add(E, "NYT",
    "Push to Ban TikTok Tests the Limits of Digital-Age Security Fears",
    "TikTok's Fate Becomes a Flashpoint in U.S.-China Tech Rivalry",
    "Lawmakers Weigh TikTok Ban as Evidence Remains Contested")
add(E, "WSJ",
    "Advertisers Draft Contingency Plans as TikTok Ban Gains Momentum",
    "TikTok Ban Would Reshape Social-Media Ad Market, Analysts Say",
    "Investors Circle TikTok's U.S. Assets Amid Forced-Sale Talk")
add(E, "Fox",
    "TikTok Is Chinese Spyware in Your Kid's Pocket, Experts Warn",
    "Ban TikTok Now: Beijing's Data Grab Targets American Teens",
    "How the Chinese Communist Party Uses TikTok to Watch You")
add(E, "Xinhua",
    "U.S. TikTok Crackdown Exposes Hypocrisy on Free Markets",
    "Suppressing TikTok Reveals U.S. Fear of Fair Competition",
    "China Opposes Politicization of Normal Business Operations")

E = "Hong Kong security law"
add(E, "NYT",
    "Sweeping Security Law Redraws the Boundaries of Hong Kong Life",
    "In Hong Kong, a Chill Descends as New Law Takes Hold",
    "Security Law Marks the End of an Era for Hong Kong's Freedoms")
add(E, "WSJ",
    "Banks Reassess Hong Kong Hub Status After Security Law Passes",
    "Security Law Clouds Hong Kong's Future as a Financial Center",
    "Capital Flight Fears Rise as Hong Kong's Legal Autonomy Erodes")
add(E, "Fox",
    "Beijing Crushes Hong Kong Freedom While the World Watches",
    "China's Broken Promise: Hong Kong Handover Deal Shredded",
    "Communist Crackdown in Hong Kong Shows China's True Face")
add(E, "Xinhua",
    "National Security Law Restores Stability and Order in Hong Kong",
    "Hong Kong Residents Welcome Return to Prosperity and Safety",
    "Law Safeguards One Country, Two Systems for the Long Term")

E = "Spy balloon"
add(E, "NYT",
    "Balloon Episode Reveals How Little Room Remains for U.S.-China Diplomacy",
    "A Balloon Drifts Across America, and Relations Sink With It",
    "After the Balloon, Both Capitals Struggle to Steady the Relationship")
add(E, "WSJ",
    "Balloon Fallout Prompts Companies to Rethink China Contingency Plans",
    "Defense Stocks Rise as Balloon Incident Fuels Spending Calls",
    "Balloon Saga Adds New Friction to Already Strained Business Ties")
add(E, "Fox",
    "Chinese Spy Balloon Floats Over America as Officials Dither",
    "Beijing's Balloon Brazenly Violates U.S. Airspace — Again",
    "Spy Balloon Scandal Proves China Thinks America Is Weak")
add(E, "Xinhua",
    "Civilian Airship Strayed Off Course, China Expresses Regret",
    "U.S. Overreaction to Weather Balloon Poisons Bilateral Ties",
    "Hyping 'Balloon Threat' Serves U.S. Domestic Politics, Analysts Say")

df = pd.DataFrame(H, columns=["event", "outlet", "headline"])
df.to_csv("/home/claude/twl/data/headlines.csv", index=False)
print(len(df), "headlines |", df.outlet.value_counts().to_dict())
