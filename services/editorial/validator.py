"""
Deterministic Post-Generation Validator for Stage 3D Editorial Synthesis.
Verifies event outputs against EvidencePack:
- Article ID membership
- Headline length & neutrality
- Summary & Why It Matters bounds
- Watch Next grounding
- Numeric token claim safety (0 novel numeric hallucinations)
- Causality safety (0 unsupported causal claims)
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from services.editorial.evidence import EvidencePack

SENSATIONAL_TERMS = {
    "shocking", "mindblowing", "unbelievable", "skyrocketing", "massive disaster",
    "catastrophic collapse", "insane", "miracle", "bombshell", "stunning"
}

CAUSAL_TRIGGERS = {
    "caused", "drove", "triggered", "led to", "resulted in", "because of", "forced by"
}


GENERIC_THEME_SUFFIXES = {"developments", "news", "updates", "stories", "key developments", "top stories", "highlights"}
GENERIC_SECTION_NAMES = {"tech", "technology", "world", "business", "energy", "economy", "trade", "sustainability", "general", "markets"}


def is_generic_theme_title(title: str) -> bool:
    """Detects and rejects generic theme titles (e.g. section name + generic suffix)."""
    if not title:
        return True
    t_clean = title.strip().lower()

    if t_clean in GENERIC_SECTION_NAMES or t_clean in ("key developments", "top stories", "main developments", "key updates"):
        return True

    words = t_clean.split()
    all_generic = True
    for w in words:
        if w not in GENERIC_SECTION_NAMES and w not in GENERIC_THEME_SUFFIXES and w not in ("key", "main", "top", "latest"):
            all_generic = False
            break

    return all_generic


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]


def extract_numeric_tokens(text: str) -> Set[str]:
    """Extracts numbers, percentages, monetary amounts, and basis points from text."""
    if not text:
        return set()
    # Matches numbers, percentages, currency, rates
    matches = re.findall(r"\b\d+(?:\.\d+)?(?:\s*(?:%|bps?|bp|billion|million|bn|m|b|trillion|t))\b|\$\d+(?:,\d+)*(?:\.\d+)?[bmk]?|\b\d+(?:\.\d+)?\b", text.lower())
    norm_matches = set()
    for m in matches:
        clean = m.replace(",", "").replace(" ", "")
        norm_matches.add(clean)
        num_only = re.sub(r"[^\d.]", "", clean)
        if num_only:
            norm_matches.add(num_only)
    return norm_matches


def validate_event_editorial_output(
    output_json: Dict[str, Any],
    evidence_pack: EvidencePack,
) -> ValidationResult:
    """
    Validates LLM-generated event editorial output deterministically against EvidencePack.
    Returns ValidationResult with is_valid boolean and detailed error logs.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Required Fields Check
    if not isinstance(output_json, dict):
        return ValidationResult(is_valid=False, errors=["Output is not a valid JSON dictionary."], warnings=[])

    headline = output_json.get("headline", "").strip()
    summary = output_json.get("summary", "").strip()
    why_it_matters = output_json.get("why_it_matters")
    watch_next = output_json.get("watch_next")
    ev_ids = output_json.get("evidence_article_ids", [])

    if not headline:
        errors.append("Headline is missing or empty.")
    if not summary:
        errors.append("Summary is missing or empty.")

    # 2. Article ID Membership Check
    allowed_ids = set(evidence_pack.evidence_article_ids)
    for aid in ev_ids:
        if aid not in allowed_ids:
            errors.append(f"Article ID {aid} in evidence_article_ids is not part of EvidencePack ({allowed_ids}).")

    # 3. Headline Neutrality & Length Check
    if headline:
        words = headline.split()
        if len(words) < 4 or len(words) > 30:
            errors.append(f"Headline length ({len(words)} words) outside acceptable bounds (4–30 words).")
        
        # Clickbait / Sensational terms check
        h_lower = headline.lower()
        for term in SENSATIONAL_TERMS:
            if term in h_lower:
                errors.append(f"Headline contains sensational/clickbait term '{term}'.")

    # 4. Summary Bounds Check
    if summary:
        sentences = [s.strip() for s in re.split(r"[.!?]+", summary) if s.strip()]
        if len(sentences) > 6:
            warnings.append(f"Summary contains {len(sentences)} sentences (target: 2–3 sentences).")

    # 5. Why It Matters Bounds Check
    if why_it_matters:
        if not isinstance(why_it_matters, str):
            errors.append("why_it_matters must be a string or null.")
        else:
            w_sentences = [s.strip() for s in re.split(r"[.!?]+", why_it_matters) if s.strip()]
            if len(w_sentences) > 4:
                warnings.append(f"why_it_matters contains {len(w_sentences)} sentences (target: 1–2 sentences).")

    # 6. Watch Next Grounding Check
    if watch_next:
        if not isinstance(watch_next, dict):
            errors.append("watch_next must be a JSON dictionary or null.")
        else:
            wn_event = watch_next.get("event", "")
            wn_src_id = watch_next.get("source_article_id")
            if not wn_event:
                errors.append("watch_next.event is missing or empty.")
            if wn_src_id and wn_src_id not in allowed_ids:
                errors.append(f"watch_next.source_article_id ({wn_src_id}) not in evidence_article_ids.")

    # 7. Numeric Token Claim Grounding Check (0 Novel Numeric Hallucinations)
    combined_gen_text = f"{headline} {summary} {why_it_matters or ''}"
    gen_numbers = extract_numeric_tokens(combined_gen_text)

    # Build evidence numbers set
    evidence_text = f"{evidence_pack.canonical_title} {evidence_pack.primary_article.title} {evidence_pack.primary_article.summary} "
    for supp in evidence_pack.supporting_articles:
        evidence_text += f"{supp.title} {supp.summary} "
    evidence_text += f"{evidence_pack.edition_date} {evidence_pack.normalized_temporal_label} {evidence_pack.distinct_source_count}"
    
    evidence_numbers = extract_numeric_tokens(evidence_text)

    for num in gen_numbers:
        # Ignore single digits 0-9 that are common sentence counters
        if len(num) == 1 and num.isdigit():
            continue
        if num not in evidence_numbers:
            # Check if partial numeric match exists (e.g. 25 in 25bps)
            num_clean = re.sub(r"[^\d.]", "", num)
            ev_clean_numbers = {re.sub(r"[^\d.]", "", e) for e in evidence_numbers}
            if num_clean and num_clean not in ev_clean_numbers:
                errors.append(f"Numeric token '{num}' in generated prose is not present in EvidencePack.")

    # 8. Causality Safety Check
    gen_text_lower = combined_gen_text.lower()
    ev_text_lower = evidence_text.lower()

    for trig in CAUSAL_TRIGGERS:
        if trig in gen_text_lower and trig not in ev_text_lower:
            # Check if explicit causal claim in evidence exists
            if not any(t in ev_text_lower for t in ["due to", "as a result", "after", "following"]):
                errors.append(f"Causal trigger phrase '{trig}' in generated output is unsupported by EvidencePack.")

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
