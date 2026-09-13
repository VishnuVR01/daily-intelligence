from ingestion.normalize import clean_summary_text


def test_clean_summary_nbsp_decoded():
    raw = "Ola&nbsp;Ishiwini&nbsp;sits with her team."
    assert clean_summary_text(raw) == "Ola Ishiwini sits with her team."


def test_clean_summary_amp_and_quot_decoded():
    raw = "Stock &amp; Bond &quot;Market&quot; Update &#39;Today&#39;"
    assert clean_summary_text(raw) == "Stock & Bond \"Market\" Update 'Today'"


def test_clean_summary_html_tags_removed():
    raw = "<p>This is a <b>summary</b> with <a href=\"https://example.com\">a link</a>.</p>"
    assert clean_summary_text(raw) == "This is a summary with a link ." or clean_summary_text(raw) == "This is a summary with a link."


def test_clean_summary_multiple_spaces_and_newlines():
    raw = "  Line 1   with   extra spaces \n\n  Line 2   and newlines.  "
    assert clean_summary_text(raw) == "Line 1 with extra spaces Line 2 and newlines."


def test_clean_summary_plain_text_unchanged():
    raw = "Normal plain text summary without HTML."
    assert clean_summary_text(raw) == "Normal plain text summary without HTML."


def test_clean_summary_none_and_empty():
    assert clean_summary_text(None) is None
    assert clean_summary_text("") is None
    assert clean_summary_text("   \n\t   ") is None
