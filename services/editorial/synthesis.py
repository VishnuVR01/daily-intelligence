"""
Stage 3D Editorial Synthesis Engine (Sprint 3 Stage 3D).
Generates concise, evidence-grounded intelligence briefings using local Ollama synthesis (qwen3.5:4b),
deterministic EvidencePack context bounding, post-generation claim validation, and deterministic fallbacks.
Enforces event-level failure isolation, snapshot persistence, and published immutability.
"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import DailyEdition, EditionEvent, EventEditorialProse, EditionBrief
from services.editorial.evidence import build_evidence_pack, EvidencePack, extract_best_summary
from services.editorial.selection import EditionAuditResult, EventSelectionResult
from services.editorial.validator import validate_event_editorial_output, ValidationResult
from services.ai.ollama import OllamaService

logger = logging.getLogger("editorial_synthesis")

PROMPT_VERSION_EVENT = "editorial_event_v1"
PROMPT_VERSION_EDITION = "editorial_edition_v1"
_ollama_service = OllamaService(timeout_seconds=30)


@dataclass
class EventSynthesisResult:
    cluster_id: str
    headline: str
    summary: str
    why_it_matters: Optional[str]
    watch_next_json: Optional[Dict[str, Any]]
    evidence_article_ids: List[int]
    status: str  # SUCCESS, FALLBACK, FAILED
    model: str
    prompt_version: str
    validation: ValidationResult


@dataclass
class EditionBriefResult:
    brief_text: str
    key_themes_json: List[Dict[str, Any]]
    status: str  # SUCCESS, FALLBACK, FAILED
    model: str
    prompt_version: str


EVENT_SYNTHESIS_PROMPT_TEMPLATE = """You are an elite senior macro editorial synthesizer for a high-level executive daily briefing.
Your goal is to produce a concise, strictly factual, neutral intelligence summary for a single selected event based ONLY on the supplied EvidencePack.

STRICT EDITORIAL RULES:
1. Do NOT invent facts, numbers, dates, or causal claims not present in the EvidencePack.
2. Every headline must be factual, non-clickbait, and 8-16 words long.
3. Summary must be 2-3 concise sentences explaining WHAT happened and WHO/WHAT is involved.
4. "why_it_matters" must be 1-2 concise sentences directly supported by evidence, or null if no clear significance is documented.
5. "watch_next" is OPTIONAL. Only supply a watch_next JSON object if the evidence explicitly states a scheduled future date/event (e.g. upcoming central bank meeting, earnings date). Otherwise null.
6. Do NOT use sensational words (e.g. "shocking", "catastrophic", "mindblowing").

EVIDENCE PACK JSON:
{evidence_json}

Respond ONLY with a valid JSON object matching this exact schema:
{{
  "event_cluster_id": "{cluster_id}",
  "headline": "Concise Factual Headline",
  "summary": "First sentence. Second sentence.",
  "why_it_matters": "Directly evidenced significance or null",
  "watch_next": null,
  "evidence_article_ids": {article_ids_json}
}}
"""


EDITION_BRIEF_PROMPT_TEMPLATE = """You are an elite senior macro editorial synthesizer writing the Morning Briefing for Daily Intelligence.
Synthesize an edition brief and key themes based ONLY on the provided selected event summaries and market context.

STRICT RULES:
1. "brief_text" must be approximately 100-180 words summarizing the most important developments across sectors.
2. "key_themes" must contain 3-5 themes. Each theme must have a title, 1-sentence description, and supporting event_cluster_ids (at least 2 events per theme).
3. Do NOT invent causality between unrelated events.
4. Do NOT introduce new events not present in the inputs.

SELECTED EVENT SUMMARIES:
{event_summaries_json}

STRUCTURED MARKET CONTEXT:
{market_context_str}

Respond ONLY with a valid JSON object matching this schema:
{{
  "brief_text": "Executive summary paragraph...",
  "key_themes": [
    {{
      "title": "Theme Title",
      "description": "One sentence description.",
      "event_cluster_ids": ["evt_1...", "evt_2..."]
    }}
  ]
}}
"""


def synthesize_event_editorial(
    db: Session,
    event_selection: EventSelectionResult,
    edition_date: date,
    model: str = "qwen3.5:4b",
    use_ollama: bool = True,
) -> EventSynthesisResult:
    """
    Synthesizes editorial prose for a single EventSelectionResult.
    Enforces EvidencePack context bounding, structured validation, and deterministic fallbacks.
    """
    evidence_pack = build_evidence_pack(event_selection, edition_date)
    evidence_json_str = json.dumps(evidence_pack.to_dict(), indent=2)

    prompt = EVENT_SYNTHESIS_PROMPT_TEMPLATE.format(
        evidence_json=evidence_json_str,
        cluster_id=evidence_pack.event_cluster_id,
        article_ids_json=json.dumps(evidence_pack.evidence_article_ids),
    )

    if use_ollama:
        try:
            output_json = _ollama_service.chat_json(
                messages=[{"role": "user", "content": prompt}],
                model_override=model,
                options={"temperature": 0.1},
            )
            if output_json and isinstance(output_json, dict):
                val_res = validate_event_editorial_output(output_json, evidence_pack)
                if val_res.is_valid:
                    return EventSynthesisResult(
                        cluster_id=evidence_pack.event_cluster_id,
                        headline=output_json.get("headline", evidence_pack.canonical_title),
                        summary=output_json.get("summary", extract_best_summary(event_selection.primary_article)),
                        why_it_matters=output_json.get("why_it_matters"),
                        watch_next_json=output_json.get("watch_next"),
                        evidence_article_ids=output_json.get("evidence_article_ids", evidence_pack.evidence_article_ids),
                        status="SUCCESS",
                        model=model,
                        prompt_version=PROMPT_VERSION_EVENT,
                        validation=val_res,
                    )
                else:
                    logger.warning(f"Ollama output failed validation for {evidence_pack.event_cluster_id}: {val_res.errors}")
        except Exception as e:
            logger.warning(f"Ollama synthesis failed or timed out for {evidence_pack.event_cluster_id}: {e}")

    # Deterministic Fallback
    fallback_val = ValidationResult(is_valid=True, errors=[], warnings=["Used deterministic fallback."])
    return EventSynthesisResult(
        cluster_id=evidence_pack.event_cluster_id,
        headline=evidence_pack.canonical_title,
        summary=extract_best_summary(event_selection.primary_article),
        why_it_matters=None,
        watch_next_json=None,
        evidence_article_ids=evidence_pack.evidence_article_ids,
        status="FALLBACK",
        model=model,
        prompt_version=PROMPT_VERSION_EVENT,
        validation=fallback_val,
    )


def synthesize_edition_brief_and_themes(
    db: Session,
    edition_audit: EditionAuditResult,
    event_prose_results: List[EventSynthesisResult],
    model: str = "qwen3.5:4b",
    use_ollama: bool = True,
) -> EditionBriefResult:
    """
    Synthesizes Edition Brief (Morning Brief) and Key Themes using ONLY selected event outputs and structured market context.
    """
    event_summaries = [
        {
            "cluster_id": ev.cluster_id,
            "headline": ev.headline,
            "summary": ev.summary,
            "section": next((s.section for s in edition_audit.selected_events if s.cluster_id == ev.cluster_id), "WORLD"),
        }
        for ev in event_prose_results
    ]
    event_summaries_str = json.dumps(event_summaries, indent=2)

    # Market context from structured market service
    market_summary = {}
    try:
        from services.markets import get_market_service
        ms = get_market_service()
        if hasattr(ms, "_cached_snapshots") and ms._cached_snapshots:
            for snap in ms._cached_snapshots:
                market_summary[snap.symbol] = {
                    "name": snap.display_name,
                    "price": snap.latest_close,
                    "change": snap.change_value,
                    "change_percent": snap.change_percent,
                    "direction": snap.direction.value if hasattr(snap.direction, "value") else str(snap.direction),
                }
    except Exception as m_err:
        logger.warning(f"Failed to fetch market snapshot for synthesis: {m_err}")
        market_summary = {}

    market_str = json.dumps(market_summary, indent=2)

    prompt = EDITION_BRIEF_PROMPT_TEMPLATE.format(
        event_summaries_json=event_summaries_str,
        market_context_str=market_str,
    )

    if use_ollama and len(event_prose_results) > 0:
        try:
            output_json = _ollama_service.chat_json(
                messages=[{"role": "user", "content": prompt}],
                model_override=model,
                options={"temperature": 0.1},
            )
            if output_json and isinstance(output_json, dict):
                brief_text = output_json.get("brief_text", "").strip()
                key_themes = output_json.get("key_themes", [])
                if brief_text and isinstance(key_themes, list):
                    return EditionBriefResult(
                        brief_text=brief_text,
                        key_themes_json=key_themes,
                        status="SUCCESS",
                        model=model,
                        prompt_version=PROMPT_VERSION_EDITION,
                    )
        except Exception as e:
            logger.warning(f"Ollama edition brief synthesis failed: {e}")

    # Fallback Brief Generation
    sec_counts = edition_audit.audit_json.get("section_counts", {})
    sec_summary_str = ", ".join(f"{k}: {v}" for k, v in sec_counts.items()) if sec_counts else "multiple sectors"
    fallback_brief = (
        f"This Daily Edition presents {len(event_prose_results)} key macro developments for {edition_audit.edition_date}. "
        f"Coverage spans {sec_summary_str}. All featured events have been verified across trusted primary sources."
    )

    # Fallback Themes grouped by section
    themes_by_sec: Dict[str, List[str]] = {}
    for ev in event_prose_results:
        sec = next((s.section for s in edition_audit.selected_events if s.cluster_id == ev.cluster_id), "WORLD")
        themes_by_sec.setdefault(sec, []).append(ev.cluster_id)

    fallback_themes = []
    for sec, c_ids in themes_by_sec.items():
        fallback_themes.append({
            "title": f"{sec.title()} Key Developments",
            "description": f"Featured developments in {sec.title()} covering key market movements.",
            "event_cluster_ids": c_ids,
        })

    return EditionBriefResult(
        brief_text=fallback_brief,
        key_themes_json=fallback_themes,
        status="FALLBACK",
        model=model,
        prompt_version=PROMPT_VERSION_EDITION,
    )


def save_editorial_synthesis(
    db: Session,
    edition: DailyEdition,
    event_prose_results: List[EventSynthesisResult],
    edition_brief_result: EditionBriefResult,
) -> None:
    """
    Persists snapshotted editorial prose and brief into DB.
    Immutability guard: raises ValueError if edition is PUBLISHED.
    """
    if edition.status == "PUBLISHED":
        raise ValueError(f"Edition {edition.id} ({edition.edition_date}) is PUBLISHED and cannot be overwritten.")

    # 1. Clear existing prose records for this edition
    ee_ids = [ee.id for ee in edition.edition_events]
    if ee_ids:
        db.query(EventEditorialProse).filter(EventEditorialProse.edition_event_id.in_(ee_ids)).delete(synchronize_session=False)

    # 2. Clear existing brief for this edition
    db.query(EditionBrief).filter(EditionBrief.edition_id == edition.id).delete(synchronize_session=False)

    # Map cluster_id to EditionEvent object
    ee_map = {ee.event_cluster_id: ee for ee in edition.edition_events}

    # 3. Add EventEditorialProse records
    for prose in event_prose_results:
        ee = ee_map.get(prose.cluster_id)
        if not ee:
            continue

        db_prose = EventEditorialProse(
            edition_event_id=ee.id,
            event_cluster_id=prose.cluster_id,
            headline=prose.headline,
            summary=prose.summary,
            why_it_matters=prose.why_it_matters,
            watch_next_json=prose.watch_next_json,
            evidence_article_ids=prose.evidence_article_ids,
            status=prose.status,
            model=prose.model,
            prompt_version=prose.prompt_version,
            generated_at=datetime.now(timezone.utc),
        )
        db.add(db_prose)

    # 4. Add EditionBrief record
    db_brief = EditionBrief(
        edition_id=edition.id,
        brief_text=edition_brief_result.brief_text,
        key_themes_json=edition_brief_result.key_themes_json,
        model=edition_brief_result.model,
        prompt_version=edition_brief_result.prompt_version,
        status=edition_brief_result.status,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(db_brief)

    db.commit()
    db.refresh(edition)
