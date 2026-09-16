"""
Article Editorial Scorer (Sprint 3 Stage 3B).
Computes a bounded 0-100 explainable Article Editorial Score using deterministic rules.
Contains NO duplication penalty — duplication is handled exclusively by Event Clustering.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.models import Article, ArticleAIOutput


@dataclass
class ArticleEditorialScoreResult:
    article_id: int
    editorial_score: float
    importance_pts: float
    source_pts: float
    recency_pts: float
    strategic_pts: float
    corroboration_pts: float
    explanation: str
    breakdown_json: Dict[str, Any]


def calculate_article_editorial_score(
    article: Article,
    ai_output: Optional[ArticleAIOutput] = None,
    distinct_corroborating_sources: int = 1,
    now: Optional[datetime] = None,
) -> ArticleEditorialScoreResult:
    """
    Calculates deterministic, explainable Article Editorial Score on a 0-100 positive scale.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Importance Component (Max 35 pts)
    imp_score = 70.0
    if ai_output and ai_output.importance_score is not None:
        imp_score = float(ai_output.importance_score)
    elif ai_output and isinstance(ai_output.output_json, dict) and "importance_score" in ai_output.output_json:
        try:
            imp_score = float(ai_output.output_json["importance_score"])
        except (ValueError, TypeError):
            pass

    imp_pts = round((imp_score / 100.0) * 35.0, 1)

    # 2. Source Quality & Provenance (Max 15 pts)
    src_type = article.source.source_type if article.source else "rss"
    trust = article.source.trust_tier if article.source else "useful"

    if src_type in ("CENTRAL_BANK", "GOVERNMENT", "COMPANY_PRIMARY"):
        src_pts = 15.0
    elif trust == "core" or src_type == "INSTITUTIONAL_RESEARCH":
        src_pts = 12.0
    elif trust == "useful":
        src_pts = 9.0
    else:
        src_pts = 6.0

    # 3. Bounded Recency Bonus (Max 15 pts)
    pub_at = article.published_at or article.collected_at
    if pub_at:
        if pub_at.tzinfo is None:
            pub_at = pub_at.replace(tzinfo=timezone.utc)
        hours_old = max(0.0, (now - pub_at).total_seconds() / 3600.0)
        rec_pts = round(max(0.0, 15.0 - (hours_old * 0.5)), 1)
    else:
        rec_pts = 5.05

    # 4. Strategic Category Alignment (Max 20 pts)
    cat = article.primary_category or (article.source.category if article.source else "General")
    cat_lower = (cat or "").lower()
    if any(k in cat_lower for k in ["ai", "tech", "economy", "markets", "monetary", "macro", "energy", "business"]):
        strat_pts = 20.0
    else:
        strat_pts = 12.0

    # 5. Distinct Source Corroboration Bonus (Max 15 pts)
    # +5 pts for each additional distinct source covering the same topic/event
    additional_sources = max(0, distinct_corroborating_sources - 1)
    corrob_pts = round(min(15.0, additional_sources * 5.0), 1)

    total_score = round(min(100.0, max(0.0, imp_pts + src_pts + rec_pts + strat_pts + corrob_pts)), 1)

    explanation = (
        f"Article Score: {total_score:.1f}/100 | Importance ({imp_pts:.1f}/35) + "
        f"Source ({src_pts:.1f}/15) + Recency ({rec_pts:.1f}/15) + Strategic ({strat_pts:.1f}/20) + "
        f"Corroboration ({corrob_pts:.1f}/15)"
    )

    breakdown = {
        "importance_pts": imp_pts,
        "source_pts": src_pts,
        "recency_pts": rec_pts,
        "strategic_pts": strat_pts,
        "corroboration_pts": corrob_pts,
        "total_score": total_score,
    }

    return ArticleEditorialScoreResult(
        article_id=article.id,
        editorial_score=total_score,
        importance_pts=imp_pts,
        source_pts=src_pts,
        recency_pts=rec_pts,
        strategic_pts=strat_pts,
        corroboration_pts=corrob_pts,
        explanation=explanation,
        breakdown_json=breakdown,
    )
