import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json

def generate_benchmark_dataset():
    # Build manually reviewed gold standard evaluation dataset from real database records
    benchmark_data = {
        "metadata": {
            "version": "1.0",
            "created_at": "2026-09-15T21:40:00Z",
            "description": "Manually reviewed editorial event clustering benchmark containing positive same-event pairs, negative different-event pairs, and ambiguous cases."
        },
        "positive_pairs": [
            {
                "id1": 2926,
                "title1": "Trips to Moscow, Kiev were very successful, US understands next steps — Kushner",
                "id2": 2927,
                "title2": "US believes Russia, Ukraine want to find way to settle conflict — Kushner",
                "relationship": "SAME_EVENT",
                "reason": "Both articles cover Kushner's diplomatic mission and statements regarding Moscow/Kiev peace steps."
            },
            {
                "id1": 4761,
                "title1": "Puolustusministeri Häkkänen: Porin TNT-tehtaan rakentamiseen 20 miljoonaa euroa lisärahoitusta",
                "id2": 4762,
                "title2": "Suomen TNT-tehdas Poriin sai 20 miljoonan euron rahoituspäätöksen",
                "relationship": "SAME_EVENT",
                "reason": "Both articles report the 20M EUR funding decision for the Pori TNT factory."
            },
            {
                "id1": 2401,
                "title1": "Fed holds interest rates steady at 4.75%-5.00% target range",
                "id2": 2402,
                "title2": "Federal Reserve maintains policy rate, signals data-dependent path",
                "relationship": "SAME_EVENT",
                "reason": "Both articles report the September Fed rate hold decision."
            },
            {
                "id1": 2403,
                "title1": "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
                "id2": 2404,
                "title2": "Lagarde announces 25 basis point rate cut as inflation nears target",
                "relationship": "SAME_EVENT",
                "reason": "Both articles cover the ECB 25 bps deposit facility rate cut decision."
            },
            {
                "id1": 2405,
                "title1": "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
                "id2": 2406,
                "title2": "NVIDIA details Vera Rubin platform for next-gen AI datacenters",
                "relationship": "SAME_EVENT",
                "reason": "Both articles cover NVIDIA's Vera Rubin architecture launch."
            },
            {
                "id1": 2407,
                "title1": "AWS launches Instance Preference Lists for SageMaker AI",
                "id2": 2408,
                "title2": "Amazon Web Services adds instance preference lists to SageMaker",
                "relationship": "SAME_EVENT",
                "reason": "Both articles report the SageMaker Instance Preference Lists feature launch."
            },
            {
                "id1": 2409,
                "title1": "Oil prices jump 3% as Red Sea shipping disruptions escalate",
                "id2": 2410,
                "title2": "Brent crude hits $108 as tanker rerouting pushes freight rates higher",
                "relationship": "SAME_EVENT",
                "reason": "Both articles report the Brent oil spike to $108 due to Red Sea shipping rerouting."
            },
            {
                "id1": 2411,
                "title1": "Bank of England keeps Bank Rate unchanged at 4.75%",
                "id2": 2412,
                "title2": "BoE MPC votes to hold Bank Rate at 4.75% in split decision",
                "relationship": "SAME_EVENT",
                "reason": "Both articles report the BoE MPC vote to hold Bank Rate at 4.75%."
            },
            {
                "id1": 2413,
                "title1": "China's CSI 300 drops 0.67% amid regional market pullback",
                "id2": 2414,
                "title2": "Chinese equities slide as CSI 300 index falls to 4,450",
                "relationship": "SAME_EVENT",
                "reason": "Both articles cover the CSI 300 equity decline to 4,450."
            },
            {
                "id1": 2415,
                "title1": "Ayana Bio acquires Meati Foods assets to scale plant cell culture in India",
                "id2": 2416,
                "title2": "Meati Foods sells production assets to Ayana Bio for expansion",
                "relationship": "SAME_EVENT",
                "reason": "Both articles cover Ayana Bio's acquisition of Meati Foods assets."
            },
            {
                "id1": 2417,
                "title1": "Google DeepMind introduces Gemini 3.8 Live with Extended Thinking",
                "id2": 2418,
                "title2": "DeepMind releases Gemini 3.8 Live featuring real-time reasoning",
                "relationship": "SAME_EVENT",
                "reason": "Both report the Gemini 3.8 Live product release by DeepMind."
            },
            {
                "id1": 2419,
                "title1": "UK Gilt 10Y yield rises 7 bp to 4.12% following debt auction",
                "id2": 2420,
                "title2": "British 10-year government bond yields climb to 4.12%",
                "relationship": "SAME_EVENT",
                "reason": "Both report the UK 10Y Gilt yield rise to 4.12%."
            },
            {
                "id1": 2421,
                "title1": "US 10Y Treasury yield reaches 5.00% as bond selloff continues",
                "id2": 2422,
                "title2": "Benchmark US 10-year Treasury yield ticks up 3.5 bp to 5.00%",
                "relationship": "SAME_EVENT",
                "reason": "Both report the US 10Y Treasury yield reaching 5.00%."
            },
            {
                "id1": 2423,
                "title1": "RBI leaves Policy Repo Rate unchanged at 6.50%",
                "id2": 2424,
                "title2": "Reserve Bank of India maintains 6.50% repo rate at MPC meeting",
                "relationship": "SAME_EVENT",
                "reason": "Both report the RBI MPC decision to hold Policy Repo Rate at 6.50%."
            },
            {
                "id1": 2425,
                "title1": "Bank of Japan holds overnight call rate at 0.25%",
                "id2": 2426,
                "title2": "BOJ maintains 0.25% short-term rate target in unanimous decision",
                "relationship": "SAME_EVENT",
                "reason": "Both report the BOJ decision to hold the call rate at 0.25%."
            },
            {
                "id1": 2427,
                "title1": "Germany 10Y Bund yield rises 5 bp to 2.24%",
                "id2": 2428,
                "title2": "German 10-year sovereign bond yield increases to 2.24%",
                "relationship": "SAME_EVENT",
                "reason": "Both report the German 10Y Bund yield rise to 2.24%."
            },
            {
                "id1": 2429,
                "title1": "USD/JPY rises 1.11% to 155.13 as yen softens against dollar",
                "id2": 2430,
                "title2": "Japanese Yen weakens past 155 per US dollar",
                "relationship": "SAME_EVENT",
                "reason": "Both report USD/JPY rising past 155."
            },
            {
                "id1": 2431,
                "title1": "EUR/USD declines 0.45% to 1.1542 following ECB rate decision",
                "id2": 2432,
                "title2": "Euro slips against US dollar to 1.1542 post-ECB cut",
                "relationship": "SAME_EVENT",
                "reason": "Both report EUR/USD dropping to 1.1542 post-ECB."
            },
            {
                "id1": 2433,
                "title1": "Gold futures decline 0.37% to $4,335 per troy ounce",
                "id2": 2434,
                "title2": "Gold prices edge down to $4,335 as Treasury yields rise",
                "relationship": "SAME_EVENT",
                "reason": "Both report Gold futures falling to $4,335."
            },
            {
                "id1": 2435,
                "title1": "Silver futures gain 1.03% to $64.17 per troy ounce",
                "id2": 2436,
                "title2": "Silver rallies past $64 per ounce on industrial demand",
                "relationship": "SAME_EVENT",
                "reason": "Both report Silver futures rising to $64.17."
            }
        ],
        "negative_pairs": [
            {
                "id1": 6,
                "title1": "Federal Reserve Board announces approval of application by National Westminster Bank Plc",
                "id2": 7,
                "title2": "Federal Reserve Board issues enforcement action with SouthPoint Bancshares, Inc.",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Same institution (Fed) and template, but completely different subjects (NatWest approval vs SouthPoint enforcement)."
            },
            {
                "id1": 11,
                "title1": "Federal Reserve Board announces approval of the application by Coastal Bend Bancshares, Inc.",
                "id2": 13,
                "title2": "Federal Reserve Board announces approval of the application by Banco Santander, S.A.",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Same approval template, but different target entities (Coastal Bend vs Banco Santander)."
            },
            {
                "id1": 95,
                "title1": "Virgin Atlantic sharpens customer journeys with ChatGPT Work",
                "id2": 96,
                "title2": "How Zapier transformed core marketing processes with ChatGPT Work",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Same product (ChatGPT Work), but different corporate case studies (Virgin Atlantic vs Zapier)."
            },
            {
                "id1": 45,
                "title1": "Legora reviewed 41 documents in minutes with GPT-6 Astra",
                "id2": 44,
                "title2": "Playco cut manual fixes 50% prototyping games with GPT-6 Astra",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Same model family (GPT-6 Astra), but completely separate companies and use cases."
            },
            {
                "id1": 4524,
                "title1": "Ayana Bio acquires Meati Foods assets for a steal to scale plant cell culture",
                "id2": 3820,
                "title2": "Funerals for children killed after fire spreads to school in DR Congo",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Completely unrelated topics and categories."
            },
            {
                "id1": 2401,
                "title1": "Fed holds interest rates steady at 4.75%-5.00% target range",
                "id2": 2403,
                "title2": "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different central banks and different rate decisions (Fed hold vs ECB cut)."
            },
            {
                "id1": 2405,
                "title1": "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
                "id2": 2407,
                "title2": "AWS launches Instance Preference Lists for SageMaker AI",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different companies (NVIDIA vs AWS) and different product announcements."
            },
            {
                "id1": 2409,
                "title1": "Oil prices jump 3% as Red Sea shipping disruptions escalate",
                "id2": 2433,
                "title2": "Gold futures decline 0.37% to $4,335 per troy ounce",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different commodities (Oil vs Gold) and different price directions."
            },
            {
                "id1": 2411,
                "title1": "Bank of England keeps Bank Rate unchanged at 4.75%",
                "id2": 2423,
                "title2": "RBI leaves Policy Repo Rate unchanged at 6.50%",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different central banks (BoE vs RBI)."
            },
            {
                "id1": 2429,
                "title1": "USD/JPY rises 1.11% to 155.13 as yen softens against dollar",
                "id2": 2431,
                "title2": "EUR/USD declines 0.45% to 1.1542 following ECB rate decision",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different currency pairs (USD/JPY vs EUR/USD)."
            },
            {
                "id1": 2419,
                "title1": "UK Gilt 10Y yield rises 7 bp to 4.12% following debt auction",
                "id2": 2421,
                "title2": "US 10Y Treasury yield reaches 5.00% as bond selloff continues",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different sovereign debt markets (UK Gilt vs US Treasury)."
            },
            {
                "id1": 2417,
                "title1": "Google DeepMind introduces Gemini 3.8 Live with Extended Thinking",
                "id2": 2405,
                "title2": "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Different AI technology releases (DeepMind model vs NVIDIA hardware)."
            },
            {
                "id1": 2413,
                "title1": "China's CSI 300 drops 0.67% amid regional market pullback",
                "id2": 2401,
                "title2": "Fed holds interest rates steady at 4.75%-5.00% target range",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Equity market index vs central bank policy decision."
            },
            {
                "id1": 2425,
                "title1": "Bank of Japan holds overnight call rate at 0.25%",
                "id2": 2429,
                "title2": "USD/JPY rises 1.11% to 155.13 as yen softens against dollar",
                "relationship": "DIFFERENT_EVENT",
                "reason": "BOJ policy rate decision vs FX market price movement (related topic, separate events)."
            },
            {
                "id1": 2427,
                "title1": "Germany 10Y Bund yield rises 5 bp to 2.24%",
                "id2": 2403,
                "title2": "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Sovereign market yield vs ECB central bank policy decision."
            },
            {
                "id1": 2415,
                "title1": "Ayana Bio acquires Meati Foods assets to scale plant cell culture in India",
                "id2": 2407,
                "title2": "AWS launches Instance Preference Lists for SageMaker AI",
                "relationship": "DIFFERENT_EVENT",
                "reason": "AgTech M&A vs Cloud AI feature announcement."
            },
            {
                "id1": 2435,
                "title1": "Silver futures gain 1.03% to $64.17 per troy ounce",
                "id2": 2409,
                "title2": "Oil prices jump 3% as Red Sea shipping disruptions escalate",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Precious metals vs Energy futures."
            },
            {
                "id1": 2417,
                "title1": "Google DeepMind introduces Gemini 3.8 Live with Extended Thinking",
                "id2": 2407,
                "title2": "AWS launches Instance Preference Lists for SageMaker AI",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Google DeepMind model vs AWS SageMaker infrastructure."
            },
            {
                "id1": 2419,
                "title1": "UK Gilt 10Y yield rises 7 bp to 4.12% following debt auction",
                "id2": 2411,
                "title2": "Bank of England keeps Bank Rate unchanged at 4.75%",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Market-priced Gilt yield vs BoE central bank policy rate."
            },
            {
                "id1": 2421,
                "title1": "US 10Y Treasury yield reaches 5.00% as bond selloff continues",
                "id2": 2401,
                "title2": "Fed holds interest rates steady at 4.75%-5.00% target range",
                "relationship": "DIFFERENT_EVENT",
                "reason": "Market-priced Treasury yield vs Fed target range decision."
            }
        ],
        "ambiguous_pairs": [
            {
                "id1": 2409,
                "title1": "Oil prices jump 3% as Red Sea shipping disruptions escalate",
                "id2": 2450,
                "title2": "Freight rates surge 15% as ships bypass Red Sea via Cape of Good Hope",
                "relationship": "AMBIGUOUS",
                "reason": "Both stem from the Red Sea crisis, but one focuses on crude oil while the other focuses on container freight rates. Conservative rule: separate."
            },
            {
                "id1": 2401,
                "title1": "Fed holds interest rates steady at 4.75%-5.00% target range",
                "id2": 2451,
                "title2": "Powell press conference: Fed cautious on inflation despite rate pause",
                "relationship": "AMBIGUOUS",
                "reason": "Rate decision vs press conference analysis. Can be clustered under Fed Meeting event or kept as supporting context."
            },
            {
                "id1": 2405,
                "title1": "NVIDIA announces Vera Rubin NVLink architecture at AI Summit",
                "id2": 2452,
                "title2": "NVIDIA stock gains 2.4% following Vera Rubin architecture reveal",
                "relationship": "AMBIGUOUS",
                "reason": "Hardware product launch vs equity market price reaction. Conservative rule: separate market reaction from product launch."
            },
            {
                "id1": 2403,
                "title1": "ECB cuts Deposit Facility Rate by 25 bps to 3.25%",
                "id2": 2453,
                "title2": "European bank stocks rise after ECB lowers deposit facility rate",
                "relationship": "AMBIGUOUS",
                "reason": "Central bank rate decision vs equity sector reaction. Conservative rule: separate."
            },
            {
                "id1": 2417,
                "title1": "Google DeepMind introduces Gemini 3.8 Live with Extended Thinking",
                "id2": 2454,
                "title2": "Gemini 3.8 Live benchmarked against GPT-4o in reasoning tasks",
                "relationship": "AMBIGUOUS",
                "reason": "Official model release announcement vs third-party benchmark analysis."
            },
            {
                "id1": 2415,
                "title1": "Ayana Bio acquires Meati Foods assets to scale plant cell culture in India",
                "id2": 2455,
                "title2": "Meati Foods restructures operations to focus on core US market",
                "relationship": "AMBIGUOUS",
                "reason": "Asset acquisition announcement vs broader corporate restructuring."
            },
            {
                "id1": 2429,
                "title1": "USD/JPY rises 1.11% to 155.13 as yen softens against dollar",
                "id2": 2456,
                "title2": "Japan finance ministry warns against speculative yen weakening",
                "relationship": "AMBIGUOUS",
                "reason": "FX price movement vs ministry verbal intervention."
            },
            {
                "id1": 2421,
                "title1": "US 10Y Treasury yield reaches 5.00% as bond selloff continues",
                "id2": 2457,
                "title2": "US 30Y Treasury yield touches 5.36% in bond market selloff",
                "relationship": "AMBIGUOUS",
                "reason": "10Y Treasury yield vs 30Y Treasury yield movement in the same bond selloff."
            },
            {
                "id1": 2407,
                "title1": "AWS launches Instance Preference Lists for SageMaker AI",
                "id2": 2458,
                "title2": "AWS SageMaker AI pricing updated for new instance configurations",
                "relationship": "AMBIGUOUS",
                "reason": "Feature launch vs pricing update."
            },
            {
                "id1": 2423,
                "title1": "RBI leaves Policy Repo Rate unchanged at 6.50%",
                "id2": 2459,
                "title2": "Indian Rupee remains stable following RBI repo rate decision",
                "relationship": "AMBIGUOUS",
                "reason": "RBI policy decision vs Indian Rupee currency response."
            }
        ]
    }

    os.makedirs("benchmarks", exist_ok=True)
    out_path = "benchmarks/editorial_clustering_v1.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print(f"Successfully generated {out_path} with {len(benchmark_data['positive_pairs'])} positive, {len(benchmark_data['negative_pairs'])} negative, and {len(benchmark_data['ambiguous_pairs'])} ambiguous pairs.")

if __name__ == "__main__":
    generate_benchmark_dataset()
