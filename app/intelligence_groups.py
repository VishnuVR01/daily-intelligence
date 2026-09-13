"""
Centralized Intelligence Group / Lens Configuration & Helper.
Snapshot Date: September 2026

Supported Lenses:
- All World (global)
- BRICS (geopolitical & economic grouping)
- G7 (economic grouping)
- G20 (economic grouping)
- EU (regional organization)
- OPEC (energy organization)
- GCC (regional organization)
- ASEAN (regional organization)
- Nordics (geographic region)
- Baltics (geographic region)
"""

from typing import Any, Dict, List, Optional

INTELLIGENCE_GROUPS: Dict[str, Dict[str, Any]] = {
    "world": {
        "key": "world",
        "name": "All World",
        "label": "All World",
        "type": "global",
        "description": "Global International News Environment",
        "country_codes": [],
    },
    "brics": {
        "key": "brics",
        "name": "BRICS",
        "label": "BRICS",
        "type": "geopolitical_economic",
        "description": "BRICS Nations & Partner Economies",
        "country_codes": ["BR", "RU", "IN", "CN", "ZA", "EG", "ET", "IR", "AE", "SA"],
    },
    "g7": {
        "key": "g7",
        "name": "G7",
        "label": "G7",
        "type": "economic_grouping",
        "description": "Group of Seven Industrialized Economies",
        "country_codes": ["US", "GB", "DE", "FR", "IT", "JP", "CA", "EU"],
    },
    "g20": {
        "key": "g20",
        "name": "G20",
        "label": "G20",
        "type": "economic_grouping",
        "description": "Group of Twenty Major Economies",
        "country_codes": [
            "US", "GB", "DE", "FR", "IT", "JP", "CA", "BR", "RU", "IN",
            "CN", "ZA", "MX", "ID", "TR", "AR", "SA", "KR", "AU", "EU"
        ],
    },
    "eu": {
        "key": "eu",
        "name": "European Union",
        "label": "EU",
        "type": "regional_organization",
        "description": "European Union Member States",
        "country_codes": [
            "DE", "FR", "IT", "NL", "BE", "ES", "PT", "AT", "SE", "FI",
            "DK", "IE", "GR", "PL", "CZ", "HU", "SK", "RO", "BG", "HR",
            "SI", "LT", "LV", "EE", "CY", "MT", "LU", "EU"
        ],
    },
    "opec": {
        "key": "opec",
        "name": "OPEC",
        "label": "OPEC",
        "type": "energy_organization",
        "description": "Organization of the Petroleum Exporting Countries",
        "country_codes": ["SA", "AE", "IR", "IQ", "KW", "DZ", "LY", "NG", "CG", "GA", "GQ"],
    },
    "gcc": {
        "key": "gcc",
        "name": "GCC",
        "label": "GCC",
        "type": "regional_organization",
        "description": "Gulf Cooperation Council",
        "country_codes": ["SA", "AE", "QA", "KW", "OM", "BH"],
    },
    "asean": {
        "key": "asean",
        "name": "ASEAN",
        "label": "ASEAN",
        "type": "regional_organization",
        "description": "Association of Southeast Asian Nations",
        "country_codes": ["BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN"],
    },
    "nordics": {
        "key": "nordics",
        "name": "Nordics",
        "label": "Nordics",
        "type": "geographic_region",
        "description": "Nordic Countries (Denmark, Finland, Iceland, Norway, Sweden)",
        "country_codes": ["DK", "FI", "IS", "NO", "SE"],
    },
    "baltics": {
        "key": "baltics",
        "name": "Baltics",
        "label": "Baltics",
        "type": "geographic_region",
        "description": "Baltic States (Estonia, Latvia, Lithuania)",
        "country_codes": ["EE", "LV", "LT"],
    },
}


def get_group_info(group_key: Optional[str]) -> Dict[str, Any]:
    """Return dictionary info for a given lens key, defaulting to 'world'."""
    key = (group_key or "world").lower().strip()
    return INTELLIGENCE_GROUPS.get(key, INTELLIGENCE_GROUPS["world"])


def get_group_country_codes(group_key: Optional[str]) -> List[str]:
    """Return list of uppercase ISO country codes for a group."""
    info = get_group_info(group_key)
    return info.get("country_codes", [])


def get_all_lens_chips() -> List[Dict[str, Any]]:
    """Return ordered list of lens dictionaries for UI chip rendering."""
    return list(INTELLIGENCE_GROUPS.values())
