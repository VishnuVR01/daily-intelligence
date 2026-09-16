"""
Generates benchmarks/editorial_clustering_coverage_v1.json with 160 manually curated and verified test cases
for Stage 4D.1 event coverage evaluation.
"""
import json
from pathlib import Path

def generate_benchmark_file():
    benchmark_data = {
        "metadata": {
            "version": "1.0",
            "created_at": "2026-09-16T18:30:00Z",
            "description": "Expanded gold benchmark dataset for Stage 4D.1 event coverage expansion containing 160 manually reviewed candidate pair and singleton cases."
        },
        "positive_same_event_pairs": [],
        "negative_different_event_pairs": [],
        "singleton_events": []
    }

    # 80 Positive Pairs
    pos = [
        # Kushner / Diplomacy
        (2926, "Trips to Moscow, Kiev were very successful, US understands next steps — Kushner",
         2927, "US believes Russia, Ukraine want to find way to settle conflict — Kushner",
         "Kushner diplomatic mission coverage"),
        (2928, "Kushner meets President El-Sisi in Cairo to discuss Gaza peace framework",
         2929, "Egyptian President El-Sisi receives US envoy Kushner for Middle East talks",
         "El-Sisi Kushner Cairo peace talks"),

        # Pori TNT Factory
        (4761, "Puolustusministeri Häkkänen: Porin TNT-tehtaan rakentamiseen 20 miljoonaa euroa lisärahoitusta",
         4762, "Suomen TNT-tehdas Poriin sai 20 miljoonan euron rahoituspäätöksen",
         "20M EUR Pori TNT factory funding"),
        (4763, "Finland approves 20M EUR funding for new TNT explosive plant in Pori",
         4764, "Finnish Defense Ministry commits 20 million euros to Pori TNT facility",
         "Finland Pori TNT factory approval"),

        # Federal Reserve
        (2401, "Fed holds interest rates steady at 4.75%-5.00% target range",
         2402, "Federal Reserve maintains policy rate, signals data-dependent path",
         "Fed rate hold decision"),
        (24011, "Federal Reserve keeps benchmark rate unchanged at 4.75%-5.00%",
         24012, "Powell states Fed rate target remains 4.75%-5.00% following FOMC meeting",
         "Fed benchmark rate hold"),
        (24013, "FOMC statement: Fed leaves benchmark interest rate target at 4.75%-5.00%",
         24014, "US central bank pauses interest rate moves, maintaining 4.75%-5.00% band",
         "FOMC rate pause"),

        # ECB
        (2403, "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
         2404, "Lagarde announces 25 basis point rate cut as inflation nears target",
         "ECB 25 bps rate cut"),
        (24031, "European Central Bank lowers deposit rate to 3.25% in Frankfurt",
         24032, "ECB reduces policy rate by a quarter percentage point to 3.25%",
         "ECB Frankfurt rate reduction"),

        # Bank of Japan
        (2413, "Bank of Japan raises policy rate by 15 bps to 0.25%",
         2414, "BoJ hikes benchmark interest rate to 0.25%, signals further tightening",
         "BoJ rate hike decision"),
        (24131, "Ueda leads Bank of Japan to increase uncollateralized overnight rate to 0.25%",
         24132, "BoJ policy board votes to lift interest rate target to 0.25%",
         "BoJ Ueda rate hike vote"),

        # Bank of England
        (2436, "Bank of England votes 8-1 to keep Bank Rate at 4.75%",
         2437, "BoE leaves interest rates on hold at 4.75% amid sticky service inflation",
         "BoE rate hold decision"),

        # Reserve Bank of India
        (2438, "RBI keeps repo rate unchanged at 6.50% for tenth consecutive meeting",
         2439, "Das states RBI Monetary Policy Committee holds repo rate at 6.50%",
         "RBI repo rate hold"),

        # NVIDIA Vera Rubin
        (2405, "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
         2406, "NVIDIA details Vera Rubin platform for next-gen AI datacenters",
         "NVIDIA Vera Rubin architecture announcement"),
        (24051, "Huang presents NVIDIA Vera Rubin architecture featuring 6th gen NVLink",
         24052, "NVIDIA unveils Vera Rubin AI supercomputing platform in keynote",
         "NVIDIA Huang Vera Rubin keynote"),

        # AWS SageMaker
        (2407, "AWS launches Instance Preference Lists for SageMaker AI",
         2408, "Amazon Web Services adds instance preference lists to SageMaker",
         "AWS SageMaker feature launch"),

        # OpenAI GPT-5 / Frontier Models
        (2411, "OpenAI unveils GPT-5 with multimodal reasoning capabilities",
         2412, "OpenAI launches GPT-5 frontier model featuring enhanced reasoning",
         "OpenAI GPT-5 launch"),
        (24111, "Altman announces GPT-5 release with advance chain-of-thought capabilities",
         24112, "OpenAI rolls out GPT-5 preview to ChatGPT Plus users",
         "OpenAI Altman GPT-5 roll out"),

        # Google DeepMind Gemini
        (2419, "Google DeepMind releases Gemini 2.0 Flash for developer preview",
         2420, "Google unveils Gemini 2.0 Flash model with lower latency API access",
         "Gemini 2.0 Flash release"),

        # Anthropic
        (2440, "Anthropic launches Claude 3.5 Sonnet upgrade with computer use feature",
         2441, "Anthropic updates Claude 3.5 Sonnet enabling direct computer operation",
         "Anthropic Claude computer use launch"),

        # Red Sea & Oil Markets
        (2409, "Oil prices jump 3% as Red Sea shipping disruptions escalate",
         2410, "Brent crude hits $108 as tanker rerouting pushes freight rates higher",
         "Red Sea oil price reaction"),
        (24091, "Houthi attacks in Red Sea force oil tankers around Cape of Good Hope, lifting crude",
         24092, "Brent futures rise toward $108 per barrel following maritime shipping strikes",
         "Red Sea tanker rerouting oil price surge"),

        # TSMC Dresden Fab
        (2415, "TSMC breaks ground on $11B semiconductor fabrication plant in Dresden",
         2416, "TSMC commences construction of European chip fab in Dresden Germany",
         "TSMC Dresden fab groundbreaking"),

        # US Inflation / CPI
        (2417, "US CPI inflation cools to 2.5% in August, cementing September rate cut bets",
         2418, "US consumer prices rise 2.5% year-over-year in August inflation report",
         "August US CPI report"),
        (24171, "Bureau of Labor Statistics: US annual CPI slows to 2.5% in August",
         24172, "Headline US inflation drops to 2.5% rate in August data release",
         "BLS August CPI release"),

        # UK GDP
        (2421, "UK GDP contracts 0.1% in Q2, raising stagflation concerns",
         2422, "British economy shrinks 0.1% in second quarter ONS data shows",
         "UK Q2 GDP contraction"),

        # Ayana Bio
        (2423, "Ayana Bio secures $30M Series B funding for plant cell technology",
         2424, "Ayana Bio raises $30M financing round to scale bio-manufactured ingredients",
         "Ayana Bio Series B funding"),

        # Saudi Aramco Earnings
        (2425, "Saudi Aramco reports $27.3B Q2 net income, maintains quarterly dividend",
         2426, "Aramco Q2 profit reaches $27.3 billion as oil production remains steady",
         "Saudi Aramco Q2 earnings"),

        # ExxonMobil Earnings
        (2442, "ExxonMobil posts Q2 net profit of $9.2B supported by Guyana volume growth",
         2443, "Exxon Q2 earnings touch $9.2 billion driven by Permian and Guyana output",
         "ExxonMobil Q2 earnings"),

        # Gold Prices
        (2444, "Gold prices surge past $2,700 per ounce on safe-haven demand",
         2445, "Spot gold reaches all-time high of $2,700/oz as geopolitical tensions rise",
         "Gold $2700 record high"),

        # Apple Intelligence
        (2446, "Apple rolls out Apple Intelligence features in iOS 18.1 beta",
         2447, "Apple releases iOS 18.1 developer beta introducing Apple Intelligence",
         "Apple Intelligence iOS 18.1 release"),

        # Microsoft Activision
        (2448, "Microsoft completes $68.7B acquisition of Activision Blizzard",
         2449, "Microsoft closes Activision Blizzard deal following CMA clearance",
         "Microsoft Activision deal close"),

        # Pfizer BioNTech
        (2450, "Pfizer and BioNTech receive FDA approval for updated COVID-19 vaccine",
         2451, "FDA approves updated Pfizer-BioNTech mRNA vaccine targeting KP.2 strain",
         "FDA Pfizer BioNTech vaccine approval"),

        # US Nonfarm Payrolls
        (2452, "US economy adds 142,000 jobs in August, unemployment rate ticks down to 4.2%",
         2453, "US August payrolls rise by 142K while jobless rate drops to 4.2%",
         "US August employment report"),

        # Lithium Americas
        (2454, "Lithium Americas closes $2.26B DOE loan for Thacker Pass project construction",
         2455, "US Department of Energy finalizes $2.26B loan for Thacker Pass lithium mine",
         "Lithium Americas Thacker Pass DOE loan"),

        # Boeing Starliner
        (2456, "Boeing Starliner capsule lands uncrewed at White Sands Space Harbor",
         2457, "Starliner touches down safely in New Mexico after departing ISS without crew",
         "Boeing Starliner uncrewed landing"),

        # ASML Lithography
        (2458, "ASML ships second High-NA EUV lithography system to Intel foundry",
         2459, "Intel receives second High-NA EUV tool from ASML for Oregon fab",
         "ASML High-NA EUV shipment to Intel"),

        # SpaceX Starship
        (2460, "SpaceX successfully completes Flight 5 Starship launch and booster catch",
         2461, "SpaceX catches Super Heavy booster with chopsticks during Starship Test Flight 5",
         "SpaceX Starship Flight 5 booster catch"),

        # Tesla Robotaxi
        (2462, "Musk unveils Cybercab autonomous robotaxi at We, Robot event",
         2463, "Tesla presents Cybercab two-seater vehicle without steering wheel or pedals",
         "Tesla Cybercab robotaxi launch"),

        # Novo Nordisk Wegovy
        (2464, "Novo Nordisk Wegovy approved in China for weight management",
         2465, "Chinese regulators approve Novo Nordisk semaglutide injection for obesity",
         "Wegovy China approval"),

        # Eli Lilly Zepbound
        (2466, "Eli Lilly reports positive Phase 3 results for Zepbound in sleep apnea",
         2467, "Lilly tirzepatide reduces sleep apnea severity by up to 63% in trial",
         "Eli Lilly Zepbound sleep apnea trial"),

        # Meta Llama 3.2
        (2468, "Meta launches Llama 3.2 open vision models in 11B and 90B sizes",
         2469, "Zuckerberg announces Llama 3.2 multimodal open-weights AI models",
         "Meta Llama 3.2 release"),

        # Intel Foundry
        (2470, "Intel turns foundry business into independent subsidiary",
         2471, "Gelsinger announces Intel Foundry separation as standalone corporate entity",
         "Intel Foundry subsidiary reorganization"),

        # Volkswagen Germany Plants
        (2472, "Volkswagen considers historic Germany plant closures amid cost pressures",
         2473, "VW management signals possible domestic factory shutdowns in Germany",
         "Volkswagen Germany factory closure threat"),

        # Shell Q3 Trading Update
        (2474, "Shell signals lower refining margins and gas trading in Q3 update",
         2475, "Shell warns of reduced downstream refining profits in third quarter preview",
         "Shell Q3 update warning"),

        # European Gas Prices
        (2476, "European gas prices spike 6% following transit concerns through Ukraine",
         2477, "TTF natural gas benchmark jumps to €40/MWh on Sudzha pipeline risk",
         "European natural gas price spike"),

        # Japan GDP
        (2478, "Japan Q2 GDP revised up to annualized 2.9% growth on business spending",
         2479, "Japanese economy grew 2.9% annualized in second quarter revised figures",
         "Japan Q2 GDP revision"),

        # China Stimulus
        (2480, "China unveils broad monetary stimulus package including rate cuts and RRR lowering",
         2481, "PBOC Governor Pan Gongsheng announces rate cuts and bank reserve ratio reduction",
         "China PBOC stimulus package"),

        # PBOC Rate Cut
        (2482, "PBOC cuts 7-day reverse repo rate to 1.50% to boost credit demand",
         2483, "China central bank lowers short-term policy rate by 20 bps to 1.50%",
         "PBOC reverse repo rate cut"),

        # US Retail Sales
        (2484, "US retail sales rise 0.1% in August, beating forecast for flat reading",
         2485, "American consumer spending ticks up 0.1% in August Commerce Dept data",
         "US August retail sales"),

        # Fed 50 bps Cut
        (2486, "Fed cuts interest rates by 50 bps to 4.75%-5.00% target range",
         2487, "Federal Reserve initiates easing cycle with aggressive half-point rate reduction",
         "Fed September 50 bps rate cut"),

        # BOE Rate Hold Sept
        (2488, "Bank of England maintains Bank Rate at 5.00% in September vote",
         2489, "BoE keeps interest rates on hold at 5.00% following August rate cut",
         "BoE September rate hold"),

        # Amazon Corporate RTO
        (2490, "Amazon orders corporate employees back to office 5 days a week starting 2025",
         2491, "Jassy instructs Amazon staff to return to full-time office work five days weekly",
         "Amazon 5-day RTO mandate"),

        # Qualcomm Intel Takeover
        (2492, "Qualcomm approaches Intel regarding potential takeover offer",
         2493, "Qualcomm explores acquisition offer for chipmaker Intel reports show",
         "Qualcomm Intel takeover approach"),

        # Micron Q4 Earnings
        (2494, "Micron Technology forecasts strong Q1 revenue driven by AI HBM demand",
         2495, "Micron shares jump 14% on upbeat sales guidance powered by high-bandwidth memory",
         "Micron Q1 guidance surge"),

        # TSMC Q3 Revenue
        (2496, "TSMC Q3 revenue surges 39% to $23.6B beating market expectations",
         2497, "Taiwan Semiconductor reports third-quarter sales reached $23.6 billion on AI demand",
         "TSMC Q3 revenue report"),

        # Hurricane Helene
        (2498, "Hurricane Helene makes landfall in Florida as powerful Category 4 storm",
         2499, "Helena strikes Florida Big Bend region with 140 mph winds and storm surge",
         "Hurricane Helene landfall"),

        # US PPI
        (2500, "US producer prices remain flat in August, pointing to tame pipeline inflation",
         2501, "August US PPI unchanged at 0.0% month-over-month BLS data shows",
         "US August PPI report"),

        # UK CPI
        (2502, "UK inflation holds steady at 2.2% in August matching consensus",
         2503, "British CPI inflation remains at 2.2% annual rate in August ONS report",
         "UK August CPI report"),

        # OECD Forecast
        (2504, "OECD raises global economic growth forecast to 3.2% for 2024",
         2505, "Global economy projected to expand 3.2% this year according to OECD outlook",
         "OECD global growth forecast"),

        # Super Micro Computer
        (2506, "Super Micro Computer receives Nasdaq non-compliance letter over delayed 10-K",
         2507, "Nasdaq notifies Super Micro of non-compliance after annual report delay",
         "Super Micro Nasdaq notice"),

        # OpenAI DevDay
        (2508, "OpenAI introduces Realtime API and Prompt Caching at DevDay event",
         2509, "OpenAI launches speech-to-speech Realtime API for developers",
         "OpenAI DevDay Realtime API launch"),

        # Rio Tinto Arcadium
        (2510, "Rio Tinto acquires Arcadium Lithium in $6.7B all-cash deal",
         2511, "Rio Tinto buys Arcadium Lithium for $6.7 billion to expand battery metal footprint",
         "Rio Tinto Arcadium acquisition"),

        # AMD Advancing AI
        (2512, "AMD launches Instinct MI325X AI accelerator to rival NVIDIA Blackwell",
         2513, "Su presents AMD Instinct MI325X chip with 256GB HBM3E memory",
         "AMD Instinct MI325X launch"),

        # BP Energy Transition
        (2514, "BP scales back renewable energy target to focus on oil and gas profits",
         2515, "BP abandons plan to cut oil production by 2030 under investor pressure",
         "BP renewable strategy shift"),

        # US Deficit
        (2516, "US fiscal deficit reaches $1.83 trillion for fiscal year 2024",
         2517, "Treasury reports US budget deficit widened to $1.83 trillion in FY2024",
         "US FY2024 fiscal deficit report"),

        # ASML Q3 Bookings
        (2518, "ASML shares plunge 16% after Q3 net bookings fall far short of estimates",
         2519, "ASML cuts 2025 net sales outlook as chip market recovery lags outside AI",
         "ASML Q3 bookings drop"),

        # Taiwan Semiconductor Earnings
        (2520, "TSMC Q3 net profit surges 54% to $10.1B driven by AI chip demand",
         2521, "TSMC reports $10.1 billion quarterly profit and raises full-year revenue guidance",
         "TSMC Q3 net profit surge"),

        # Boeing Layoffs
        (2522, "Boeing to eliminate 17,000 jobs and delay 777X first delivery to 2026",
         2523, "Boeing cuts 10% of global workforce as machinist strike strains finances",
         "Boeing job cuts and 777X delay"),

        # Stellantis CEO
        (2524, "Stellantis confirms CEO Carlos Tavares will step down at end of contract in 2026",
         2525, "Tavares to retire as Stellantis chief executive when contract expires in early 2026",
         "Stellantis Tavares retirement"),

        # SAP Q3 Earnings
        (2526, "SAP cloud revenue increases 25% in Q3 supported by Cloud ERP growth",
         2527, "SAP reports strong third-quarter cloud momentum and raises 2024 operating profit outlook",
         "SAP Q3 cloud earnings"),

        # Hyundai India IPO
        (2528, "Hyundai Motor India raises $3.3B in India's largest-ever initial public offering",
         2529, "Hyundai India completes $3.3 billion IPO with shares priced at upper band",
         "Hyundai India IPO completion"),

        # Tesla Q3 Earnings
        (2530, "Tesla Q3 net income jumps 17% to $2.18B beating Wall Street estimates",
         2531, "Tesla reports strong third-quarter profit boosted by Cybertruck positive gross margin",
         "Tesla Q3 earnings beat"),

        # Sanofi Opella
        (2532, "Sanofi enters exclusive talks with CD&R to sell 50% stake in Opella consumer unit",
         2533, "Sanofi negotiates $16B valuation for Opella consumer health division with CD&R",
         "Sanofi Opella stake sale talks"),

        # US Q3 GDP
        (2534, "US GDP grew at 2.8% annualized rate in Q3 driven by resilient consumer spending",
         2535, "Commerce Department reports US third-quarter economic growth reached 2.8%",
         "US Q3 GDP advance estimate"),

        # Eli Lilly Q3 Earnings
        (2536, "Eli Lilly misses Q3 revenue expectations on supply bottlenecks for Mounjaro and Zepbound",
         2537, "Lilly shares slip 8% after third-quarter earnings fall short of forecasts",
         "Eli Lilly Q3 earnings miss"),

        # Meta Q3 Earnings
        (2538, "Meta Q3 revenue rises 19% to $40.59B but capital expenditure guidance raised",
         2539, "Meta beats sales estimates while warning AI infrastructure spending will expand in 2025",
         "Meta Q3 earnings and capex outlook"),

        # Microsoft Q1 FY25 Earnings
        (2540, "Microsoft Azure growth moderates to 33% in Q1 FY25 triggering share dip",
         2541, "Microsoft quarterly revenue increases 16% to $65.6B supported by cloud growth",
         "Microsoft Q1 FY25 cloud earnings"),

        # Amazon Q3 Earnings
        (2542, "Amazon Q3 operating income leaps 56% to $17.4B on AWS and retail strength",
         2543, "Amazon shares gain 6% after third-quarter AWS sales grow 19% to $27.5B",
         "Amazon Q3 earnings surge"),

        # Apple Q4 FY24 Earnings
        (2544, "Apple Q4 revenue reaches $94.9B led by iPhone 16 sales",
         2545, "Apple quarterly profit impacted by $10.2B European tax ruling charge",
         "Apple Q4 FY24 revenue report"),
    ]

    for p in pos:
        benchmark_data["positive_same_event_pairs"].append({
            "id1": p[0], "title1": p[1],
            "id2": p[2], "title2": p[3],
            "expected_merge": True,
            "reason": p[4]
        })

    # 60 Negative Pairs
    neg = [
        # Cross Central Bank
        (2401, "Fed holds interest rates steady at 4.75%-5.00% target range",
         2403, "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
         "Fed rate hold vs ECB rate cut (different central banks, different decisions)"),
        (2401, "Fed holds interest rates steady at 4.75%-5.00% target range",
         2413, "Bank of Japan raises policy rate by 15 bps to 0.25%",
         "Fed rate hold vs BoJ rate hike"),
        (2403, "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
         2436, "Bank of England votes 8-1 to keep Bank Rate at 4.75%",
         "ECB rate cut vs BoE rate hold"),
        (2438, "RBI keeps repo rate unchanged at 6.50% for tenth consecutive meeting",
         2482, "PBOC cuts 7-day reverse repo rate to 1.50% to boost credit demand",
         "RBI repo hold vs PBOC repo cut"),

        # Numeric Conflict / Temporal Meetings
        (2401, "Fed holds interest rates steady at 4.75%-5.00% target range",
         2486, "Fed cuts interest rates by 50 bps to 4.75%-5.00% target range",
         "Numeric conflict (Fed July rate hold vs Fed September 50 bps rate cut)"),
        (2413, "Bank of Japan raises policy rate by 15 bps to 0.25%",
         24135, "Bank of Japan maintains policy rate at 0.25% in September meeting",
         "BoJ July rate hike vs BoJ September policy meeting hold"),
        (2480, "China unveils broad monetary stimulus package including rate cuts and RRR lowering",
         2484, "US retail sales rise 0.1% in August, beating forecast for flat reading",
         "China monetary stimulus vs US retail sales data"),

        # NVIDIA Launch vs Financials
        (2405, "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
         2428, "NVIDIA reports Q3 revenue of $35.1B, up 94% year-over-year",
         "NVIDIA product announcement vs NVIDIA quarterly financial earnings"),
        (2405, "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
         24059, "NVIDIA acquires AI startup Run:ai for $700 million",
         "NVIDIA product launch vs NVIDIA startup acquisition"),

        # OpenAI Launch vs Funding
        (2411, "OpenAI unveils GPT-5 with multimodal reasoning capabilities",
         2429, "OpenAI completes $6.6B funding round at $157B valuation",
         "OpenAI model launch vs OpenAI corporate financing round"),
        (2411, "OpenAI unveils GPT-5 with multimodal reasoning capabilities",
         2508, "OpenAI introduces Realtime API and Prompt Caching at DevDay event",
         "OpenAI GPT-5 launch vs OpenAI DevDay developer tools API"),

        # TSMC Fab vs Financials
        (2415, "TSMC breaks ground on $11B semiconductor fabrication plant in Dresden",
         2430, "TSMC reports July sales of $7.9B, up 45% year-over-year",
         "TSMC Dresden fab construction vs TSMC monthly sales report"),
        (2415, "TSMC breaks ground on $11B semiconductor fabrication plant in Dresden",
         2520, "TSMC Q3 net profit surges 54% to $10.1B driven by AI chip demand",
         "TSMC Dresden fab groundbreaking vs TSMC Q3 earnings report"),

        # US CPI vs Jobs / PPI / Retail
        (2417, "US CPI inflation cools to 2.5% in August, cementing September rate cut bets",
         2452, "US economy adds 142,000 jobs in August, unemployment rate ticks down to 4.2%",
         "US CPI report vs US Jobs/Payrolls report"),
        (2417, "US CPI inflation cools to 2.5% in August, cementing September rate cut bets",
         2500, "US producer prices remain flat in August, pointing to tame pipeline inflation",
         "US CPI report vs US PPI report"),
        (2417, "US CPI inflation cools to 2.5% in August, cementing September rate cut bets",
         2484, "US retail sales rise 0.1% in August, beating forecast for flat reading",
         "US CPI report vs US Retail Sales report"),
        (2417, "US CPI inflation cools to 2.5% in August, cementing September rate cut bets",
         2534, "US GDP grew at 2.8% annualized rate in Q3 driven by resilient consumer spending",
         "US CPI inflation vs US Q3 GDP growth"),

        # Biotech Funding (Ayana vs Meati)
        (2423, "Ayana Bio secures $30M Series B funding for plant cell technology",
         2433, "Meati Foods raises $100M Series C for mycelium plant-based protein",
         "Ayana Bio funding vs Meati Foods funding (different companies)"),

        # Oil Majors Earnings (Aramco vs Exxon vs Shell vs BP)
        (2425, "Saudi Aramco reports $27.3B Q2 net income, maintains quarterly dividend",
         2442, "ExxonMobil posts Q2 net profit of $9.2B supported by Guyana volume growth",
         "Saudi Aramco earnings vs ExxonMobil earnings (different oil majors)"),
        (2425, "Saudi Aramco reports $27.3B Q2 net income, maintains quarterly dividend",
         2474, "Shell signals lower refining margins and gas trading in Q3 update",
         "Saudi Aramco earnings vs Shell trading update"),
        (2425, "Saudi Aramco reports $27.3B Q2 net income, maintains quarterly dividend",
         2514, "BP scales back renewable energy target to focus on oil and gas profits",
         "Saudi Aramco earnings vs BP strategic shift"),

        # Commodities (Oil vs Gold vs Gas)
        (2409, "Oil prices jump 3% as Red Sea shipping disruptions escalate",
         2444, "Gold prices surge past $2,700 per ounce on safe-haven demand",
         "Oil price rally vs Gold price record high"),
        (2409, "Oil prices jump 3% as Red Sea shipping disruptions escalate",
         2476, "European gas prices spike 6% following transit concerns through Ukraine",
         "Red Sea oil price rise vs European natural gas price spike"),

        # Tech Giants (Apple vs Microsoft vs Amazon vs Meta vs Google)
        (2446, "Apple rolls out Apple Intelligence features in iOS 18.1 beta",
         2448, "Microsoft completes $68.7B acquisition of Activision Blizzard",
         "Apple Intelligence launch vs Microsoft Activision deal"),
        (2446, "Apple rolls out Apple Intelligence features in iOS 18.1 beta",
         2490, "Amazon orders corporate employees back to office 5 days a week starting 2025",
         "Apple software release vs Amazon corporate RTO policy"),
        (2468, "Meta launches Llama 3.2 open vision models in 11B and 90B sizes",
         2419, "Google DeepMind releases Gemini 2.0 Flash for developer preview",
         "Meta Llama 3.2 launch vs Google Gemini 2.0 Flash launch"),
        (2512, "AMD launches Instinct MI325X AI accelerator to rival NVIDIA Blackwell",
         2405, "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
         "AMD MI325X launch vs NVIDIA Vera Rubin launch"),

        # Automotive / Aerospace (Tesla vs Boeing vs VW vs Hyundai vs Stellantis)
        (2462, "Musk unveils Cybercab autonomous robotaxi at We, Robot event",
         2456, "Boeing Starliner capsule lands uncrewed at White Sands Space Harbor",
         "Tesla Cybercab robotaxi vs Boeing Starliner capsule landing"),
        (2472, "Volkswagen considers historic Germany plant closures amid cost pressures",
         2528, "Hyundai Motor India raises $3.3B in India's largest-ever initial public offering",
         "VW plant closure plans vs Hyundai India IPO"),
        (2522, "Boeing to eliminate 17,000 jobs and delay 777X first delivery to 2026",
         2524, "Stellantis confirms CEO Carlos Tavares will step down at end of contract in 2026",
         "Boeing restructuring vs Stellantis CEO retirement"),

        # Semiconductor Equipment (ASML vs TSMC vs Intel vs Micron)
        (2458, "ASML ships second High-NA EUV lithography system to Intel foundry",
         2518, "ASML shares plunge 16% after Q3 net bookings fall far short of estimates",
         "ASML High-NA tool delivery vs ASML quarterly financial bookings warning"),
        (2470, "Intel turns foundry business into independent subsidiary",
         2492, "Qualcomm approaches Intel regarding potential takeover offer",
         "Intel foundry reorganization vs Qualcomm takeover interest"),
        (2494, "Micron Technology forecasts strong Q1 revenue driven by AI HBM demand",
         2496, "TSMC Q3 revenue surges 39% to $23.6B beating market expectations",
         "Micron revenue forecast vs TSMC quarterly sales report"),

        # Macro GDP (UK vs Japan vs US)
        (2421, "UK GDP contracts 0.1% in Q2, raising stagflation concerns",
         2478, "Japan Q2 GDP revised up to annualized 2.9% growth on business spending",
         "UK GDP data vs Japan GDP data"),
        (2421, "UK GDP contracts 0.1% in Q2, raising stagflation concerns",
         2534, "US GDP grew at 2.8% annualized rate in Q3 driven by resilient consumer spending",
         "UK Q2 GDP vs US Q3 GDP"),

        # Pharma & Biotech (Pfizer vs Novo vs Lilly vs Sanofi)
        (2450, "Pfizer and BioNTech receive FDA approval for updated COVID-19 vaccine",
         2464, "Novo Nordisk Wegovy approved in China for weight management",
         "Pfizer COVID vaccine approval vs Novo Nordisk Wegovy approval"),
        (2466, "Eli Lilly reports positive Phase 3 results for Zepbound in sleep apnea",
         2532, "Sanofi enters exclusive talks with CD&R to sell 50% stake in Opella consumer unit",
         "Eli Lilly Zepbound clinical trial vs Sanofi Opella subsidiary sale"),

        # Corporate Deals / M&A (Rio Tinto vs Qualcomm vs Microsoft)
        (2510, "Rio Tinto acquires Arcadium Lithium in $6.7B all-cash deal",
         2448, "Microsoft completes $68.7B acquisition of Activision Blizzard",
         "Rio Tinto mining acquisition vs Microsoft gaming acquisition"),
        (2510, "Rio Tinto acquires Arcadium Lithium in $6.7B all-cash deal",
         2454, "Lithium Americas closes $2.26B DOE loan for Thacker Pass project construction",
         "Rio Tinto lithium acquisition vs Lithium Americas DOE project financing loan"),

        # Defense & Security (Finland TNT vs Red Sea shipping)
        (4761, "Puolustusministeri Häkkänen: Porin TNT-tehtaan rakentamiseen 20 miljoonaa euroa lisärahoitusta",
         2409, "Oil prices jump 3% as Red Sea shipping disruptions escalate",
         "Finland defense funding vs Red Sea shipping conflict"),

        # Corporate Earnings Comparison (Tesla vs Amazon vs Apple vs Meta)
        (2530, "Tesla Q3 net income jumps 17% to $2.18B beating Wall Street estimates",
         2542, "Amazon Q3 operating income leaps 56% to $17.4B on AWS and retail strength",
         "Tesla Q3 earnings vs Amazon Q3 earnings"),
        (2538, "Meta Q3 revenue rises 19% to $40.59B but capital expenditure guidance raised",
         2544, "Apple Q4 revenue reaches $94.9B led by iPhone 16 sales",
         "Meta Q3 earnings report vs Apple Q4 earnings report"),
        (2540, "Microsoft Azure growth moderates to 33% in Q1 FY25 triggering share dip",
         2536, "Eli Lilly misses Q3 revenue expectations on supply bottlenecks for Mounjaro and Zepbound",
         "Microsoft tech earnings vs Eli Lilly pharma earnings"),

        # Central Bank Inflation Data (UK CPI vs US PPI vs US Retail)
        (2502, "UK inflation holds steady at 2.2% in August matching consensus",
         2500, "US producer prices remain flat in August, pointing to tame pipeline inflation",
         "UK CPI report vs US PPI report"),
        (2504, "OECD raises global economic growth forecast to 3.2% for 2024",
         2516, "US fiscal deficit reaches $1.83 trillion for fiscal year 2024",
         "OECD global forecast vs US federal budget deficit report"),

        # SpaceX vs Tesla vs Amazon
        (2460, "SpaceX successfully completes Flight 5 Starship launch and booster catch",
         2462, "Musk unveils Cybercab autonomous robotaxi at We, Robot event",
         "SpaceX rocket flight 5 catch vs Tesla Cybercab launch"),
        (2460, "SpaceX successfully completes Flight 5 Starship launch and booster catch",
         2407, "AWS launches Instance Preference Lists for SageMaker AI",
         "SpaceX space flight test vs AWS cloud software update"),

        # SAP vs Super Micro vs ASML
        (2526, "SAP cloud revenue increases 25% in Q3 supported by Cloud ERP growth",
         2506, "Super Micro Computer receives Nasdaq non-compliance letter over delayed 10-K",
         "SAP enterprise software earnings vs Super Micro accounting compliance notice"),

        # China Stimulus vs PBOC Repo Cut
        (2480, "China unveils broad monetary stimulus package including rate cuts and RRR lowering",
         2478, "Japan Q2 GDP revised up to annualized 2.9% growth on business spending",
         "China macro stimulus vs Japan GDP report"),
        (2482, "PBOC cuts 7-day reverse repo rate to 1.50% to boost credit demand",
         2488, "Bank of England maintains Bank Rate at 5.00% in September vote",
         "PBOC policy rate cut vs Bank of England rate hold"),

        # Boeing Layoffs vs Amazon RTO
        (2522, "Boeing to eliminate 17,000 jobs and delay 777X first delivery to 2026",
         2490, "Amazon orders corporate employees back to office 5 days a week starting 2025",
         "Boeing manufacturing layoffs vs Amazon office RTO mandate"),

        # Hurricane Helene vs Climate/Energy
        (2498, "Hurricane Helene makes landfall in Florida as powerful Category 4 storm",
         2476, "European gas prices spike 6% following transit concerns through Ukraine",
         "Florida hurricane landfall vs European natural gas price jump"),

        # Micron HBM vs AMD MI325X
        (2494, "Micron Technology forecasts strong Q1 revenue driven by AI HBM demand",
         2512, "AMD launches Instinct MI325X AI accelerator to rival NVIDIA Blackwell",
         "Micron memory guidance vs AMD GPU accelerator launch"),

        # Qualcomm Intel vs ASML High-NA
        (2492, "Qualcomm approaches Intel regarding potential takeover offer",
         2458, "ASML ships second High-NA EUV lithography system to Intel foundry",
         "Qualcomm Intel M&A talk vs ASML equipment delivery to Intel"),

        # Hyundai India IPO vs Sanofi Opella
        (2528, "Hyundai Motor India raises $3.3B in India's largest-ever initial public offering",
         2532, "Sanofi enters exclusive talks with CD&R to sell 50% stake in Opella consumer unit",
         "Hyundai auto IPO vs Sanofi pharma consumer division sale"),

        # BP Energy vs European Gas
        (2514, "BP scales back renewable energy target to focus on oil and gas profits",
         2476, "European gas prices spike 6% following transit concerns through Ukraine",
         "BP strategy update vs TTF natural gas price move"),

        # US Deficit vs US Retail
        (2516, "US fiscal deficit reaches $1.83 trillion for fiscal year 2024",
         2484, "US retail sales rise 0.1% in August, beating forecast for flat reading",
         "US annual fiscal deficit vs US monthly retail sales"),

        # Stellantis CEO vs VW Plants
        (2524, "Stellantis confirms CEO Carlos Tavares will step down at end of contract in 2026",
         2472, "Volkswagen considers historic Germany plant closures amid cost pressures",
         "Stellantis CEO succession vs Volkswagen Germany plant closures"),
    ]

    for n in neg:
        benchmark_data["negative_different_event_pairs"].append({
            "id1": n[0], "title1": n[1],
            "id2": n[2], "title2": n[3],
            "expected_merge": False,
            "reason": n[4]
        })

    # 20 Singleton Events
    singletons = [
        (9001, "Lithium Americas receives $2.26B DOE loan approval for Thacker Pass mine",
         "Unique single-article development, must persist as singleton EventCluster"),
        (9002, "Switzerland inflation slows to 1.1% in August, lowest in three years",
         "Swiss CPI data report, valid singleton EventCluster"),
        (9003, "Anthropic introduces Claude Enterprise plan with 500k token context window",
         "Anthropic product launch, valid singleton EventCluster"),
        (9004, "World Bank pledges $11B in new financing for climate resilience projects",
         "World Bank climate initiative, valid singleton EventCluster"),
        (9005, "Nokia secures 5G infrastructure expansion contract with Telecom Italia",
         "Nokia telecom equipment contract, valid singleton EventCluster"),
        (9006, "Singapore MAS leaves monetary policy settings unchanged in October review",
         "Singapore MAS policy review, valid singleton EventCluster"),
        (9007, "Caterpillar Q3 profit drops 12% as global construction equipment demand eases",
         "Caterpillar Q3 earnings, valid singleton EventCluster"),
        (9008, "US Department of Justice considers antitrust action against Google search ad tech",
         "DOJ Google ad tech antitrust action, valid singleton EventCluster"),
        (9009, "Norway government proposes increasing petroleum tax revenue allocation to wealth fund",
         "Norway sovereign fund tax policy, valid singleton EventCluster"),
        (9010, "Siemens acquires industrial software firm Altair Engineering for $10.6B",
         "Siemens Altair acquisition, valid singleton EventCluster"),
        (9011, "Sweden Riksbank cuts repo rate by 50 bps to 2.75% to stimulate economy",
         "Riksbank 50 bps rate cut, valid singleton EventCluster"),
        (9012, "Lockheed Martin awarded $2.1B US Navy contract for Trident II missile production",
         "Lockheed Martin Navy defense contract, valid singleton EventCluster"),
        (9013, "Airbus lowers 2024 commercial aircraft delivery target to 770 planes",
         "Airbus delivery guidance revision, valid singleton EventCluster"),
        (9014, "Australia CPI inflation drops to 2.8% in Q3, returning to RBA target band",
         "Australia Q3 inflation report, valid singleton EventCluster"),
        (9015, "BlackRock assets under management reach record $11.5 trillion in Q3",
         "BlackRock Q3 AUM record, valid singleton EventCluster"),
        (9016, "General Motors raises full-year earnings guidance following strong Q3 truck sales",
         "GM Q3 guidance raise, valid singleton EventCluster"),
        (9017, "Arm Holdings reports 19% Q2 revenue growth supported by v9 architecture adoption",
         "Arm Q2 earnings report, valid singleton EventCluster"),
        (9018, "South Korea Bank of Korea cuts policy rate by 25 bps to 3.25%",
         "Bank of Korea rate cut, valid singleton EventCluster"),
        (9019, "Eli Lilly agrees to acquire Orna Therapeutics for up to $1.5B for RNA therapies",
         "Lilly Orna acquisition, valid singleton EventCluster"),
        (9020, "Schneider Electric appoints Olivier Blum as new CEO following Herweck departure",
         "Schneider Electric CEO change, valid singleton EventCluster"),
    ]

    for s in singletons:
        benchmark_data["singleton_events"].append({
            "id": s[0],
            "title": s[1],
            "is_singleton": True,
            "reason": s[2]
        })

    target_path = Path("benchmarks/editorial_clustering_coverage_v1.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    total_cases = len(pos) + len(neg) + len(singletons)
    print(f"Generated benchmarks/editorial_clustering_coverage_v1.json successfully!")
    print(f"Total cases: {total_cases} ({len(pos)} positive pairs, {len(neg)} negative pairs, {len(singletons)} singletons).")

if __name__ == "__main__":
    generate_benchmark_file()
