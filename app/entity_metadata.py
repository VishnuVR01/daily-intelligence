from typing import Any, Dict, List, Optional

COUNTRY_NAMES: Dict[str, str] = {
    "US": "United States",
    "GB": "United Kingdom",
    "CN": "China",
    "BR": "Brazil",
    "FR": "France",
    "ZA": "South Africa",
    "CH": "Switzerland",
    "NL": "Netherlands",
    "IN": "India",
    "JP": "Japan",
    "DE": "Germany",
    "RU": "Russia",
    "EG": "Egypt",
    "ET": "Ethiopia",
    "IR": "Iran",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "CA": "Canada",
    "IT": "Italy",
    "AU": "Australia",
    "KR": "South Korea",
    "SG": "Singapore",
    "ID": "Indonesia",
    "AR": "Argentina",
    "MX": "Mexico",
    "TR": "Turkey",
    "EU": "European Union",
    "QA": "Qatar",
    "FI": "Finland",
}

COUNTRY_FLAGS: Dict[str, str] = {
    "US": "🇺🇸",
    "GB": "🇬🇧",
    "CN": "🇨🇳",
    "BR": "🇧🇷",
    "FR": "🇫🇷",
    "ZA": "🇿🇦",
    "CH": "🇨🇭",
    "NL": "🇳🇱",
    "IN": "🇮🇳",
    "JP": "🇯🇵",
    "DE": "🇩🇪",
    "RU": "🇷🇺",
    "EG": "🇪🇬",
    "ET": "🇪🇹",
    "IR": "🇮🇷",
    "AE": "🇦🇪",
    "SA": "🇸🇦",
    "CA": "🇨🇦",
    "IT": "🇮🇹",
    "AU": "🇦🇺",
    "KR": "🇰🇷",
    "SG": "🇸🇬",
    "ID": "🇮🇩",
    "AR": "🇦🇷",
    "MX": "🇲🇽",
    "TR": "🇹🇷",
    "EU": "🇪🇺",
    "QA": "🇶🇦",
    "FI": "🇫🇮",
}


class EntityMetadata:
    """
    Extensible entity metadata model representing countries, companies,
    universities, consulting firms, governments, central banks, mining, and industry.
    """

    def __init__(
        self,
        name: str,
        entity_type: str,
        country_code: Optional[str] = None,
        logo_url: Optional[str] = None,
        fallback_icon: Optional[str] = None,
    ):
        self.name = name
        self.entity_type = entity_type
        self.country_code = (country_code or "").upper() if country_code else None
        self.logo_url = logo_url
        self.fallback_icon = fallback_icon or self.default_icon_for_type(entity_type)

    @staticmethod
    def default_icon_for_type(entity_type: str) -> str:
        icons = {
            "country": "🌐",
            "company": "🏢",
            "university": "🎓",
            "consulting_firm": "💼",
            "consulting": "💼",
            "government": "🏛️",
            "central_bank": "🏦",
            "institution": "🏛️",
            "research": "🔬",
            "open_source": "⚡",
            "industrial": "🏭",
            "mining": "⛏",
            "shipping": "🚢",
            "construction": "🏗",
        }
        return icons.get(entity_type.lower() if entity_type else "", "📰")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "country_code": self.country_code,
            "country_name": COUNTRY_NAMES.get(self.country_code, self.country_code) if self.country_code else None,
            "country_flag": COUNTRY_FLAGS.get(self.country_code, "🌐") if self.country_code else None,
            "logo_url": self.logo_url,
            "fallback_icon": self.fallback_icon,
        }


def get_country_info(country_code: str) -> Dict[str, str]:
    """Return country code, full country name, and flag emoji."""
    code = (country_code or "").upper()
    return {
        "code": code,
        "name": COUNTRY_NAMES.get(code, code),
        "flag": COUNTRY_FLAGS.get(code, "🌐"),
    }


def format_country_badges(countries: List[str], max_visible: int = 3) -> Dict[str, Any]:
    """
    Formats a list of country codes into visible country objects
    and an overflow count (+N) with tooltip text.
    """
    cleaned = [c.upper() for c in (countries or []) if c]
    visible_codes = cleaned[:max_visible]
    overflow_codes = cleaned[max_visible:]

    visible_items = [get_country_info(c) for c in visible_codes]
    overflow_names = [COUNTRY_NAMES.get(c, c) for c in overflow_codes]

    return {
        "visible": visible_items,
        "overflow_count": len(overflow_codes),
        "overflow_names": ", ".join(overflow_names) if overflow_names else "",
        "total_count": len(cleaned),
    }


def get_source_family_info(family: str) -> Dict[str, str]:
    """
    Returns display metadata (label, icon, css_class) for a given source family.
    Supported families: news, government, central_bank, consulting, university, research, industry, open_source.
    """
    family_map: Dict[str, Dict[str, str]] = {
        "news": {"label": "News & Media", "icon": "📰", "class": "family-news"},
        "government": {"label": "Government & Multilateral", "icon": "🏛️", "class": "family-gov"},
        "central_bank": {"label": "Central Bank", "icon": "🏦", "class": "family-bank"},
        "consulting": {"label": "Consulting", "icon": "💼", "class": "family-consulting"},
        "university": {"label": "University & Academia", "icon": "🎓", "class": "family-university"},
        "research": {"label": "Research Institute", "icon": "🔬", "class": "family-research"},
        "industry": {"label": "Industry & Tech", "icon": "🏢", "class": "family-industry"},
        "open_source": {"label": "Open Source", "icon": "⚡", "class": "family-open-source"},
    }
    key = (family or "news").lower()
    return family_map.get(
        key,
        {"label": (family or "News").capitalize(), "icon": "📰", "class": "family-news"},
    )


def get_trust_tier_info(tier: str) -> Dict[str, Any]:
    """
    Returns display metadata for trust tiers: primary, institutional, open_source_signal, social_signal, state_affiliated.
    """
    tier_map: Dict[str, Dict[str, Any]] = {
        "primary": {"label": "Primary", "class": "trust-primary", "weight": 1},
        "institutional": {"label": "Institutional", "class": "trust-institutional", "weight": 2},
        "open_source_signal": {"label": "Open Source Signal", "class": "trust-open-source", "weight": 3},
        "social_signal": {"label": "Social Signal", "class": "trust-social", "weight": 4},
        "state_affiliated": {"label": "State-Affiliated", "class": "trust-state-affiliated", "weight": 5},
    }
    key = (tier or "primary").lower()
    return tier_map.get(
        key,
        {"label": (tier or "Primary").capitalize(), "class": "trust-primary", "weight": 1},
    )
