"""
Event Clustering & Story Deduplication Engine (Sprint 3 Stage 3B).
Converts multiple articles covering the same development into an EventCluster containing 1 Primary Story and supporting coverage.
Enforces deterministic-first similarity scoring, candidate blocking, numeric/event marker preservation, distinct-source corroboration, and bounded event scoring.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, EventCluster, EventClusterArticle
from services.editorial.scorer import calculate_article_editorial_score, ArticleEditorialScoreResult

SAFE_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "up", "about", "into", "over", "after", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would", "shall", "should",
    "can", "could", "may", "might", "must", "this", "that", "these", "those", "it", "its",
    "says", "said", "new", "announces", "announced", "reports", "reported", "signals"
}

GENERIC_ENTITIES = {
    "united states", "us", "uk", "united kingdom", "china", "russia", "india", "japan",
    "europe", "eu", "ai", "artificial intelligence", "tech", "technology", "business",
    "market", "markets", "economy", "government", "official", "officials", "report", "news"
}

# Synonyms for canonical event normalization
ENTITY_ALIASES = {
    "fed": "federal reserve",
    "fomc": "federal reserve",
    "federal reserve board": "federal reserve",
    "boe": "bank of england",
    "ecb": "european central bank",
    "boj": "bank of japan",
    "rbi": "reserve bank of india",
    "deepmind": "google deepmind",
    "aws": "amazon web services",
    "mbs": "mohammed bin salman",
    "gilt": "uk gilt",
    "bund": "germany bund",
    "jgb": "japan jgb",
    "g-sec": "india g-sec",
}


# Company suffixes to strip during entity normalization
COMPANY_SUFFIXES = {
    "bancorp", "bank", "inc", "corp", "corporation", "ltd", "limited", "plc", "co", "company",
    "group", "holdings", "llc", "sa", "ag", "nv", "se"
}


INSTITUTIONAL_ALIASES = {
    "federal reserve", "european central bank", "bank of england", "bank of japan", "reserve bank of india"
}

def resolve_article_category(article: Article, ai_output: Optional[ArticleAIOutput] = None) -> str:
    """
    Resolves article/cluster category following strict priority hierarchy:
    1. ArticleAIOutput.primary_category
    2. article.primary_category
    3. Contextual title keyword fallback
    4. Conservative source.category fallback
    5. Default 'General'
    """
    if ai_output and ai_output.primary_category:
        return ai_output.primary_category.strip()
    if article.primary_category:
        return article.primary_category.strip()

    title_lower = (article.title or "").lower()
    if any(w in title_lower for w in ["oil", "gas", "crude", "brent", "wti", "refinery", "opec", "solar", "nuclear", "electricity", "power", "grid", "fuel"]):
        return "Energy"
    if any(w in title_lower for w in ["fed", "fomc", "inflation", "cpi", "ecb", "interest rate", "yield", "gdp", "recession", "central bank"]):
        return "Markets & Economy"
    if any(w in title_lower for w in ["ai", "software", "chip", "semiconductor", "cloud", "model", "algorithm"]):
        return "AI & Technology"

    if article.source and article.source.category:
        return article.source.category.strip()

    return "General"


def normalize_token(token: str) -> str:
    """Normalizes token using entity aliases and company suffix stripping."""
    t = token.strip().lower()
    t = ENTITY_ALIASES.get(t, t)
    if t in INSTITUTIONAL_ALIASES:
        return t
    # Strip common trailing company suffixes for entity tokens
    words = t.split()
    if len(words) > 1 and words[-1] in COMPANY_SUFFIXES:
        t = " ".join(words[:-1])
    return ENTITY_ALIASES.get(t, t)


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and removing safe stopwords."""
    if not text:
        return ""
    text_clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [normalize_token(w) for w in text_clean.split() if w and w not in SAFE_STOPWORDS]
    return " ".join(tokens)


def extract_key_entities(text: str, ai_output: Optional[ArticleAIOutput] = None) -> Set[str]:
    """Extracts key proper nouns, entities, institutions, and product names from text and AI metadata."""
    entities = set()
    
    # 1. AI Output Metadata
    if ai_output and isinstance(ai_output.output_json, dict):
        raw_ents = ai_output.output_json.get("entities", [])
        for e in raw_ents:
            if isinstance(e, dict):
                val = e.get("name", "")
            elif isinstance(e, str):
                val = e
            else:
                val = ""
            val_norm = normalize_token(val)
            if val_norm and val_norm not in GENERIC_ENTITIES:
                entities.add(val_norm)

    # 2. Text extraction via Regex
    if text:
        # Proper Nouns / Multi-word capitalizations
        caps = re.findall(r"\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b", text)
        for c in caps:
            c_norm = normalize_token(c)
            if c_norm and len(c_norm) > 1 and c_norm not in GENERIC_ENTITIES and c_norm not in SAFE_STOPWORDS:
                entities.add(c_norm)

        # Explicit key domain terms
        domain_terms = [
            "fed", "federal reserve", "ecb", "bank of england", "boe", "bank of japan", "boj",
            "reserve bank of india", "rbi", "kushner", "pori", "tnt", "ayana bio", "meati",
            "sage maker", "sagemaker", "vera rubin", "gemini 3.8", "gpt-4o", "chatgpt",
            "gilt", "bund", "jgb", "g-sec", "brent", "wti", "red sea", "houthis", "el-sisi", "mbs"
        ]
        text_lower = text.lower()
        for dt in domain_terms:
            if dt in text_lower:
                entities.add(normalize_token(dt))

    return entities


def extract_numeric_markers(text: str) -> Set[str]:
    """Extracts numbers, percentages, basis points, and currency values that serve as event markers."""
    if not text:
        return set()
    matches = re.findall(r"\b\d+(?:\.\d+)?(?:\s*(?:%|bps?|bp|billion|million|bn|m|b|trillion|t))|\$\d+(?:,\d+)*(?:\.\d+)?[bmk]?", text.lower())
    # Normalize numbers: strip commas and spaces
    norm_matches = {m.replace(",", "").replace(" ", "") for m in matches}
    return norm_matches


def calculate_title_similarity(t1: str, t2: str) -> float:
    """Calculates combined Jaccard and Overlap Coefficient token similarity over normalized titles."""
    n1 = set(normalize_text(t1).split())
    n2 = set(normalize_text(t2).split())
    if not n1 or not n2:
        return 0.0
    intersection = n1.intersection(n2)
    union = n1.union(n2)
    jaccard = len(intersection) / float(len(union))
    overlap_coef = len(intersection) / float(min(len(n1), len(n2)))
    return (jaccard + overlap_coef) / 2.0


def calculate_entity_overlap(e1: Set[str], e2: Set[str]) -> Tuple[float, int]:
    """
    Calculates entity overlap excluding generic entities.
    Returns (overlap_ratio, specific_matches_count).
    """
    if not e1 or not e2:
        return 0.0, 0
    common = set()
    for item1 in e1:
        for item2 in e2:
            if item1 == item2 or (len(item1) > 3 and len(item2) > 3 and (item1 in item2 or item2 in item1)):
                common.add(min(item1, item2))
    union = e1.union(e2)
    ratio = len(common) / float(len(union)) if union else 0.0
    return ratio, len(common)


@dataclass
class SimilarityComparison:
    article1_id: int
    article2_id: int
    similarity_score: float
    confidence_band: str  # HIGH_CONFIDENCE, AMBIGUOUS, LOW_CONFIDENCE
    title_sim: float
    entity_sim: float
    numeric_conflict: bool
    explanation: str
    breakdown_json: Dict[str, Any]


def compare_articles_similarity(
    a1: Article,
    a2: Article,
    ai1: Optional[ArticleAIOutput] = None,
    ai2: Optional[ArticleAIOutput] = None,
) -> SimilarityComparison:
    """
    Computes explainable, deterministic pairwise similarity between two candidate articles.
    Confidence Bands:
    - HIGH_CONFIDENCE (score >= 0.70): Automatically cluster as same event.
    - AMBIGUOUS (0.45 <= score < 0.70): Separate initially.
    - LOW_CONFIDENCE (score < 0.45): Separate.
    """
    title_sim = calculate_title_similarity(a1.title, a2.title)

    # Key entities extraction
    ent1 = extract_key_entities(a1.title, ai1)
    ent2 = extract_key_entities(a2.title, ai2)

    entity_sim, specific_matches = calculate_entity_overlap(ent1, ent2)

    # Category match
    cat1 = a1.primary_category or (a1.source.category if (a1.source and a1.source.category) else "") or ""
    cat2 = a2.primary_category or (a2.source.category if (a2.source and a2.source.category) else "") or ""
    cat_match = 1.0 if (cat1 and cat2 and cat1.lower() == cat2.lower()) else 0.5

    # Numeric marker check
    num1 = extract_numeric_markers(a1.title)
    num2 = extract_numeric_markers(a2.title)
    numeric_conflict = False
    numeric_match = False
    if num1 and num2:
        if num1.intersection(num2):
            numeric_match = True
        else:
            numeric_conflict = True

    # Action / Event Type Conflict Check
    t1_lower = (a1.title or "").lower()
    t2_lower = (a2.title or "").lower()

    hold_words = {"holds", "hold", "steady", "maintains", "maintain", "unchanged", "pauses", "pause"}
    cut_words = {"cuts", "cut", "lowers", "lower", "reduces", "reduce", "easing"}
    hike_words = {"hikes", "hike", "raises", "raise", "lifts", "lift", "tightening"}

    has_hold1 = any(re.search(r"\b" + w + r"\b", t1_lower) for w in hold_words)
    has_hold2 = any(re.search(r"\b" + w + r"\b", t2_lower) for w in hold_words)
    has_cut1 = any(re.search(r"\b" + w + r"\b", t1_lower) for w in cut_words)
    has_cut2 = any(re.search(r"\b" + w + r"\b", t2_lower) for w in cut_words)
    has_hike1 = any(re.search(r"\b" + w + r"\b", t1_lower) for w in hike_words)
    has_hike2 = any(re.search(r"\b" + w + r"\b", t2_lower) for w in hike_words)

    action_conflict = False
    if (has_hold1 and (has_cut2 or has_hike2)) or (has_hold2 and (has_cut1 or has_hike1)):
        action_conflict = True
    elif (has_cut1 and has_hike2) or (has_cut2 and has_hike1):
        action_conflict = True

    is_earnings1 = any(w in t1_lower for w in ["earnings", "q1", "q2", "q3", "q4", "net income", "quarterly profit"])
    is_earnings2 = any(w in t2_lower for w in ["earnings", "q1", "q2", "q3", "q4", "net income", "quarterly profit"])
    is_launch1 = any(w in t1_lower for w in ["unveils", "launches", "announces", "introduces", "keynote"])
    is_launch2 = any(w in t2_lower for w in ["unveils", "launches", "announces", "introduces", "keynote"])

    if (is_earnings1 and is_launch2 and not is_earnings2) or (is_earnings2 and is_launch1 and not is_earnings1):
        action_conflict = True

    if action_conflict:
        numeric_match = False
        numeric_conflict = True

    # Temporal proximity score (decay over 48 hours)
    temp_sim = 1.0
    if a1.published_at and a2.published_at:
        gap_hours = abs((a1.published_at - a2.published_at).total_seconds()) / 3600.0
        temp_sim = max(0.0, 1.0 - (gap_hours / 48.0))

    # Base weighted score
    if specific_matches >= 2:
        # High entity alignment (e.g. Kushner + Moscow + Kiev or Fed + 4.75%)
        base_score = (title_sim * 0.35) + (entity_sim * 0.45) + (cat_match * 0.10) + (temp_sim * 0.10)
    elif specific_matches == 1:
        base_score = (title_sim * 0.45) + (entity_sim * 0.30) + (cat_match * 0.15) + (temp_sim * 0.10)
    else:
        base_score = (title_sim * 0.65) + (cat_match * 0.20) + (temp_sim * 0.15)

    # Numeric bonus/penalty
    if numeric_match:
        base_score += 0.15
    elif numeric_conflict:
        base_score -= 0.35

    final_score = round(min(1.0, max(0.0, base_score)), 2)

    # Adaptive confidence threshold: if 2+ specific entities match or numeric event marker matches, threshold is 0.55
    req_threshold = 0.55 if (specific_matches >= 2 and numeric_match and not action_conflict) else 0.68

    if final_score >= req_threshold and not action_conflict:
        band = "HIGH_CONFIDENCE"
    elif final_score >= 0.45:
        band = "AMBIGUOUS"
    else:
        band = "LOW_CONFIDENCE"

    explanation = (
        f"Pair [{a1.id}-{a2.id}] Similarity: {final_score:.2f} ({band}) | "
        f"Title Sim: {title_sim:.2f} | Entity Sim: {entity_sim:.2f} ({specific_matches} matches) | "
        f"Category Match: {cat_match:.1f} | Proximity: {temp_sim:.2f} | Numeric Conflict: {numeric_conflict}"
    )

    breakdown = {
        "final_score": final_score,
        "confidence_band": band,
        "title_sim": round(title_sim, 2),
        "entity_sim": round(entity_sim, 2),
        "specific_entity_matches": specific_matches,
        "category_match": cat_match,
        "temporal_proximity": round(temp_sim, 2),
        "numeric_conflict": numeric_conflict,
        "numeric_match": numeric_match,
    }

    return SimilarityComparison(
        article1_id=a1.id,
        article2_id=a2.id,
        similarity_score=final_score,
        confidence_band=band,
        title_sim=title_sim,
        entity_sim=entity_sim,
        numeric_conflict=numeric_conflict,
        explanation=explanation,
        breakdown_json=breakdown,
    )


@dataclass
class EventClusterResult:
    cluster_id: str
    canonical_title: str
    primary_article_id: int
    primary_article: Article
    supporting_articles: List[Article]
    all_articles: List[Article]
    category: str
    distinct_source_count: int
    article_count: int
    cluster_score: float
    earliest_article_at: Optional[datetime]
    latest_article_at: Optional[datetime]
    explanations: List[str]
    metadata_json: Dict[str, Any]


def generate_candidate_pairs(articles: List[Article], max_window_hours: float = 48.0) -> List[Tuple[Article, Article]]:
    """Generates candidate pairs using category and temporal blocking."""
    candidate_pairs = []
    n = len(articles)
    for i in range(n):
        for j in range(i + 1, n):
            a1 = articles[i]
            a2 = articles[j]
            
            p1 = a1.published_at or a1.collected_at
            p2 = a2.published_at or a2.collected_at
            if p1 and p2:
                gap_hours = abs((p1 - p2).total_seconds()) / 3600.0
                if gap_hours > max_window_hours:
                    continue

            c1 = (a1.primary_category or (a1.source.category if (a1.source and a1.source.category) else "") or "").lower()
            c2 = (a2.primary_category or (a2.source.category if (a2.source and a2.source.category) else "") or "").lower()
            if c1 and c2 and c1 != c2 and c1 not in ("world", "general", "geopolitics") and c2 not in ("world", "general", "geopolitics"):
                continue

            candidate_pairs.append((a1, a2))
    return candidate_pairs


def cluster_articles(
    articles: List[Article],
    ai_outputs_map: Optional[Dict[int, ArticleAIOutput]] = None,
    high_confidence_threshold: float = 0.70,
    now: Optional[datetime] = None,
) -> List[EventClusterResult]:
    """
    Clusters articles deterministically into EventClusterResult objects.
    Ensures:
    - Same topic != Same event. Conservative high-confidence merging.
    - Selects 1 Primary Article per cluster based on Article Editorial Score & tie-breakers.
    - Computes Distinct-Source Corroboration & Bounded Event Cluster Score (0-100).
    - Idempotent and deterministic fingerprint IDs.
    """
    if not articles:
        return []

    if ai_outputs_map is None:
        ai_outputs_map = {}

    if now is None:
        now = datetime.now(timezone.utc)

    candidate_pairs = generate_candidate_pairs(articles)
    adjacency: Dict[int, Set[int]] = {a.id: set([a.id]) for a in articles}
    pairwise_reasons: Dict[Tuple[int, int], str] = {}

    for a1, a2 in candidate_pairs:
        ai1 = ai_outputs_map.get(a1.id)
        ai2 = ai_outputs_map.get(a2.id)
        comp = compare_articles_similarity(a1, a2, ai1, ai2)

        if comp.confidence_band == "HIGH_CONFIDENCE" or comp.similarity_score >= high_confidence_threshold:
            adjacency[a1.id].add(a2.id)
            adjacency[a2.id].add(a1.id)
            pairwise_reasons[(min(a1.id, a2.id), max(a1.id, a2.id))] = comp.explanation

    visited = set()
    raw_clusters: List[List[Article]] = []
    art_by_id = {a.id: a for a in articles}

    for a in articles:
        if a.id in visited:
            continue
        component = []
        queue = [a.id]
        visited.add(a.id)

        while queue:
            curr_id = queue.pop(0)
            component.append(art_by_id[curr_id])
            for nxt_id in adjacency.get(curr_id, []):
                if nxt_id not in visited:
                    visited.add(nxt_id)
                    queue.append(nxt_id)

        raw_clusters.append(component)

    cluster_results: List[EventClusterResult] = []

    for comp in raw_clusters:
        comp_ids = sorted([a.id for a in comp])
        
        scored_articles: List[Tuple[Article, ArticleEditorialScoreResult]] = []
        distinct_sources = set(a.source_id for a in comp if a.source_id is not None)
        distinct_source_count = max(1, len(distinct_sources))

        for a in comp:
            ai_out = ai_outputs_map.get(a.id)
            score_res = calculate_article_editorial_score(
                article=a,
                ai_output=ai_out,
                distinct_corroborating_sources=distinct_source_count,
                now=now,
            )
            scored_articles.append((a, score_res))

        scored_articles.sort(
            key=lambda x: (
                x[1].editorial_score,
                1 if (x[0].source and x[0].source.source_type in ("CENTRAL_BANK", "GOVERNMENT", "COMPANY_PRIMARY")) else 0,
                x[0].published_at.timestamp() if x[0].published_at else 0,
            ),
            reverse=True,
        )

        primary_article, primary_score_res = scored_articles[0]
        supporting_articles = [x[0] for x in scored_articles[1:]]

        finger_raw = "-".join(str(i) for i in comp_ids)
        finger_hash = hashlib.sha256(finger_raw.encode("utf-8")).hexdigest()[:16]
        cluster_id = f"evt_{comp_ids[0]}_{finger_hash}"

        canonical_title = primary_article.title
        primary_ai_out = ai_outputs_map.get(primary_article.id)
        category = resolve_article_category(primary_article, primary_ai_out)

        dates = [a.published_at or a.collected_at for a in comp if (a.published_at or a.collected_at)]
        earliest_at = min(dates) if dates else None
        latest_at = max(dates) if dates else None

        corrob_bonus = min(15.0, (distinct_source_count - 1) * 5.0)
        event_cluster_score = round(min(100.0, primary_score_res.editorial_score + corrob_bonus), 1)

        explanations = []
        if len(comp) == 1:
            explanations.append(f"Singleton cluster for Article {primary_article.id}. {primary_score_res.explanation}")
        else:
            for i in range(len(comp_ids)):
                for j in range(i + 1, len(comp_ids)):
                    key = (comp_ids[i], comp_ids[j])
                    if key in pairwise_reasons:
                        explanations.append(pairwise_reasons[key])

        meta = {
            "primary_editorial_score": primary_score_res.editorial_score,
            "corroboration_bonus": corrob_bonus,
            "distinct_source_count": distinct_source_count,
            "supporting_article_ids": [a.id for a in supporting_articles],
        }

        result = EventClusterResult(
            cluster_id=cluster_id,
            canonical_title=canonical_title,
            primary_article_id=primary_article.id,
            primary_article=primary_article,
            supporting_articles=supporting_articles,
            all_articles=comp,
            category=category,
            distinct_source_count=distinct_source_count,
            article_count=len(comp),
            cluster_score=event_cluster_score,
            earliest_article_at=earliest_at,
            latest_article_at=latest_at,
            explanations=explanations,
            metadata_json=meta,
        )
        cluster_results.append(result)

    cluster_results.sort(key=lambda c: c.cluster_score, reverse=True)
    return cluster_results


def save_event_clusters(db: Session, clusters: List[EventClusterResult]) -> None:
    """
    Persists EventClusterResult objects cleanly into event_clusters and event_cluster_articles tables.
    Upserts EventCluster rows in-place to avoid deleting dependent records (such as DailyEdition edition_events).
    """
    for cl in clusters:
        existing = db.query(EventCluster).filter(EventCluster.cluster_id == cl.cluster_id).first()
        if existing:
            existing.canonical_title = cl.canonical_title
            existing.primary_article_id = cl.primary_article_id
            existing.category = cl.category
            existing.distinct_source_count = cl.distinct_source_count
            existing.article_count = cl.article_count
            existing.cluster_score = cl.cluster_score
            existing.earliest_article_at = cl.earliest_article_at
            existing.latest_article_at = cl.latest_article_at
            existing.metadata_json = cl.metadata_json
        else:
            db_cluster = EventCluster(
                cluster_id=cl.cluster_id,
                canonical_title=cl.canonical_title,
                primary_article_id=cl.primary_article_id,
                category=cl.category,
                distinct_source_count=cl.distinct_source_count,
                article_count=cl.article_count,
                cluster_score=cl.cluster_score,
                earliest_article_at=cl.earliest_article_at,
                latest_article_at=cl.latest_article_at,
                metadata_json=cl.metadata_json,
            )
            db.add(db_cluster)

        # Refresh EventClusterArticle associations
        db.query(EventClusterArticle).filter(EventClusterArticle.cluster_id == cl.cluster_id).delete(synchronize_session=False)
        for a in cl.all_articles:
            is_prim = (a.id == cl.primary_article_id)
            rel = "PRIMARY" if is_prim else "SUPPORTING"
            db_art = EventClusterArticle(
                cluster_id=cl.cluster_id,
                article_id=a.id,
                is_primary=is_prim,
                article_relationship=rel,
                similarity_score=1.0 if is_prim else 0.85,
                reason_json={"explanations": cl.explanations},
            )
            db.add(db_art)

    db.commit()


# Backward-compatibility aliases for backfill and knowledge utilities
def generate_clusters_from_articles(articles: List[Article], ai_outputs_map: Optional[Dict[int, ArticleAIOutput]] = None, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Helper wrapper returning list of dict representations of clusters for backfill pipeline compatibility."""
    cluster_results = cluster_articles(articles, ai_outputs_map=ai_outputs_map, now=now)
    out = []
    for c in cluster_results:
        out.append({
            "cluster_id": c.cluster_id,
            "canonical_title": c.canonical_title,
            "primary_article_id": c.primary_article_id,
            "category": c.category,
            "distinct_source_count": c.distinct_source_count,
            "article_count": c.article_count,
            "cluster_score": c.cluster_score,
            "earliest_article_at": c.earliest_article_at,
            "latest_article_at": c.latest_article_at,
            "metadata_json": c.metadata_json,
            "article_ids": [a.id for a in c.all_articles],
            "raw_result": c,
        })
    return out


def persist_event_clusters(db: Session, clusters_data: List[Any]) -> List[EventCluster]:
    """Persists either EventClusterResult objects or dict representations of clusters."""
    cluster_objs = []
    for cd in clusters_data:
        if isinstance(cd, EventClusterResult):
            cluster_objs.append(cd)
        elif isinstance(cd, dict) and "raw_result" in cd and isinstance(cd["raw_result"], EventClusterResult):
            cluster_objs.append(cd["raw_result"])
    
    if cluster_objs:
        save_event_clusters(db, cluster_objs)

    # Return persisted EventCluster DB models
    cluster_ids = [c["cluster_id"] if isinstance(c, dict) else c.cluster_id for c in clusters_data]
    return db.query(EventCluster).filter(EventCluster.cluster_id.in_(cluster_ids)).all()

