from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from app.models import Article, ArticleAIOutput, Country, Source
from services.markets.models import MarketSnapshot, SovereignYieldSnapshot, MonetaryPolicySnapshot

RelationshipType = Literal["MARKET_MOVING", "RELATED"]

EXPLICIT_MARKET_MOVING_PATTERNS = [
    r"\bstocks?\s+(fell|rose|dropped|surged|tumbled|rallied|slid|sank|gained|lost|plunged)\b",
    r"\bmarkets?\s+(fell|rose|dropped|surged|tumbled|rallied|slid|sank|gained|lost|plunged)\b",
    r"\bshares?\s+(fell|rose|dropped|surged|tumbled|rallied|slid|sank|gained|lost|plunged)\b",
    r"\bindex\s+(fell|rose|dropped|surged|tumbled|rallied|slid|sank|gained|lost|plunged)\b",
    r"\bequities?\s+(fell|rose|dropped|surged|tumbled|rallied|slid|sank|gained|lost|plunged)\b",
    r"\binvestors?\s+(reacted\s+to|weighed|fled|flocked\s+to|poured\s+into)\b",
    r"\bwall\s+street\s+(fell|rose|dropped|surged|tumbled|rallied|slid)\b",
    r"\byields?\s+(spiked|jumped|surged|dropped|fell|climbed|rose|slid)\b",
    r"\bmarket\s+sell-?off\b",
    r"\bstock\s+rally\b",
    r"\boil\s+(prices?\s+)?(fell|rose|surged|dropped|tumbled|spiked|rallied)\b",
    r"\bgold\s+(prices?\s+)?(fell|rose|surged|dropped|tumbled|spiked|rallied)\b",
    r"\bcrude\s+(fell|rose|surged|dropped|tumbled|spiked)\b",
    r"\bcurrency\s+(fell|rose|surged|dropped|tumbled|slid)\b",
    r"\binterest\s+rates?\s+(hike|cut|raised|lowered|slashed|paused|held)\b",
    r"\bcentral\s+bank\s+(hikes?|cuts?|paused?|held|decision)\b",
]

MARKET_AFFINITY_CONFIG: Dict[str, Dict[str, List[str]]] = {
    "United States": {
        "keywords": ["united states", "us", "fed", "federal reserve", "fomc", "powell", "federal funds", "wall street", "s&p", "nasdaq", "dow", "us equities", "us economy", "treasury", "usd", "american"],
        "country_codes": ["US", "USA"],
        "categories": ["Markets", "Business", "Tech", "Economy"],
    },
    "United Kingdom": {
        "keywords": ["united kingdom", "uk", "bank of england", "boe", "bank rate", "mpc", "ftse", "gilt", "uk equities", "british economy", "sterling", "gbp", "london"],
        "country_codes": ["GB", "UK"],
        "categories": ["Markets", "Economy"],
    },
    "India": {
        "keywords": ["india", "rbi", "reserve bank of india", "repo rate", "g-sec", "mpc", "nifty", "sensex", "indian equities", "indian economy", "rupee", "inr", "mumbai"],
        "country_codes": ["IN", "IND"],
        "categories": ["Markets", "Economy"],
    },
    "Japan": {
        "keywords": ["japan", "bank of japan", "boj", "jgb", "overnight call rate", "monetary policy", "nikkei", "japanese equities", "japanese economy", "yen", "jpy", "tokyo"],
        "country_codes": ["JP", "JPN"],
        "categories": ["Markets", "Tech"],
    },
    "Europe": {
        "keywords": ["europe", "eu", "eurozone", "ecb", "european central bank", "deposit facility", "lagarde", "bund", "stoxx", "european equities", "euro", "eur", "frankfurt", "paris"],
        "country_codes": ["DE", "FR", "EU", "IT", "ES"],
        "categories": ["Markets", "Economy", "Geopolitics"],
    },
    "China": {
        "keywords": ["china", "pboc", "people's bank of china", "csi", "shanghai", "shenzhen", "chinese equities", "yuan", "renminbi", "cny", "beijing"],
        "country_codes": ["CN", "CHN"],
        "categories": ["Markets", "Economy", "Tech"],
    },
    "Energy": {
        "keywords": ["oil", "crude", "brent", "wti", "opec", "opec+", "petroleum", "energy supply", "refinery", "middle east supply disruption", "gasoline", "fuel"],
        "country_codes": ["US", "SA", "RU", "AE"],
        "categories": ["Energy", "Markets", "Economy"],
    },
    "Precious Metals": {
        "keywords": ["gold", "silver", "precious metals", "safe haven", "bullion", "comex", "metals", "mining"],
        "country_codes": ["US", "ZA", "AU", "CA"],
        "categories": ["Markets", "Economy"],
    },
    "Critical Minerals": {
        "keywords": ["rare earth", "critical minerals", "strategic metals", "neodymium", "ndpr", "lynas", "mp materials", "mineral supply chain", "remx", "lithium", "cobalt"],
        "country_codes": ["CN", "AU", "US"],
        "categories": ["Mining", "Tech", "Energy"],
    },
    "FX": {
        "keywords": ["currency", "foreign exchange", "forex", "fx", "sterling", "euro", "rupee", "yen", "dollar", "federal reserve", "bank of england", "ecb", "rbi", "bank of japan"],
        "country_codes": ["US", "GB", "EU", "IN", "JP"],
        "categories": ["Markets", "Economy"],
    },
    "Sovereign Yields": {
        "keywords": ["treasury", "bond", "yield", "gilt", "bund", "government bond", "g-sec", "jgb", "debt market", "sovereign debt", "auction", "sovereign yield"],
        "country_codes": ["US", "GB", "DE", "JP", "IN"],
        "categories": ["Markets", "Economy"],
    },
    "Monetary Policy": {
        "keywords": ["monetary policy", "interest rates", "fed", "ecb", "boe", "boj", "rbi", "fomc", "mpc", "central bank", "bank rate", "repo rate", "deposit facility"],
        "country_codes": ["US", "GB", "EU", "JP", "IN"],
        "categories": ["Markets", "Economy"],
    },
}


@dataclass
class MarketIntelligenceMatch:
    article: Article
    market_region: str
    affinity_score: float
    relationship: RelationshipType
    reasons: List[str] = field(default_factory=list)
    published_at: Optional[datetime] = None
    relevance_score: int = 0
    importance_score: int = 0


def classify_causality_relationship(text: str) -> Tuple[RelationshipType, List[str]]:
    """
    Evaluates title, summary, or body text against explicit market-moving patterns.
    Returns ('MARKET_MOVING', reasons) if explicit evidence exists, else ('RELATED', reasons).
    """
    if not text:
        return "RELATED", ["Contextual background story"]

    text_lower = text.lower()
    matches = []

    for pat in EXPLICIT_MARKET_MOVING_PATTERNS:
        if re.search(pat, text_lower):
            matches.append(f"Explicit market-moving phrase match: '{pat}'")

    if matches:
        return "MARKET_MOVING", matches

    return "RELATED", ["Contextual intelligence without explicit market causality link"]


def calculate_article_market_affinity(
    article: Article,
    target_region: str,
) -> Optional[MarketIntelligenceMatch]:
    """
    Calculates deterministic affinity score between an Article and a target Market Region/Category.
    Returns MarketIntelligenceMatch if score > 0, else None.
    """
    config = MARKET_AFFINITY_CONFIG.get(target_region)
    if not config:
        return None

    score = 0.0
    reasons = []

    title = (article.title or "").lower()
    summary = (article.raw_summary or "").lower()
    
    ai_output = None
    if getattr(article, "ai_outputs", None):
        ai_outputs_list = list(article.ai_outputs)
        if ai_outputs_list:
            ai_output = ai_outputs_list[0]

    ai_summary = (ai_output.summary or "").lower() if ai_output else ""
    full_text = f"{title} {summary} {ai_summary}"

    matched_keywords = [kw for kw in config["keywords"] if kw in full_text]
    if matched_keywords:
        score += len(matched_keywords) * 10.0
        reasons.append(f"Matched market keywords: {', '.join(matched_keywords[:3])}")

    if getattr(article, "countries", None):
        for c in article.countries:
            if c.code in config["country_codes"] or (c.name and c.name.lower() in target_region.lower()):
                score += 25.0
                reasons.append(f"Matched country metadata: {c.name or c.code}")
                break

    art_cat = None
    if ai_output and ai_output.primary_category:
        art_cat = ai_output.primary_category
    elif article.source and article.source.category:
        art_cat = article.source.category

    if art_cat and art_cat in config["categories"]:
        score += 15.0
        reasons.append(f"Matched sector category: {art_cat}")

    if score <= 0:
        return None

    imp = ai_output.importance_score if (ai_output and ai_output.importance_score is not None) else 5
    rel = ai_output.relevance_score if (ai_output and ai_output.relevance_score is not None) else 5

    score += (imp * 2.0) + (rel * 1.5)

    relationship, causality_reasons = classify_causality_relationship(f"{article.title} {ai_summary}")
    reasons.extend(causality_reasons)

    pub_date = article.published_at or article.collected_at

    return MarketIntelligenceMatch(
        article=article,
        market_region=target_region,
        affinity_score=round(score, 2),
        relationship=relationship,
        reasons=reasons,
        published_at=pub_date,
        relevance_score=rel,
        importance_score=imp,
    )


def interpret_fx_movement(snapshot: MarketSnapshot) -> Dict[str, str]:
    """
    Interpret FX currency rate movement deterministically.
    """
    symbol = (snapshot.symbol or snapshot.display_name or "").upper()
    direction = snapshot.direction

    if "GBP" in symbol:
        if direction == "UP":
            statement = f"Sterling (GBP) strengthened against USD ({snapshot.change_percent:+,.2f}%)"
            detail = "GBP/USD rose — £1 buys more US Dollars"
        elif direction == "DOWN":
            statement = f"Sterling (GBP) weakened against USD ({snapshot.change_percent:+,.2f}%)"
            detail = "GBP/USD fell — £1 buys fewer US Dollars"
        else:
            statement = "Sterling (GBP) held flat versus USD"
            detail = "GBP/USD unchanged"
    elif "EUR" in symbol:
        if direction == "UP":
            statement = f"Euro (EUR) strengthened against USD ({snapshot.change_percent:+,.2f}%)"
            detail = "EUR/USD rose — €1 buys more US Dollars"
        elif direction == "DOWN":
            statement = f"Euro (EUR) weakened against USD ({snapshot.change_percent:+,.2f}%)"
            detail = "EUR/USD fell — €1 buys fewer US Dollars"
        else:
            statement = "Euro (EUR) held flat versus USD"
            detail = "EUR/USD unchanged"
    elif "INR" in symbol:
        if direction == "UP":
            statement = f"Indian Rupee (INR) weakened versus USD ({snapshot.change_percent:+,.2f}%)"
            detail = "USD/INR rose — $1 buys more Indian Rupees"
        elif direction == "DOWN":
            statement = f"Indian Rupee (INR) strengthened versus USD ({snapshot.change_percent:+,.2f}%)"
            detail = "USD/INR fell — $1 buys fewer Indian Rupees"
        else:
            statement = "Indian Rupee (INR) held flat versus USD"
            detail = "USD/INR unchanged"
    elif "JPY" in symbol:
        if direction == "UP":
            statement = f"Japanese Yen (JPY) weakened versus USD ({snapshot.change_percent:+,.2f}%)"
            detail = "USD/JPY rose — $1 buys more Japanese Yen"
        elif direction == "DOWN":
            statement = f"Japanese Yen (JPY) strengthened versus USD ({snapshot.change_percent:+,.2f}%)"
            detail = "USD/JPY fell — $1 buys fewer Japanese Yen"
        else:
            statement = "Japanese Yen (JPY) held flat versus USD"
            detail = "USD/JPY unchanged"
    else:
        statement = f"{snapshot.display_name} {direction}"
        detail = ""

    return {"statement": statement, "detail": detail}


def get_market_intelligence(
    db: Session,
    selected_region: str = "United States",
    hours_window: int = 48,
    limit_recent: int = 6,
) -> Dict[str, Any]:
    """
    Fetches, ranks, and structures market intelligence stories for the /markets dashboard.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours_window)

    query = (
        db.query(Article)
        .options(
            joinedload(Article.source),
            joinedload(Article.ai_outputs),
            joinedload(Article.countries),
        )
        .filter(
            or_(Article.published_at.is_(None), Article.published_at <= now),
            or_(Article.published_at >= cutoff, Article.collected_at >= cutoff),
        )
        .order_by(Article.published_at.desc().nullslast())
        .limit(100)
    )

    articles = query.all()

    if len(articles) < 3:
        cutoff_7d = now - timedelta(days=7)
        articles = (
            db.query(Article)
            .options(
                joinedload(Article.source),
                joinedload(Article.ai_outputs),
                joinedload(Article.countries),
            )
            .filter(
                or_(Article.published_at.is_(None), Article.published_at <= now),
                or_(Article.published_at >= cutoff_7d, Article.collected_at >= cutoff_7d),
            )
            .order_by(Article.published_at.desc().nullslast())
            .limit(100)
            .all()
        )

    selected_matches: List[MarketIntelligenceMatch] = []
    all_matches: List[MarketIntelligenceMatch] = []

    for art in articles:
        match = calculate_article_market_affinity(art, selected_region)
        if match:
            selected_matches.append(match)

        for r_name in MARKET_AFFINITY_CONFIG.keys():
            m_any = calculate_article_market_affinity(art, r_name)
            if m_any:
                all_matches.append(m_any)
                break

    featured_story: Optional[MarketIntelligenceMatch] = None
    if selected_matches:
        selected_matches.sort(
            key=lambda m: (
                1 if m.relationship == "MARKET_MOVING" else 0,
                m.affinity_score,
                m.published_at.timestamp() if m.published_at else 0,
            ),
            reverse=True,
        )
        featured_story = selected_matches[0]

    seen_ids = set()
    recent_stories: List[MarketIntelligenceMatch] = []
    
    all_matches.sort(
        key=lambda m: (
            1 if m.relationship == "MARKET_MOVING" else 0,
            m.published_at.timestamp() if m.published_at else 0,
            m.importance_score,
        ),
        reverse=True,
    )

    for m in all_matches:
        if m.article.id not in seen_ids:
            seen_ids.add(m.article.id)
            recent_stories.append(m)
            if len(recent_stories) >= limit_recent:
                break

    return {
        "selected_region": selected_region,
        "featured_story": featured_story,
        "selected_matches_count": len(selected_matches),
        "recent_stories": recent_stories,
        "hours_window": hours_window,
    }


def generate_market_takeaways(
    snapshots: List[MarketSnapshot],
    selected_region: str,
    matched_count: int,
    macro_snapshots: Optional[List[MarketSnapshot]] = None,
    yield_snapshots: Optional[List[SovereignYieldSnapshot]] = None,
    policy_snapshots: Optional[List[MonetaryPolicySnapshot]] = None,
) -> List[Dict[str, str]]:
    """
    Generates 3 compact, deterministic market takeaways based on equity market snapshot directions,
    sovereign bond yields, central bank policy rate decisions, and grounded article archive availability.
    """
    if not snapshots:
        return [
            {
                "topic": "GLOBAL SENTIMENT",
                "text": "Market data is currently refreshing. Archive coverage highlights ongoing macroeconomic developments.",
            },
            {
                "topic": "MARKET FOCUS",
                "text": f"Selected region ({selected_region}) monitoring ongoing market sentiment.",
            },
            {
                "topic": "COVERAGE NOTICE",
                "text": "Among currently processed intelligence in the active archive window.",
            },
        ]

    up_count = sum(1 for s in snapshots if s.direction == "UP")
    down_count = sum(1 for s in snapshots if s.direction == "DOWN")
    flat_count = sum(1 for s in snapshots if s.direction == "FLAT")

    # 1. Global Sentiment & Yield Takeaway
    if down_count > up_count and down_count >= 3:
        sent_text = f"Broad risk-off session across tracked equity markets ({down_count} of {len(snapshots)} indices down)."
    elif up_count > down_count and up_count >= 3:
        sent_text = f"Positive risk-on sentiment across global benchmarks ({up_count} of {len(snapshots)} indices up)."
    else:
        sent_text = f"Mixed market sentiment across global regions ({up_count} up, {down_count} down, {flat_count} flat)."

    # Incorporate sovereign yield factual observation if available
    if yield_snapshots:
        us_yield = next((y for y in yield_snapshots if y.instrument_id == "US_10Y_TREASURY"), None)
        if us_yield:
            sign = "+" if us_yield.change_basis_points > 0 else ""
            sent_text += f" US 10Y Treasury yield stands at {us_yield.yield_percent:.2f}% ({sign}{us_yield.change_basis_points:g} bp)."

    # 2. Focus & Monetary Policy Takeaway
    sorted_by_change = sorted(snapshots, key=lambda s: abs(s.change_percent), reverse=True)
    top_mover = sorted_by_change[0] if sorted_by_change else None

    if top_mover:
        focus_text = f"Largest index movement observed in {top_mover.region} ({top_mover.display_name}: {top_mover.change_percent:+,.2f}% {top_mover.direction})."
    else:
        focus_text = f"Market movements in {selected_region} monitored alongside key economic news."

    # Incorporate central bank policy rate factual observation if available
    if policy_snapshots:
        ecb_policy = next((p for p in policy_snapshots if "European Central Bank" in p.central_bank or "ECB" in p.central_bank), None)
        fed_policy = next((p for p in policy_snapshots if "Federal Reserve" in p.central_bank), None)
        if ecb_policy and ecb_policy.rate is not None:
            focus_text += f" ECB Deposit Facility Rate stands at {ecb_policy.rate:.2f}% (Last action: {ecb_policy.action})."
        elif fed_policy and fed_policy.lower_bound is not None:
            focus_text += f" Fed Funds Target Range stands at {fed_policy.lower_bound:.2f}%–{fed_policy.upper_bound:.2f}% (Last action: {fed_policy.action})."

    # 3. Grounded Coverage Notice
    if matched_count > 0:
        cov_text = f"Among currently processed intelligence in the active archive window, {matched_count} stories correlate with market sentiment."
    else:
        cov_text = "Among currently processed intelligence, no explicit market-moving headlines detected in the current 48-hour window."

    return [
        {"topic": "GLOBAL SENTIMENT", "text": sent_text},
        {"topic": "MARKET FOCUS", "text": focus_text},
        {"topic": "COVERAGE NOTICE", "text": cov_text},
    ]
