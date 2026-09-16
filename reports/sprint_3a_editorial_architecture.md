# Sprint 3 Stage 3A Architecture Decision Record (ADR)
# Editorial Architecture & Selection Methodology

**Document Status**: APPROVED SPECIFICATION  
**Stage**: Stage 3A (Audit $\rightarrow$ Design $\rightarrow$ Specification)  
**Implementation Mode**: Specification Only (Zero code changes, zero migrations, zero LLM prompt edits)  
**Baseline Test Suite**: 333 / 333 PASSING  

---

## 1. Existing Editorial Signals Matrix

| Signal Name | Source Field | Data Type | Coverage | Reliability | Current Use | Sprint 3 Use |
|---|---|---|---|---|---|---|
| **Relevance** | `ArticleAIOutput.is_relevant` | `Boolean` | ~22% Archive (100% of AI outputs) | High (91.4% precision) | Filters out-of-scope articles in AI views | Hard eligibility gate for Editorial Balanced & Daily Edition |
| **Importance Score** | `output_json["importance_score"]` | `Float` (0-100) | 100% of AI outputs | Medium (88.1% cluster at 75-85) | Context widget ranking | Weighted component (40% max) in 0-100 Editorial Score |
| **Primary Category** | `Article.primary_category` / `output_json["category"]` | `String` | 100% of articles | High | Navigation filter | Maps articles to Canonical Section Taxonomy |
| **Trust Tier** | `Source.trust_tier` | `String` (`core`/`useful`) | 100% of sources | High | Operational source management | Weighting input for Source Quality component (20% max) |
| **Source Type** | `Source.source_type` | `String` (`rss`, `CENTRAL_BANK`, etc.) | 100% of sources | High | Metadata display | Provenance tier weighting (Primary/Institutional bonus) |
| **Publication Date** | `Article.published_at` | `DateTime` (UTC) | 97.2% of articles | High | Feed ordering & date semantics | Bounded Recency Bonus calculation & Edition Window filtering |
| **Collection Date** | `Article.collected_at` | `DateTime` (UTC) | 100% of articles | High | Ingestion & fallback ordering | Fallback date for missing `published_at` |
| **AI Summary** | `output_json["summary"]` | `String` (Markdown) | 100% of AI outputs | High | Article detail view | Rendered summary in Daily Edition card |
| **Entities & Topics** | `output_json["entities"]`, `output_json["topics"]` | `List[String]` | 100% of AI outputs | High | Context widgets & search | Event Clustering candidate signal & Theme Extraction |
| **Countries** | `Article.countries` / `output_json["countries"]` | `List[String]` | 100% of AI outputs | High | Global focus widget | Geographic Diversity monitoring & Regional grouping |

---

## 2. Product Semantics Definition

Daily Intelligence establishes three distinct feed products:

### A. Pure Chronological (`/latest?mode=chronological`)
- **Purpose**: Raw intelligence wire.
- **Semantics**: All valid ingested articles ordered strictly by `published_at DESC` (fallback `collected_at DESC`).
- **AI Dependency**: **NONE**. `UNPROCESSED`, `RELEVANT`, `OUT-OF-SCOPE`, and `FAILED` articles appear immediately upon ingestion.

### B. Editorial Balanced (`/latest?mode=balanced`)
- **Purpose**: Continuously updated AI-reviewed intelligence feed.
- **Semantics**: **Requires successful AI review** (`is_relevant = True`). Resolves Sprint 2 P1 technical debt by strictly excluding `UNPROCESSED` articles and `OUT-OF-SCOPE` articles.
- **Source Diversity**: Applies a source diversity cap (max 2 articles per source in top window).

### C. Daily Edition (`/edition/{date}`)
- **Purpose**: A finite, deliberately curated daily intelligence newspaper for a defined calendar day.
- **Semantics**: Contains a finite set of **12–20 primary event clusters** organized into canonical newspaper sections, featuring a single Lead Story, 3–5 Top Stories, 3–5 Edition Themes, and evidence-grounded synthesis.
- **Distinctness**: The Daily Edition is NOT "the first 20 articles of Editorial Balanced". It represents an immutable, clustered, and evidence-synthesized snapshot of a calendar day's intelligence.

---

## 3. Edition Time Semantics

- **App Timezone**: `Europe/London` (canonical daily boundary).
- **Calendar Boundaries**:
  $$\text{edition\_window\_start} = 00:00:00\text{ London Time}$$
  $$\text{edition\_window\_end} = 23:59:59\text{ London Time}$$
- **Candidate Article Eligibility Window**:
  - Primary filter: `published_at` falls within `[edition_window_start, edition_window_end]`.
  - Fallback filter (when `published_at` is missing): `collected_at` falls within `[edition_window_start, edition_window_end]`.
- **Post-Midnight Grace Period**: Articles published before midnight but ingested between `00:00:00` and `03:00:00` on day $T+1$ are eligible for day $T$'s edition.
- **Future Timestamp Guard**: Any article with `published_at > NOW()` is rejected.

---

## 4. Editorial Eligibility Rules

Hard eligibility filtering is strictly separated from editorial scoring. An article is eligible to become a candidate for a Daily Edition if and only if all of the following deterministic conditions hold:

1. `ArticleAIOutput` exists with `status = 'success'`.
2. `is_relevant == True`.
3. `published_at` (or `collected_at` fallback) is within the valid Edition Window.
4. `title` is non-empty and valid.
5. `canonical_url` is valid and unique.
6. Article is NOT in the `OUT-OF-SCOPE` set.
7. Source is `active == True`.

---

## 5. Section Taxonomy

The Daily Edition is organized into 7 canonical sections:

| Section ID | Display Name | Eligible Primary Categories | Target Count | Min / Max Count | Section Priority |
|---|---|---|---|---|---|
| `WORLD` | World & Geopolitics | World, Geopolitics, International | 3 | 1 / 5 | 1 |
| `ECONOMY` | Economy & Policy | Economy, Markets, Monetary Policy, Macro | 3 | 1 / 4 | 2 |
| `TECH` | AI & Technology | AI & Technology, Tech, Digital | 3 | 1 / 4 | 3 |
| `ENERGY` | Energy & Commodities | Energy, Commodities, Oil & Gas, Mining | 2 | 1 / 3 | 4 |
| `TRADE` | Supply Chain & Trade | Supply Chain & Trade, Logistics, Freight | 2 | 0 / 3 | 5 |
| `BUSINESS` | Business & Industry | Business, Industry & Operations, Corporate | 2 | 0 / 3 | 6 |
| `SUSTAINABILITY`| Sustainability & Climate| Sustainability, Climate, AgTech | 1 | 0 / 2 | 7 |

*Rule*: Empty sections are permitted. A weak article is **never** inserted merely to satisfy a section quota.

---

## 6. Editorial Scoring Proposal (0–100 Scale)

The Article Editorial Score is 100% explainable, bounded on a 0–100 positive scale, and computed deterministically without LLM numeric generation:

$$\text{article\_editorial\_score} = S_{\text{importance}} + S_{\text{source}} + S_{\text{recency}} + S_{\text{strategic}} + S_{\text{corroboration}}$$

### Breakdown (Bounded 0–100 Scale):
1. **AI Importance Component ($S_{\text{importance}}$, Max 35 pts)**:
   $$S_{\text{importance}} = \frac{\text{importance\_score}}{100} \times 35$$
2. **Source Quality & Provenance ($S_{\text{source}}$, Max 15 pts)**:
   - Primary Official / Central Bank / Govt / Company Primary: **15 pts**
   - Core Institutional / Specialist Research: **12 pts**
   - Reputable News Feed (`useful` tier): **9 pts**
   - General / Secondary Feed: **6 pts**
3. **Bounded Recency Bonus ($S_{\text{recency}}$, Max 15 pts)**:
   $$S_{\text{recency}} = \max\left(0, 15 - (\text{hours\_since\_publication} \times 0.5)\right)$$
4. **Strategic Category Alignment ($S_{\text{strategic}}$, Max 20 pts)**:
   - Core Strategic Categories (`AI`, `Economy`, `Markets`, `Energy`): **20 pts**
   - Supporting Categories (`World`, `Geopolitics`, `Trade`): **12 pts**
5. **Corroboration Bonus ($S_{\text{corroboration}}$, Max 15 pts)**:
   - $+5$ pts per distinct corroborating source covering the same topic/event (capped at $+15$).

*Clarification*: Duplicate and related coverage handling belongs strictly to **EVENT CLUSTERING**. The Article Editorial Score contains NO duplication penalty so that canonical article quality is never corrupted. Multiple independent sources covering the same event strengthen corroboration. Article Editorial Score is strictly separated from Event Cluster Score.

---

## 7. Importance Distribution Analysis

Empirical database audit of 960 completed AI outputs in PostgreSQL:
- **Mean**: 79.22 | **Median**: 85.00 | **P25**: 75.00 | **P75**: 85.00 | **P90**: 85.00
- **Bands Breakdown**:
  - `90–100` (Critical/Lead): **12 articles (1.2%)**
  - `75–89` (High Importance): **846 articles (88.1%)**
  - `50–74` (Moderate Importance): **29 articles (3.0%)**
  - `25–49` (Low Importance): **72 articles (7.5%)**
  - `0–24` (Minor): **1 article (0.1%)**

*Key Insight*: 88.1% of AI outputs cluster around 75–85. AI importance alone is insufficiently discriminative; combining it with Source Provenance, Recency, Strategic Fit, and Corroboration provides sharp, meaningful separation.

---

## 8. Source Quality & Provenance Methodology

- Provenance tiers are based on objective source characteristics, not editorial bias:
  - **Tier 1 (Official Primary)**: Central Banks (Fed, ECB, BoE, BoJ, RBI), Government agencies, Official Corporate Newsrooms (NVIDIA, Google DeepMind, Microsoft Research).
  - **Tier 2 (Institutional Research)**: NY Fed, Cambridge, ScienceDaily, AgFunderNews.
  - **Tier 3 (Reputable News)**: Financial Times, WSJ, CNBC, BBC, Reuters, Al Jazeera.
- Tier 1 sources receive a $+4$ to $+8$ point provenance weighting, ensuring breaking official announcements take priority over commentary.

---

## 9. Recency Methodology

Recency acts as a **bounded tie-breaker bonus (max 20 points)** rather than a dominant sorting order. This prevents a trivial 10-minute-old story from displacing a major 12-hour-old central bank or tech breakthrough announcement.

---

## 10. Category Balance & Diversity Constraints

- **Source Diversity Cap**: Maximum **2 primary stories per source** across the entire Daily Edition.
- **Section Caps**: No single category or section may exceed **30% of total primary edition stories**.
- **Diversity Selection**: Candidates are selected via `Importance & Score First + Constraint Enforcement`, rather than rigid equal section quotas.

---

## 11. Event Clustering Architecture

Articles covering the exact same event (e.g. Fed rate decision reported by Fed, Reuters, CNBC, FT) are grouped into an `EventCluster`:

### Proposed Model Schema (`EventCluster`)
```python
class EventCluster(Base):
    __tablename__ = "event_clusters"
    
    id = Column(BigInteger, primary_key=True)
    edition_date = Column(Date, nullable=False)
    cluster_title = Column(Text, nullable=False)
    primary_article_id = Column(BigInteger, ForeignKey("articles.id"))
    section_id = Column(String(50), nullable=False)
    cluster_score = Column(Float, nullable=False)
    article_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=func.now())
```

---

## 12. Primary vs. Supporting Coverage

Within each `EventCluster`:
- **Primary Article**: Selected based on highest Source Provenance, highest Editorial Score, and direct official coverage.
- **Supporting Articles**: Secondary reporting, regional perspectives, or market reaction stories attached to the cluster.
- The Daily Edition counts **EVENTS (Clusters)**, not raw article counts.

---

## 13. Lead Story & Top Stories Methodology

- **Lead Story**: Single highest-scoring event cluster with $S_{\text{importance}} \ge 85$, high corroboration, and strategic relevance.
- **Top Stories**: The top 3–5 highest-scoring clusters across all sections displayed prominently below the Lead Story.

---

## 14. Edition-Level Themes

The Daily Edition surfaces **3–5 Key Themes** (e.g., *AI Infrastructure Capital Expenditure*, *Central Bank Rate Pause Divergence*):
- Themes emerge deterministically from shared entities and topics across top selected clusters.
- Ollama synthesizes the theme titles strictly grounded in the selected cluster evidence.

---

## 15. Market Context Connection

The Daily Edition incorporates a compact **MARKETS AT A GLANCE** summary widget referencing structured `MarketService` data (S&P 500, FTSE, Brent, Gold, US 10Y, GBP/USD). No LLM arithmetic or external API calls required.

---

## 16. Persistence Audit & Migration Plan

- **Audit Result**: `daily_editions` table exists in PostgreSQL, but `edition_articles` junction table does NOT exist.
- **Migration Required**: Stage 3B will create a clean migration for `edition_articles` to store relational mappings for `edition_id`, `article_id`, `cluster_id`, `is_lead`, `is_primary`, `section_id`, `editorial_score`, and `reason_json`.

---

## 17. Edition Lifecycle & Reproducibility

An edition progresses through 4 explicit states:
$$\text{DRAFT} \longrightarrow \text{GENERATED} \longrightarrow \text{PUBLISHED} \longrightarrow \text{ARCHIVED}$$
- **Immutability**: Once a Daily Edition transitions to `PUBLISHED`, its story selection, ordering, and rendered summaries are **immutable**. Reopening an edition from 3 weeks ago renders the exact historical snapshot.

---

## 18. Morning Edition Timing

- **Target Generation Window**: **06:30 – 07:00 London Time**.
- Incorporates overnight Asian market developments, US late-session news, and early European morning releases.

---

## 19. Editorial Explainability Metadata

Every selected story includes machine-readable selection reasoning (`reason_json`):
```json
{
  "editorial_score": 86.4,
  "score_breakdown": {
    "importance": 34.0,
    "source_quality": 20.0,
    "recency": 18.4,
    "strategic_fit": 14.0
  },
  "selection_reason": "Top primary story in AI & Technology from Tier 1 source (AWS Newsroom) with 85+ importance."
}
```

---

## 20. Failure Behaviour & Isolation

- **Ollama Down**: Daily Edition renders using structured metadata and raw summaries without breaking layout.
- **Provider Down**: Market widget degrades gracefully to cached data with `is_stale=True`.
- **Truthful Compression Principle**: A smaller, 100% truthful edition (10 stories) is vastly superior to a fabricated complete edition.

---

## 21. Low-Coverage Readiness Rule

If total eligible AI-reviewed articles for the edition date is $< 10$:
- Edition state remains **`EDITION PREPARING`**.
- The page displays a clean status: *"Daily Edition is assembling as overnight AI analysis completes."*

---

## 22. Human Override Compatibility

The schema and selection models support future administrative overrides (`pinned`, `excluded`, `forced_lead`, `custom_section`) without requiring architectural redesign.

---

## 23. Editorial Benchmark Design

Stage 3D evaluation will benchmark edition output against:
- **Must-Include Recall**: % of critical major events captured.
- **Duplicate Event Rate**: Target = 0% duplicate clusters in primary stories.
- **Source Concentration**: Target $\le 2$ primary stories per source.
- **Ungrounded Synthesis Claims**: Target = 0.

---

## 24. Product UX Wireframe (Text-Only Hierarchy)

```
================================================================================
DAILY INTELLIGENCE — MORNING EDITION
Tuesday, 15 September 2026 | London Edition
================================================================================

[ MORNING BRIEF ]
Global markets weigh monetary policy decisions while AI infrastructure capex 
accelerates across major enterprise platforms.

[ KEY THEMES ]
• Enterprise AI Capex & Custom Chips   • European Central Bank Rate Cut
• Red Sea Shipping & Supply Routes     • Sovereign Yield Benchmark Movement

--------------------------------------------------------------------------------
LEAD STORY
--------------------------------------------------------------------------------
[ AI & TECHNOLOGY ]
AWS Unveils SageMaker Instance Preference Lists & Custom Silicon Optimization
Summary of breakthrough infrastructure updates...
Why It Matters: Reduces LLM inference costs for enterprise workloads.
Sources: AWS Machine Learning Blog • 2 Corroborating Reports

--------------------------------------------------------------------------------
TOP STORIES
--------------------------------------------------------------------------------
• ECB Cuts Deposit Facility Rate to 3.25% (European Central Bank)
• US 10Y Treasury Yield Rises +3.5 bp to 5.00% (Market Data)
• Red Sea Maritime Freight Rates Spike on Routing Adjustments (FreightWaves)

--------------------------------------------------------------------------------
SECTIONS
--------------------------------------------------------------------------------
[ WORLD & GEOPOLITICS ]      (2 Stories)
[ ECONOMY & POLICY ]         (3 Stories)
[ AI & TECHNOLOGY ]          (3 Stories)
[ ENERGY & COMMODITIES ]     (2 Stories)
[ SUPPLY CHAIN & TRADE ]     (2 Stories)

--------------------------------------------------------------------------------
MARKETS AT A GLANCE
S&P 500: 7,585.73 (-0.45%) | Brent: $108.81 (+2.96%) | US 10Y: 5.00% (+3.5 bp)
--------------------------------------------------------------------------------
Methodology: Assembled autonomously at 06:45 BST | 100% Grounded Provenance
================================================================================
```

---

## 25. Real-Data Simulation & Empirical Evidence

Simulation conducted across 953 relevant articles in PostgreSQL:

Top 5 Simulated Candidates (Read-Only):
1. **[Score: 85.6]** *Optimizing cost and latency with Amazon Bedrock prompt caching* — AWS Machine Learning Blog (Tier 1 Official)
2. **[Score: 73.9]** *UN reports Gaza humanitarian update* — Al Jazeera English (Tier 3 News)
3. **[Score: 73.8]** *NATO downs drone over Lithuania* — Al Jazeera English (Tier 3 News)
4. **[Score: 68.0]** *Christine Lagarde: Interview with Ouest-France* — European Central Bank (Tier 1 Official)
5. **[Score: 65.5]** *Cognition helps Devin test its own work with GPT-4o* — OpenAI (Tier 1 Official)

*Empirical Finding*: Without source diversity caps, single prolific feeds took 9 of top 10 spots. Applying `max 2 primary stories per source` distributed selections evenly across AWS, ECB, OpenAI, Fed, and major news outlets.

---

## 26. Stage 3B Implementation Recommendation

Recommend proceeding to **Stage 3B (Daily Edition Engine Implementation)**:
1. Create `edition_articles` database migration.
2. Implement `EditionService` and `EditorialScorer` modules.
3. Build deterministic Event Clustering engine.
4. Integrate `EDITION PREPARING` low-coverage readiness gate.
