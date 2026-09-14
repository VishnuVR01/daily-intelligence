"""
Local Grounded RAG Engine Service (v1)
Performs evidence retrieval, compact context preparation, strictly grounded Ollama prompting,
and real citation mapping over the Daily Intelligence archive.
Snapshot Date: September 2026
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article
from repositories.articles import get_article_ai_output, search_articles_v1
from services.ai.ollama import OllamaService

logger = logging.getLogger(__name__)


# ==============================================================================
# RAG SERVICE IMPLEMENTATION
# ==============================================================================

def ask_archive(
    db: Session,
    question: str,
    filters: Optional[Dict[str, Any]] = None,
    max_evidence_count: int = 10,
) -> Dict[str, Any]:
    """
    Execute grounded RAG over historical intelligence archive:
    1. Validate input question
    2. Retrieve evidence records via search_articles_v1
    3. Construct compact context budget
    4. Prompt Ollama with strict boundary rules
    5. Return structured ArchiveAnswer with real traceable citations
    """
    clean_q = (question or "").strip()
    if not clean_q:
        return {
            "question": question,
            "answer": "Please enter a specific research question to query the intelligence archive.",
            "confidence": "low",
            "evidence_count": 0,
            "citations": [],
            "key_themes": [],
            "date_range": None,
            "insufficient_evidence": True,
        }

    filters = filters or {}
    try:
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        categories = filters.get("categories")
        countries = filters.get("countries")
        sources = filters.get("sources")
        min_importance = filters.get("min_importance")
        min_relevance = filters.get("min_relevance")
        relevant_only = filters.get("relevant_only", True)

        # 1. Retrieve Evidence Records via Search
        search_res = search_articles_v1(
            db,
            query=clean_q,
            date_from=date_from,
            date_to=date_to,
            categories=categories,
            countries=countries,
            sources=sources,
            min_importance=min_importance,
            min_relevance=min_relevance,
            relevant_only=relevant_only,
            limit=max_evidence_count,
            offset=0,
        )

        evidence_articles: List[Article] = search_res.get("articles", [])

        if not evidence_articles:
            return {
                "question": clean_q,
                "answer": "No matching intelligence records were found in the archive for this query. Try broadening search keywords or removing category/date filters.",
                "confidence": "low",
                "evidence_count": 0,
                "citations": [],
                "key_themes": [],
                "date_range": None,
                "insufficient_evidence": True,
            }

        # 2. Prepare Compact Context Budget
        context_records = []
        citations_map = []
        dates_found = []

        for idx, art in enumerate(evidence_articles, 1):
            ai_out = get_article_ai_output(art)
            pub_dt = art.published_at or art.collected_at
            pub_str = pub_dt.strftime("%Y-%m-%d") if pub_dt else "Unknown Date"
            if pub_dt:
                dates_found.append(pub_dt)

            summary_text = ai_out.summary if (ai_out and ai_out.summary) else (art.raw_summary or art.title)
            src_name = art.source.name if art.source else "RSS Feed"
            cat_name = (ai_out.primary_category if ai_out else art.primary_category) or "World"

            topics = []
            entities = []
            if ai_out and isinstance(ai_out.output_json, dict):
                topics = [t.strip().lstrip("#") for t in ai_out.output_json.get("topics", []) if isinstance(t, str)][:4]
                raw_ents = ai_out.output_json.get("entities", [])
                for e in raw_ents[:4]:
                    if isinstance(e, dict) and e.get("name"):
                        entities.append(e["name"])
                    elif isinstance(e, str):
                        entities.append(e)

            context_records.append({
                "record_number": idx,
                "article_id": art.id,
                "headline": art.title,
                "source": src_name,
                "published_date": pub_str,
                "category": cat_name,
                "ai_summary": summary_text,
                "topics": topics,
                "entities": entities,
            })

            citations_map.append({
                "citation_number": idx,
                "article_id": art.id,
                "headline": art.title,
                "source_name": src_name,
                "publication_date": pub_str,
                "canonical_url": art.canonical_url,
                "category": cat_name,
            })

        date_range_str = None
        if dates_found:
            min_d = min(dates_found).strftime("%b %d, %Y")
            max_d = max(dates_found).strftime("%b %d, %Y")
            date_range_str = f"{min_d} – {max_d}" if min_d != max_d else min_d

        # 3. Grounded Prompting for Ollama
        system_prompt = (
            "You are the Daily Intelligence Archive Research Assistant.\n"
            "Your task is to answer the user's research question ONLY using the supplied archive evidence records below.\n\n"
            "STRICT GROUNDING RULES:\n"
            "1. Base all facts, numbers, dates, company names, and developments EXCLUSIVELY on the provided evidence.\n"
            "2. NEVER invent or extrapolate unmentioned events, statistics, quotes, or geopolitical facts.\n"
            "3. For every substantive claim in your answer, cite the corresponding evidence record number in brackets e.g. [1], [2].\n"
            "4. If the evidence is insufficient or irrelevant to answer the question, explicitly state that evidence is insufficient and set insufficient_evidence to true.\n"
            "5. Return strictly a JSON object with keys: answer (string), key_themes (list of strings), confidence (high/medium/low), insufficient_evidence (boolean), cited_record_numbers (list of integers).\n"
        )

        user_prompt = (
            f"RESEARCH QUESTION: {clean_q}\n\n"
            f"EVIDENCE RECORDS:\n{json.dumps(context_records, indent=2)}\n\n"
            "Provide your grounded answer in JSON."
        )

        # 4. Invoke Ollama or Deterministic Fallback
        ollama_res = _call_ollama_rag(system_prompt, user_prompt)

        if ollama_res and isinstance(ollama_res, dict):
            answer_text = ollama_res.get("answer", "")
            key_themes = ollama_res.get("key_themes", [])
            confidence = ollama_res.get("confidence", "medium")
            insufficient = bool(ollama_res.get("insufficient_evidence", False))
            cited_nums = ollama_res.get("cited_record_numbers", [])

            # Filter citations to only those actually referenced
            if cited_nums and isinstance(cited_nums, list):
                final_citations = [c for c in citations_map if c["citation_number"] in cited_nums]
                if not final_citations:
                    final_citations = citations_map
            else:
                final_citations = citations_map
        else:
            # Fallback summary answer when Ollama is unavailable
            fallback_bullets = []
            all_themes = set()
            for c in context_records[:5]:
                fallback_bullets.append(f"[{c['record_number']}] {c['source']}: {c['ai_summary']}")
                for t in c.get("topics", []):
                    all_themes.add(t)

            answer_text = (
                f"Based on {len(context_records)} matching archive record(s):\n\n"
                + "\n\n".join(fallback_bullets)
            )
            key_themes = list(all_themes)[:5]
            confidence = "medium"
            insufficient = False
            final_citations = citations_map

        total_chars = sum(len(c.get("ai_summary", "")) + len(c.get("raw_summary", "")) for c in context_records)
        return {
            "question": clean_q,
            "answer": answer_text,
            "confidence": confidence,
            "evidence_count": len(evidence_articles),
            "citations": final_citations,
            "key_themes": key_themes,
            "date_range": date_range_str,
            "insufficient_evidence": insufficient,
            "context_meta": {
                "article_count": len(evidence_articles),
                "total_chars": total_chars,
            },
        }
    except Exception as exc:
        logger.error(f"Unexpected error in ask_archive: {exc}")
        return {
            "question": clean_q,
            "answer": "Archive research is temporarily unavailable.",
            "confidence": "low",
            "evidence_count": 0,
            "citations": [],
            "key_themes": [],
            "date_range": None,
            "insufficient_evidence": True,
        }


def _call_ollama_rag(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Invoke Ollama API chat completion for RAG using the unified OllamaService."""
    settings = get_settings()
    if not getattr(settings, "ollama_enabled", True):
        return None

    ollama_svc = OllamaService()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return ollama_svc.chat_json(messages, options={"temperature": 0.1})
