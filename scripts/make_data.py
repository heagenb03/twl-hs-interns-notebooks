"""Generate placeholder congressional bill snippets for the Week 1 bill classifier notebook.

Four pools:
  - direct positives (explicit China mentions)
  - indirect positives (Indo-Pacific, semiconductors, Taiwan, etc. -- the "sneaky" set)
  - clear negatives (domestic policy)
  - hard negatives / borderline (trade with allies, country-neutral export controls)

Borderline items get mixed labels on purpose so the logistic-regression head produces
genuinely uncertain probabilities and the threshold beat works.
"""
import random
import pandas as pd

random.seed(42)

direct_pos = [
    ("Countering Chinese Communist Party Influence Act", "To counter the malign influence of the Chinese Communist Party in international organizations and to require annual reports on CCP-affiliated entities operating in the United States."),
    ("China Trade Enforcement Act", "To direct the United States Trade Representative to investigate unfair trade practices by the People's Republic of China and impose duties on subsidized imports."),
    ("Hong Kong Human Rights and Democracy Act", "To require annual certification of Hong Kong's autonomy from the People's Republic of China as a condition for special trade treatment."),
    ("Uyghur Forced Labor Prevention Act", "To prohibit the importation of goods produced with forced labor in the Xinjiang Uyghur Autonomous Region of the People's Republic of China."),
    ("PRC Military Companies Sanctions Act", "To impose sanctions on companies affiliated with the People's Liberation Army of the People's Republic of China."),
    ("Chinese Currency Accountability Act", "To require the Secretary of the Treasury to analyze whether the People's Republic of China is manipulating the exchange rate of the renminbi."),
    ("Beijing Winter Olympics Accountability Act", "To express the sense of Congress regarding the participation of United States officials in the Beijing Winter Olympic Games."),
    ("China Grid Security Act", "To prohibit the acquisition of bulk-power system equipment manufactured in the People's Republic of China."),
    ("Protecting America From Chinese Espionage Act", "To enhance counterintelligence efforts against espionage activities directed by the Government of the People's Republic of China."),
    ("China Financial Threat Mitigation Act", "To require a report on exposure of the United States financial system to the People's Republic of China."),
    ("Stop CCP Land Grabs Act", "To prohibit the purchase of agricultural land in the United States by entities owned or controlled by the Government of the People's Republic of China."),
    ("Chinese Fentanyl Sanctions Act", "To impose sanctions with respect to the trafficking of synthetic opioids originating in the People's Republic of China."),
    ("Taiwan Relations Reinforcement Act", "To reaffirm the commitment of the United States to Taiwan in the face of military pressure from the People's Republic of China."),
    ("China Exchange Rate Transparency Act", "To direct United States representatives at international financial institutions to advocate for exchange rate transparency by China."),
    ("Countering China's Belt and Road Act", "To develop a strategy to provide alternatives to financing offered by China under the Belt and Road Initiative."),
    ("Ban Chinese Drones Act", "To prohibit Federal agencies from procuring unmanned aircraft systems manufactured in the People's Republic of China."),
    ("China Pandemic Accountability Act", "To require a determination regarding the origins of COVID-19 and the role of the Government of the People's Republic of China in early reporting."),
    ("Fair Trade With China Enforcement Act", "To amend the Harmonized Tariff Schedule to increase duties on goods imported from the People's Republic of China in strategic sectors."),
    ("Chinese Student Visa Security Act", "To require additional screening of visa applicants affiliated with universities connected to the military of the People's Republic of China."),
    ("Hold China Accountable Act", "To authorize civil actions against the Government of the People's Republic of China for damages relating to intellectual property theft."),
]

indirect_pos = [
    ("Indo-Pacific Deterrence Act", "To strengthen the posture of the United States Armed Forces in the Indo-Pacific region and enhance security cooperation with regional allies facing coercion."),
    ("Semiconductor Supply Chain Security Act", "To reduce reliance on foreign adversaries for the fabrication of advanced semiconductors and to incentivize domestic chip manufacturing."),
    ("Taiwan Strait Stability Act", "To require an annual assessment of military balance across the Taiwan Strait and contingency planning for cross-strait conflict."),
    ("Confucius Institute Transparency Act", "To require institutions of higher education to disclose contracts with foreign government-sponsored cultural and language programs."),
    ("South China Sea Freedom of Navigation Act", "To reaffirm the commitment of the United States to freedom of navigation operations in the South China Sea and adjacent waters."),
    ("Rare Earth Independence Act", "To establish a strategic reserve of rare earth elements and reduce dependence on a single dominant foreign supplier of critical minerals."),
    ("Foreign Apps Data Security Act", "To restrict social media applications owned by ByteDance or subject to the jurisdiction of foreign adversary governments from Federal devices."),
    ("Xinjiang Supply Chain Transparency Act", "To require issuers to disclose whether their supply chains source polysilicon, cotton, or tomatoes from the Xinjiang region."),
    ("Pacific Islands Partnership Act", "To expand diplomatic and development engagement with Pacific Island nations in response to growing strategic competition in the region."),
    ("Hong Kong Autonomy Review Act", "To review export control treatment of a special administrative region following the imposition of a national security law."),
    ("Countering Economic Coercion Act", "To develop tools to support allies and partners subjected to economic coercion by an adversarial trading power in the Asia-Pacific."),
    ("Quad Cooperation Enhancement Act", "To deepen cooperation among the United States, Japan, India, and Australia on maritime security and critical technology standards."),
    ("Telecommunications Adversary Equipment Ban", "To prohibit Federal subsidies for telecommunications equipment produced by Huawei or ZTE."),
    ("AUKUS Implementation Act", "To facilitate the transfer of submarine technology among Australia, the United Kingdom, and the United States under the AUKUS partnership."),
    ("Strategic Ports Security Act", "To require review of foreign operation of cranes and logistics software at United States ports by companies domiciled in adversary nations."),
]

clear_neg = [
    ("Veterans Mental Health Access Act", "To expand access to mental health services for veterans in rural areas through telehealth grants administered by the Department of Veterans Affairs."),
    ("Rural Broadband Expansion Act", "To provide grants for the deployment of high-speed broadband infrastructure in unserved rural communities."),
    ("Student Loan Interest Relief Act", "To reduce interest rates on Federal student loans and expand income-driven repayment options for borrowers."),
    ("National Parks Maintenance Act", "To address the deferred maintenance backlog of the National Park Service and establish a legacy restoration fund."),
    ("Opioid Treatment Access Act", "To expand access to medication-assisted treatment for opioid use disorder in underserved communities."),
    ("Small Business Tax Simplification Act", "To simplify quarterly tax filing requirements for small businesses with fewer than fifty employees."),
    ("Clean Drinking Water Infrastructure Act", "To provide funding for the replacement of lead service lines in public water systems."),
    ("School Lunch Nutrition Act", "To update nutrition standards for the national school lunch program and expand summer meal availability."),
    ("Wildfire Prevention and Forest Management Act", "To improve forest management practices and fund hazardous fuel reduction on Federal lands."),
    ("Social Security Fairness Act", "To repeal the windfall elimination provision and government pension offset under title II of the Social Security Act."),
    ("Affordable Housing Credit Improvement Act", "To expand the low-income housing tax credit and improve the allocation of credits to high-need areas."),
    ("Highway Safety Improvement Act", "To reauthorize Federal highway safety programs and fund improvements at high-crash rural intersections."),
    ("Childhood Cancer Research Act", "To expand pediatric cancer research programs at the National Institutes of Health."),
    ("Farm to Food Bank Act", "To provide tax incentives for farmers who donate surplus crops to regional food banks."),
    ("Postal Service Reform Act", "To reform the financing of retiree health benefits for employees of the United States Postal Service."),
    ("Great Lakes Restoration Act", "To reauthorize the Great Lakes Restoration Initiative and address invasive species in the Great Lakes basin."),
    ("Apprenticeship Expansion Act", "To expand registered apprenticeship programs in the skilled trades through grants to community colleges."),
    ("Disaster Relief Flexibility Act", "To provide State and local governments greater flexibility in the use of Federal disaster relief funds."),
    ("Election Infrastructure Modernization Act", "To provide grants to States for the replacement of aging voting equipment and post-election audits."),
    ("Honoring Our Firefighters Act", "To establish a national memorial and expand death benefits for firefighters who die in the line of duty."),
    ("Community Policing Grant Act", "To reauthorize the community oriented policing services grant program and fund officer wellness initiatives."),
    ("Flood Insurance Affordability Act", "To reform the national flood insurance program and provide means-tested premium assistance."),
    ("Teacher Loan Forgiveness Expansion Act", "To expand loan forgiveness for teachers serving in high-need public schools."),
    ("Organ Donation Modernization Act", "To modernize the organ procurement and transplantation network and improve donor registry interoperability."),
    ("Rural Hospital Stabilization Act", "To provide enhanced Medicare payments to critical access hospitals at risk of closure."),
    ("Youth Sports Safety Act", "To establish concussion management guidelines for youth athletic programs receiving Federal funds."),
    ("Historic Preservation Tax Credit Act", "To enhance the rehabilitation tax credit for certified historic structures."),
    ("Volunteer Emergency Responders Tax Relief Act", "To provide a tax credit for volunteer firefighters and emergency medical personnel."),
    ("Chesapeake Bay Cleanup Act", "To reauthorize the Chesapeake Bay program and fund agricultural runoff reduction practices."),
    ("Airport Infrastructure Modernization Act", "To fund terminal improvements and runway safety projects at small and medium hub airports."),
    ("Foster Care Stability Act", "To improve placement stability for children in foster care and support kinship caregivers."),
    ("Meat Processing Competition Act", "To expand competition in livestock markets and fund small regional meat processing facilities."),
    ("Digital Literacy for Seniors Act", "To provide grants to public libraries for digital literacy training programs for older adults."),
    ("Honey Bee Habitat Act", "To promote pollinator habitat on Federal highway rights-of-way and conservation reserve lands."),
    ("Court Interpreter Access Act", "To improve access to qualified interpreters in Federal court proceedings."),
]

# Hard negatives and genuinely ambiguous items. `label` given explicitly.
borderline = [
    ("United States-Japan Trade Agreement Act", "To implement the trade agreement between the United States and Japan regarding agricultural and digital trade.", 0),
    ("North American Steel Tariff Review Act", "To review the application of section 232 tariffs on steel and aluminum imports from Canada and Mexico.", 0),
    ("Export Control Modernization Act", "To modernize the export control system for emerging and foundational technologies with military applications.", 1),
    ("Supply Chain Resilience Act", "To establish a program to map critical supply chains and reduce single-source foreign dependencies in essential industries.", 1),
    ("Foreign Adversary Telecom Review Act", "To formalize the process for reviewing telecommunications licenses held by companies subject to foreign adversary jurisdiction.", 1),
    ("Critical Minerals Processing Act", "To incentivize domestic processing of critical minerals used in batteries and defense systems.", 1),
    ("Trans-Pacific Fisheries Enforcement Act", "To combat illegal, unreported, and unregulated fishing in the Pacific Ocean through expanded Coast Guard cooperation.", 1),
    ("Korean Peninsula Peace Act", "To encourage diplomatic engagement toward a formal end to the Korean War and denuclearization of the Korean Peninsula.", 0),
    ("European Union Data Privacy Compatibility Act", "To align cross-border data transfer rules with frameworks negotiated with the European Union.", 0),
    ("Buy American Manufacturing Act", "To strengthen domestic content requirements for Federal procurement of manufactured goods.", 0),
    ("Foreign Agricultural Land Disclosure Act", "To require disclosure of foreign ownership of United States agricultural land to the Department of Agriculture.", 1),
    ("Tableware Import Safety Act", "To establish lead and cadmium safety standards for imported ceramic and porcelain tableware.", 0),
    ("Outbound Investment Transparency Act", "To require notification of United States investments in sensitive technologies in countries of concern.", 1),
    ("Global Vaccine Distribution Act", "To support equitable international distribution of vaccines through multilateral institutions.", 0),
    ("International Students STEM Retention Act", "To provide a pathway for international students earning advanced STEM degrees to remain in the United States.", 0),
    ("Solar Component Tariff Adjustment Act", "To adjust tariff treatment of imported solar cells and modules to support domestic solar manufacturing.", 1),
    ("Pharmaceutical Ingredient Independence Act", "To reduce dependence on foreign sources of active pharmaceutical ingredients through domestic production incentives.", 1),
    ("Arctic Strategy Act", "To develop a comprehensive Arctic strategy addressing increased commercial and military activity by near-peer competitors.", 1),
    ("World Trade Organization Reform Act", "To direct the United States Trade Representative to pursue reform of dispute settlement at the World Trade Organization.", 0),
    ("Allied Shipbuilding Cooperation Act", "To permit maintenance of United States naval vessels at shipyards in allied Indo-Pacific nations.", 1),
]

rows = []
bill_no = 1001
for title, snippet in direct_pos:
    rows.append((f"H.R.{bill_no}", title, snippet, 1)); bill_no += random.randint(3, 40)
for title, snippet in indirect_pos:
    rows.append((f"S.{bill_no}", title, snippet, 1)); bill_no += random.randint(3, 40)
for title, snippet in clear_neg:
    rows.append((f"H.R.{bill_no}", title, snippet, 0)); bill_no += random.randint(3, 40)
for title, snippet, label in borderline:
    rows.append((f"S.{bill_no}", title, snippet, label)); bill_no += random.randint(3, 40)

random.shuffle(rows)
df = pd.DataFrame(rows, columns=["bill_id", "title", "snippet", "about_china"])
df.to_csv("/home/claude/twl/data/bills_china.csv", index=False)
print(len(df), "bills |", df.about_china.value_counts().to_dict())
