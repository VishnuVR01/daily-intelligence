"""
Deterministic Priority Scoring Engine for Safe AI Processing Queue (Sprint 1 Stage 1B).
Calculates pre-AI article priority scores, tiers (P0-P3), and starvation aging bonuses.
No LLM calls required; purely deterministic and transparent.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models import Article

# --- SIGNAL DICTIONARIES & CONSTANTS ---

TRUST_TIER_SCORES = {
    "primary": 25,
    "institutional": 20,
    "open_source_signal": 15,
    "state_affiliated": 10,
    "useful": 5,
}

SOURCE_FAMILY_SCORES = {
    "central_bank": 20,
    "government": 15,
    "research": 10,
    "university": 10,
    "consulting": 10,
    "news": 5,
    "industry": 5,
    "open_source": 5,
}

SOURCE_CATEGORY_SCORES = {
    "AI & Technology": 15,
    "Geopolitics": 15,
    "Supply Chain & Trade": 12,
    "Markets & Economy": 12,
    "Energy": 12,
    "Commodities": 12,
    "Sustainability": 10,
    "Industry & Operations": 10,
    "Research": 10,
    "World": 8,
    "Business": 8,
}

# Critical Strategic Keywords (+25)
CRITICAL_KEYWORDS = [
    r"\bAI\b", r"\bartificial intelligence\b", r"\bsemiconductor\b", r"\bchip(?:s)?\b",
    r"\bGPU\b", r"\bNvidia\b", r"\bTSMC\b", r"\bOpenAI\b", r"\bAnthropic\b",
    r"\bFederal Reserve\b", r"\bFOMC\b", r"\bECB\b", r"\binterest rate(?:s)?\b",
    r"\binflation\b", r"\bOPEC\b", r"\boil\b", r"\bLNG\b", r"\bwar\b", r"\bceasefire\b",
]

# High Strategic Keywords (+15)
HIGH_KEYWORDS = [
    r"\bsupply chain\b", r"\bshipping\b", r"\bfreight\b", r"\bcontainer\b", r"\btrade route\b",
    r"\bdisruption\b", r"\bgas\b", r"\belectricity\b", r"\bgold\b", r"\bcopper\b",
    r"\bcritical mineral(?:s)?\b", r"\bBank of England\b", r"\bGDP\b", r"\bion bond\b",
    r"\btariff(?:s)?\b", r"\bsanction(?:s)?\b", r"\bBRICS\b", r"\bG7\b", r"\bG20\b",
    r"\bNATO\b", r"\bmanufacturing\b", r"\bautomation\b", r"\brobotics\b",
    r"\bdecarbonisation\b", r"\bnuclear\b", r"\bclimate policy\b",
]

# Normal Strategic Keywords (+8)
NORMAL_KEYWORDS = [
    r"\beconomy\b", r"\bmarket(?:s)?\b", r"\btrade\b", r"\benergy\b", r"\btechnology\b",
    r"\bindustry\b", r"\bproduction\b", r"\brenewable\b", r"\bsolar\b", r"\bwind\b",
    r"\bfactory\b", r"\bmaintenance\b", r"\bresearch\b",
]

# Low-Priority / Negative Keywords (-30)
LOW_PRIORITY_KEYWORDS = [
    r"\bsport(?:s)?\b", r"\bmatch\b", r"\bscore(?:s)?\b", r"\bfootball\b", r"\bbasketball\b",
    r"\bcelebrity\b", r"\bgossip\b", r"\bfashion\b", r"\blifestyle\b", r"\bentertainment\b",
    r"\bhollywood\b", r"\bmovie\b", r"\bactor\b", r"\bactress\b", r"\bhoroscope\b",
]


def calculate_article_priority(
    article: Article,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calculates transparent pre-AI priority scores, tier, and aging bonus for an article.

    Returns:
        {
            "base_score": int (0-100),
            "aging_bonus": float,
            "effective_score": float (0-100),
            "priority_tier": "P0_CRITICAL" | "P1_HIGH" | "P2_NORMAL" | "P3_LOW",
            "reasons": list[str]
        }
    """
    if now is None:
        now = datetime.now(timezone.utc)

    reasons: List[str] = []
    raw_score = 0

    # 1. Source Trust Tier Signal
    trust_tier = "useful"
    if article.source and article.source.trust_tier:
        trust_tier = article.source.trust_tier.lower()

    trust_score = TRUST_TIER_SCORES.get(trust_tier, 5)
    raw_score += trust_score
    reasons.append(f"Trust tier '{trust_tier}' (+{trust_score})")

    # 2. Source Family Signal
    source_family = "news"
    if article.source and article.source.source_family:
        source_family = article.source.source_family.lower()

    family_score = SOURCE_FAMILY_SCORES.get(source_family, 5)
    raw_score += family_score
    reasons.append(f"Source family '{source_family}' (+{family_score})")

    # 3. Source Category Signal
    category = None
    if article.primary_category:
        category = article.primary_category
    elif article.source and article.source.category:
        category = article.source.category

    if category:
        cat_score = SOURCE_CATEGORY_SCORES.get(category, 5)
        raw_score += cat_score
        reasons.append(f"Category '{category}' (+{cat_score})")

    # 4. Keyword Signals in Title & Raw Summary
    text_corpus = f"{article.title or ''} {article.raw_summary or ''}"
    keyword_score = 0

    # Check Negative / Low-Priority Keywords first
    low_priority_matched = []
    for pat in LOW_PRIORITY_KEYWORDS:
        if re.search(pat, text_corpus, re.IGNORECASE):
            match_word = pat.replace(r"\b", "").replace("(?:s)?", "")
            low_priority_matched.append(match_word)

    if low_priority_matched:
        keyword_score -= 30
        reasons.append(f"Low priority material match: {', '.join(low_priority_matched[:2])} (-30)")

    # Check Critical Keywords
    crit_matched = []
    for pat in CRITICAL_KEYWORDS:
        if re.search(pat, text_corpus, re.IGNORECASE):
            match_word = pat.replace(r"\b", "").replace("(?:s)?", "")
            crit_matched.append(match_word)

    if crit_matched:
        keyword_score += 25
        reasons.append(f"Critical keyword match: {', '.join(crit_matched[:3])} (+25)")

    # Check High Keywords
    high_matched = []
    for pat in HIGH_KEYWORDS:
        if re.search(pat, text_corpus, re.IGNORECASE):
            match_word = pat.replace(r"\b", "").replace("(?:s)?", "")
            high_matched.append(match_word)

    if high_matched and not crit_matched:
        keyword_score += 15
        reasons.append(f"High strategic keyword match: {', '.join(high_matched[:3])} (+15)")

    # Check Normal Keywords
    normal_matched = []
    for pat in NORMAL_KEYWORDS:
        if re.search(pat, text_corpus, re.IGNORECASE):
            match_word = pat.replace(r"\b", "").replace("(?:s)?", "")
            normal_matched.append(match_word)

    if normal_matched and not crit_matched and not high_matched:
        keyword_score += 8
        reasons.append(f"Strategic keyword match: {', '.join(normal_matched[:3])} (+8)")

    raw_score += keyword_score

    # Clamp base score to [0, 100]
    base_score = max(0, min(100, raw_score))

    # 5. Aging / Starvation Protection Bonus
    # aging_bonus = min(50.0, waiting_hours * 2.0)
    col_time = article.collected_at or article.published_at or now
    if col_time.tzinfo is None:
        col_time = col_time.replace(tzinfo=timezone.utc)

    waiting_seconds = max(0.0, (now - col_time).total_seconds())
    waiting_hours = waiting_seconds / 3600.0
    aging_bonus = min(50.0, waiting_hours * 2.0)

    if aging_bonus > 0.5:
        reasons.append(f"Aging bonus: {waiting_hours:.1f}h in queue (+{aging_bonus:.1f} pts)")

    effective_score = min(100.0, base_score + aging_bonus)

    # 6. Assign Priority Tier based on effective_score
    if effective_score >= 80:
        tier = "P0_CRITICAL"
    elif effective_score >= 60:
        tier = "P1_HIGH"
    elif effective_score >= 35:
        tier = "P2_NORMAL"
    else:
        tier = "P3_LOW"

    return {
        "base_score": base_score,
        "aging_bonus": round(aging_bonus, 2),
        "effective_score": round(effective_score, 2),
        "priority_tier": tier,
        "reasons": reasons,
    }
