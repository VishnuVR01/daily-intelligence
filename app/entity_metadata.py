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
    "DK": "Denmark",
    "IS": "Iceland",
    "NO": "Norway",
    "SE": "Sweden",
    "EE": "Estonia",
    "LV": "Latvia",
    "LT": "Lithuania",
    "BN": "Brunei",
    "KH": "Cambodia",
    "LA": "Laos",
    "MY": "Malaysia",
    "MM": "Myanmar",
    "PH": "Philippines",
    "TH": "Thailand",
    "TL": "Timor-Leste",
    "VN": "Vietnam",
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
    "DK": "🇩🇰",
    "IS": "🇮🇸",
    "NO": "🇳🇴",
    "SE": "🇸🇪",
    "EE": "🇪🇪",
    "LV": "🇱🇻",
    "LT": "🇱🇹",
    "BN": "🇧🇳",
    "KH": "🇰🇭",
    "LA": "🇱🇦",
    "MY": "🇲🇾",
    "MM": "🇲🇲",
    "PH": "🇵🇭",
    "TH": "🇹🇭",
    "TL": "🇹🇱",
    "VN": "🇻🇳",
}

# Complete ISO 3166-1 Numeric (3-digit zero-padded string) to ISO 3166-1 Alpha-2 mapping
ISO_NUMERIC_TO_ALPHA2: Dict[str, str] = {
    "004": "AF", "008": "AL", "012": "DZ", "016": "AS", "020": "AD", "024": "AO", "028": "AG", "032": "AR",
    "051": "AM", "036": "AU", "040": "AT", "031": "AZ", "044": "BS", "048": "BH", "050": "BD", "052": "BB",
    "112": "BY", "056": "BE", "084": "BZ", "204": "BJ", "060": "BM", "064": "BT", "068": "BO", "070": "BA",
    "072": "BW", "076": "BR", "096": "BN", "100": "BG", "854": "BF", "108": "BI", "116": "KH", "120": "CM",
    "124": "CA", "132": "CV", "140": "CF", "148": "TD", "152": "CL", "156": "CN", "170": "CO", "174": "KM",
    "178": "CG", "180": "CD", "188": "CR", "384": "CI", "191": "HR", "192": "CU", "196": "CY", "203": "CZ",
    "208": "DK", "262": "DJ", "212": "DM", "214": "DO", "218": "EC", "818": "EG", "222": "SV", "226": "GQ",
    "232": "ER", "233": "EE", "231": "ET", "242": "FJ", "246": "FI", "250": "FR", "266": "GA", "270": "GM",
    "268": "GE", "276": "DE", "288": "GH", "300": "GR", "308": "GD", "320": "GT", "324": "GN", "624": "GW",
    "328": "GY", "332": "HT", "340": "HN", "348": "HU", "352": "IS", "356": "IN", "360": "ID", "364": "IR",
    "368": "IQ", "372": "IE", "376": "IL", "380": "IT", "388": "JM", "392": "JP", "400": "JO", "398": "KZ",
    "404": "KE", "296": "KI", "408": "KP", "410": "KR", "414": "KW", "417": "KG", "418": "LA", "428": "LV",
    "422": "LB", "426": "LS", "430": "LR", "434": "LY", "438": "LI", "440": "LT", "442": "LU", "807": "MK",
    "450": "MG", "454": "MW", "458": "MY", "462": "MV", "466": "ML", "470": "MT", "584": "MH", "478": "MR",
    "480": "MU", "484": "MX", "583": "FM", "498": "MD", "492": "MC", "496": "MN", "499": "ME", "504": "MA",
    "508": "MZ", "104": "MM", "516": "NA", "520": "NR", "524": "NP", "528": "NL", "554": "NZ", "558": "NI",
    "562": "NE", "566": "NG", "578": "NO", "512": "OM", "586": "PK", "585": "PW", "591": "PA", "598": "PG",
    "600": "PY", "604": "PE", "608": "PH", "616": "PL", "620": "PT", "634": "QA", "642": "RO", "643": "RU",
    "646": "RW", "659": "KN", "662": "LC", "670": "VC", "882": "WS", "674": "SM", "678": "ST", "682": "SA",
    "686": "SN", "688": "RS", "690": "SC", "694": "SL", "702": "SG", "703": "SK", "705": "SI", "090": "SB",
    "706": "SO", "710": "ZA", "728": "SS", "724": "ES", "144": "LK", "729": "SD", "740": "SR", "748": "SZ",
    "752": "SE", "756": "CH", "760": "SY", "158": "TW", "762": "TJ", "834": "TZ", "764": "TH", "626": "TL",
    "768": "TG", "776": "TO", "780": "TT", "788": "TN", "792": "TR", "795": "TM", "798": "TV", "800": "UG",
    "804": "UA", "784": "AE", "826": "GB", "840": "US", "858": "UY", "860": "UZ", "548": "VU", "862": "VE",
    "704": "VN", "887": "YE", "894": "ZM", "716": "ZW"
}


def normalize_iso_code(val: Any) -> Optional[str]:
    """
    Canonical helper for converting numeric or string ISO identifiers into ISO 3166-1 alpha-2 code.
    NEVER defaults unknown or unmapped codes to GB or UK. Returns None if unmapped.
    """
    if val is None:
        return None

    val_str = str(val).strip()
    if not val_str:
        return None

    # If numeric representation (e.g. 208 or "208" or "096")
    if val_str.isdigit():
        padded = val_str.zfill(3)
        return ISO_NUMERIC_TO_ALPHA2.get(padded)

    val_upper = val_str.upper()
    if len(val_upper) == 2 and val_upper in COUNTRY_NAMES:
        return val_upper

    val_lower = val_str.lower()
    if val_lower in COUNTRY_NAME_TO_CODE:
        return COUNTRY_NAME_TO_CODE[val_lower]

    return None



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


# Reverse lookup map for full country names to ISO code
COUNTRY_NAME_TO_CODE: Dict[str, str] = {
    v.lower(): k for k, v in COUNTRY_NAMES.items()
}
# Additional alias mappings
COUNTRY_NAME_TO_CODE.update({
    "usa": "US",
    "united states of america": "US",
    "uk": "GB",
    "great britain": "GB",
    "uae": "AE",
    "russia": "RU",
    "russian federation": "RU",
    "south korea": "KR",
    "republic of korea": "KR",
    "korea": "KR",
})


def get_country_info(country_input: Any) -> Dict[str, str]:
    """Return country code, full human-readable country name, and flag emoji."""
    if not country_input:
        return {"code": "", "name": "Global / Unknown", "flag": "🌐"}

    if isinstance(country_input, dict):
        code = (country_input.get("code") or country_input.get("country_code") or "").upper()
        name = country_input.get("name") or COUNTRY_NAMES.get(code, code)
        flag = country_input.get("flag") or COUNTRY_FLAGS.get(code, "🌐")
        return {"code": code, "name": name, "flag": flag}

    val = str(country_input).strip()
    val_upper = val.upper()
    val_lower = val.lower()

    # 1. Direct code lookup (e.g. "US")
    if val_upper in COUNTRY_NAMES:
        return {
            "code": val_upper,
            "name": COUNTRY_NAMES[val_upper],
            "flag": COUNTRY_FLAGS.get(val_upper, "🌐"),
        }

    # 2. Name lookup (e.g. "United States" or "russia")
    if val_lower in COUNTRY_NAME_TO_CODE:
        code = COUNTRY_NAME_TO_CODE[val_lower]
        return {
            "code": code,
            "name": COUNTRY_NAMES.get(code, val.title()),
            "flag": COUNTRY_FLAGS.get(code, "🌐"),
        }

    # Fallback for unmapped country names/codes
    return {
        "code": val_upper if len(val) == 2 else "",
        "name": val.title() if len(val) > 2 else val_upper,
        "flag": "🌐",
    }


def format_country_badges(countries: Any, max_visible: int = 3) -> Dict[str, Any]:
    """
    Formats a list of country codes or names into visible country objects
    and an overflow count (+N) with tooltip text.
    """
    if isinstance(countries, str):
        countries = [countries]
    elif not isinstance(countries, (list, tuple, set)):
        countries = []

    cleaned = [str(c).strip() for c in (countries or []) if c]
    visible_items = [get_country_info(c) for c in cleaned[:max_visible]]
    overflow_items = [get_country_info(c) for c in cleaned[max_visible:]]
    overflow_names = [item["name"] for item in overflow_items]

    return {
        "visible": visible_items,
        "overflow_count": len(overflow_items),
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


SECTOR_DESCRIPTIONS: Dict[str, str] = {
    "AI & Technology": "Artificial intelligence, cybersecurity, software and emerging technology.",
    "Geopolitics": "Diplomacy, conflict, security and international power relations.",
    "Markets & Economy": "Macroeconomics, financial markets, monetary policy and economic developments.",
    "Business": "Companies, strategy, investment, earnings and corporate developments.",
    "Energy": "Oil, gas, electricity, renewables and global energy markets.",
    "Supply Chain & Trade": "Logistics, shipping, trade flows and global supply networks.",
    "Industry & Operations": "Manufacturing, mining, infrastructure and industrial operations.",
    "Sustainability": "Climate, environmental policy, transition and sustainable industry.",
    "World": "Strategically relevant developments across the international news environment.",
}


def get_sector_description(category_name: str) -> str:
    """Return a concise deterministic sector description for a given category name."""
    if not category_name:
        return "Strategic intelligence briefings and sector updates."
    return SECTOR_DESCRIPTIONS.get(
        category_name,
        f"Coverage and strategic intelligence analysis for {category_name}."
    )
