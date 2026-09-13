"""
Unit tests for app/intelligence_groups.py and intelligence group lens functionality.
"""

from app.intelligence_groups import (
    INTELLIGENCE_GROUPS,
    get_all_lens_chips,
    get_group_country_codes,
    get_group_info,
)


def test_intelligence_groups_configuration_keys():
    expected_keys = ["world", "brics", "g7", "g20", "eu", "opec", "gcc", "asean", "nordics", "baltics"]
    for key in expected_keys:
        assert key in INTELLIGENCE_GROUPS
        group = INTELLIGENCE_GROUPS[key]
        assert "name" in group
        assert "label" in group
        assert "type" in group
        assert "country_codes" in group


def test_g7_membership():
    g7_codes = get_group_country_codes("g7")
    expected = ["US", "GB", "DE", "FR", "IT", "JP", "CA", "EU"]
    for code in expected:
        assert code in g7_codes


def test_asean_exact_membership():
    asean_codes = get_group_country_codes("asean")
    expected = {"BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN"}
    assert set(asean_codes) == expected
    assert len(asean_codes) == 11
    assert "TL" in asean_codes  # Timor-Leste explicit check


def test_nordics_exact_membership():
    nordic_codes = get_group_country_codes("nordics")
    expected = {"DK", "FI", "IS", "NO", "SE"}
    assert set(nordic_codes) == expected
    assert len(nordic_codes) == 5


def test_baltics_exact_membership():
    baltic_codes = get_group_country_codes("baltics")
    expected = {"EE", "LV", "LT"}
    assert set(baltic_codes) == expected
    assert len(baltic_codes) == 3


def test_gb_not_in_regional_lenses():
    assert "GB" not in get_group_country_codes("asean")
    assert "GB" not in get_group_country_codes("nordics")
    assert "GB" not in get_group_country_codes("baltics")


def test_iso_normalization_no_gb_fallback():
    from app.entity_metadata import ISO_NUMERIC_TO_ALPHA2, normalize_iso_code

    # Unknown or invalid codes must NEVER resolve to GB
    assert normalize_iso_code("999") is None
    assert normalize_iso_code("XX") is None
    assert normalize_iso_code("") is None
    assert normalize_iso_code(None) is None

    # Every member of ASEAN, Nordics, and Baltics must resolve properly
    all_members = set(get_group_country_codes("asean")) | set(get_group_country_codes("nordics")) | set(get_group_country_codes("baltics"))
    for code in all_members:
        assert normalize_iso_code(code) == code

    # Verify every member has a valid numeric ISO entry in ISO_NUMERIC_TO_ALPHA2
    num_to_alpha = set(ISO_NUMERIC_TO_ALPHA2.values())
    for code in all_members:
        assert code in num_to_alpha

