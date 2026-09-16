"""
Deterministic Query Expansion Module (v1.1)
Provides transparent, version-controlled, domain-specific query expansion
for Daily Intelligence historical archive retrieval.
Grounded in archive vocabulary without LLM rewriters or vector dependencies.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Set, Tuple


@dataclass
class ExpandedQueryResult:
    original_query: str
    clean_query: str
    original_tokens: List[str]
    expanded_tokens: List[str]
    triggered_rules: List[str]
    fts_expression: str


# Transparent, conservative domain expansion dictionary
DOMAIN_EXPANSION_MAP: Dict[str, List[str]] = {
    "sustainability": ["decarbonization", "carbon", "emissions", "environmental", "lower-carbon", "clean"],
    "sustainable": ["decarbonization", "carbon", "emissions", "environmental", "lower-carbon"],
    "renewable": ["biofuel", "biofuels", "solar", "wind", "ethanol", "clean energy"],
    "renewable energy": ["biofuel", "biofuels", "solar", "wind", "ethanol", "clean energy"],
    "grain": ["wheat", "corn", "maize", "soybean", "rice", "crop"],
    "grains": ["wheat", "corn", "maize", "soybean", "rice", "crops"],
    "agriculture": ["farming", "crop", "crops", "feedstock", "agricultural"],
    "agricultural": ["farming", "crop", "crops", "feedstock", "agriculture"],
    "supply chain": ["logistics", "transport", "shipping", "freight", "distribution"],
    "supply chains": ["logistics", "transport", "shipping", "freight", "distribution"],
    "ai": ["artificial intelligence", "machine learning", "generative ai", "autonomous", "digital twin"],
    "artificial intelligence": ["machine learning", "generative ai", "autonomous", "digital twin"],
    "geopolitics": ["sanctions", "diplomacy", "summit", "treaty", "foreign policy"],
    "geopolitical": ["sanctions", "diplomacy", "summit", "treaty", "foreign policy"],
}


STOP_WORDS: Set[str] = {
    "what", "did", "say", "about", "the", "a", "an", "is", "are", "in", "on", "of", "for", "to", "how", "why", "who", "where", "which", "with",
    "today", "yesterday", "this", "week", "month", "past", "last", "days", "happened", "latest", "news", "show", "tell", "me", "documented", "across", "sources"
}


def expand_query(query: str) -> ExpandedQueryResult:
    """
    Deterministically expands a user research query using the domain expansion map.
    Preserves original query terms and returns structured expansion metadata.
    """
    clean_q = (query or "").strip()
    if not clean_q:
        return ExpandedQueryResult(
            original_query=query,
            clean_query="",
            original_tokens=[],
            expanded_tokens=[],
            triggered_rules=[],
            fts_expression="",
        )

    raw_tokens = [t.lower().strip() for t in re.findall(r"\w+", clean_q) if t.strip()]
    original_tokens = [t for t in raw_tokens if t not in STOP_WORDS and len(t) > 1]

    clean_lower = clean_q.lower()
    triggered_rules: List[str] = []
    expanded_term_set: Set[str] = set()

    # 1. Multi-word phrase matching
    for phrase, expansions in DOMAIN_EXPANSION_MAP.items():
        if " " in phrase and phrase in clean_lower:
            triggered_rules.append(f"PHRASE:'{phrase}'")
            for exp in expansions:
                if exp.lower() not in original_tokens and exp.lower() != clean_lower:
                    expanded_term_set.add(exp.lower())

    # 2. Single token matching
    for tok in original_tokens:
        if tok in DOMAIN_EXPANSION_MAP:
            triggered_rules.append(f"TOKEN:'{tok}'")
            for exp in DOMAIN_EXPANSION_MAP[tok]:
                if exp.lower() not in original_tokens and exp.lower() != clean_lower:
                    expanded_term_set.add(exp.lower())

    expanded_tokens = sorted(list(expanded_term_set))

    # FTS expression construction
    fts_parts = []
    if original_tokens:
        fts_parts.append("(" + " & ".join(original_tokens) + ")")
    if expanded_tokens:
        # Clean multi-word expanded tokens for FTS OR query
        clean_exp_tokens = [t.replace(" ", " & ") if " " in t else t for t in expanded_tokens]
        fts_parts.append("(" + " | ".join(clean_exp_tokens) + ")")

    fts_expression = " | ".join(fts_parts) if fts_parts else clean_q

    return ExpandedQueryResult(
        original_query=query,
        clean_query=clean_q,
        original_tokens=original_tokens,
        expanded_tokens=expanded_tokens,
        triggered_rules=list(dict.fromkeys(triggered_rules)),
        fts_expression=fts_expression,
    )
