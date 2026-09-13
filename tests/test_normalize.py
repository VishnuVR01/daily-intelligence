from ingestion.normalize import canonicalize_url


def test_tracking_parameters_removed():
    url = "https://example.com/story/?utm_source=test&id=42"
    assert canonicalize_url(url) == "https://example.com/story?id=42"


def test_canonicalize_url_strips_fbclid_and_gclid():
    url = "https://EXAMPLE.COM/article/?gclid=123&fbclid=abc&utm_medium=email"
    assert canonicalize_url(url) == "https://example.com/article"


def test_canonicalize_url_normalizes_case_and_trailing_slashes():
    url = "HTTPS://HTTPBIN.ORG/PATH/to/resource/"
    assert canonicalize_url(url) == "https://httpbin.org/PATH/to/resource"
