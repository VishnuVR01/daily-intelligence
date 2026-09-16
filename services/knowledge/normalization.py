"""
Stage 4B Entity & Type Normalization Engine.
Maps 57+ observed raw entity type strings into the frozen 10-type canonical ontology,
normalizes entity names and surface forms, and generates clean slugs.
"""
import re
import unicodedata
from typing import Optional

CANONICAL_ONTOLOGY = {
    "ORGANIZATION",
    "COMPANY",
    "GOVERNMENT_BODY",
    "CENTRAL_BANK",
    "COUNTRY",
    "REGION",
    "PERSON",
    "COMMODITY",
    "TECHNOLOGY",
    "PRODUCT",
}

# Explicit mapping table for observed raw type strings
RAW_TYPE_MAP = {
    # Company / Corporate
    "company": "COMPANY",
    "technology company": "COMPANY",
    "software company": "COMPANY",
    "technology provider": "COMPANY",
    "corporate": "COMPANY",
    "financial institution": "COMPANY",
    "type: financial institution": "COMPANY",
    "pharmaceutical company": "COMPANY",
    "media organization": "COMPANY",

    # Central Bank
    "central bank": "CENTRAL_BANK",

    # Government / Regulatory
    "government": "GOVERNMENT_BODY",
    "government body": "GOVERNMENT_BODY",
    "regulatory body": "GOVERNMENT_BODY",
    "ministry": "GOVERNMENT_BODY",
    "military organization": "GOVERNMENT_BODY",

    # Organization / Multilateral
    "organization": "ORGANIZATION",
    "organisation": "ORGANIZATION",
    "type: organization": "ORGANIZATION",
    "group": "ORGANIZATION",
    "operational group": "ORGANIZATION",
    "influence network": "ORGANIZATION",
    "influence campaign": "ORGANIZATION",
    "influence operation": "ORGANIZATION",
    "educational institution": "ORGANIZATION",

    # Country / Region / Location
    "country": "COUNTRY",
    "location": "REGION",
    "region": "REGION",
    "capital": "REGION",

    # Person / Individual
    "person": "PERSON",
    "politician": "PERSON",
    "prime minister": "PERSON",
    "governor": "PERSON",
    "ceo": "PERSON",
    "central bank executive": "PERSON",
    "central bank official": "PERSON",
    "economist": "PERSON",
    "quantum physicist": "PERSON",
    "filmmaker": "PERSON",

    # Technology
    "technology": "TECHNOLOGY",
    "framework": "TECHNOLOGY",
    "api": "TECHNOLOGY",
    "cloud service": "TECHNOLOGY",
    "service": "TECHNOLOGY",

    # Product
    "product": "PRODUCT",
    "product/platform": "PRODUCT",
    "software product": "PRODUCT",
    "model": "PRODUCT",
    "ai model": "PRODUCT",
    "artificial intelligence model": "PRODUCT",
    "benchmark": "PRODUCT",

    # Commodity
    "commodity": "COMMODITY",
}

COUNTRY_ALIAS_MAP = {
    "united states": "US",
    "us": "US",
    "u.s.": "US",
    "usa": "US",
    "united states of america": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "great britain": "GB",
    "india": "IN",
    "republic of india": "IN",
    "china": "CN",
    "prc": "CN",
    "people's republic of china": "CN",
    "japan": "JP",
    "nippon": "JP",
    "germany": "DE",
    "federal republic of germany": "DE",
    "france": "FR",
    "french republic": "FR",
    "russia": "RU",
    "russian federation": "RU",
}

COMPANY_SUFFIXES = {
    "inc", "inc.", "corp", "corp.", "corporation", "ltd", "ltd.", "limited",
    "plc", "co", "co.", "company", "group", "holdings", "llc", "sa", "ag", "nv", "se"
}


def normalize_entity_type(raw_type: str, surface_name: str = "") -> str:
    """
    Normalizes raw entity type into frozen 10-type canonical ontology.
    Defaults conservatively to 'ORGANIZATION' for unknown organizational terms or 'COMPANY'.
    """
    if not raw_type:
        return "ORGANIZATION"

    raw_clean = raw_type.strip().lower()
    if raw_clean in RAW_TYPE_MAP:
        return RAW_TYPE_MAP[raw_clean]

    # Partial keyword checks
    if "company" in raw_clean or "corp" in raw_clean:
        return "COMPANY"
    if "bank" in raw_clean:
        return "CENTRAL_BANK" if "central" in raw_clean else "COMPANY"
    if "government" in raw_clean or "ministry" in raw_clean:
        return "GOVERNMENT_BODY"
    if "person" in raw_clean or "official" in raw_clean or "executive" in raw_clean or "minister" in raw_clean:
        return "PERSON"
    if "model" in raw_clean or "product" in raw_clean:
        return "PRODUCT"
    if "tech" in raw_clean or "software" in raw_clean:
        return "TECHNOLOGY"
    if "country" in raw_clean:
        return "COUNTRY"
    if "region" in raw_clean:
        return "REGION"

    return "ORGANIZATION"


def normalize_entity_name(name: str) -> str:
    """
    Normalizes entity surface form for matching:
    Unicode normalization, lowercasing, collapsing whitespace, punctuation stripping.
    """
    if not name:
        return ""

    # Unicode NFKD decomposition
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = n.lower().strip()
    # Strip quotes & common punctuation (preserving -, &, ., +)
    n = re.sub(r"[^\w\s\-&.+]", "", n)


    words = n.split()
    if len(words) > 1 and words[-1] in COMPANY_SUFFIXES:
        words = words[:-1]

    clean_name = " ".join(words).strip()
    return clean_name if clean_name else n.strip()


def slugify_entity_name(canonical_name: str, entity_type: str) -> str:
    """Generates clean, deterministic unique slug for an entity."""
    clean_name = normalize_entity_name(canonical_name)
    s = clean_name.lower().replace("+", "-plus").replace("&", "and")
    slug_base = re.sub(r"[^\w\s\-]", "", s).strip().replace(" ", "-")
    type_base = entity_type.lower().replace("_", "-")
    return f"{slug_base}-{type_base}"



def normalize_country_code(text: str) -> Optional[str]:
    """Returns ISO 3166-1 alpha-2 country code if unambiguous alias match."""
    if not text:
        return None
    t_clean = text.strip().lower()
    return COUNTRY_ALIAS_MAP.get(t_clean)
