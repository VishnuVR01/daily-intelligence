from ingestion.dedupe import normalise_title, title_fingerprint


def test_equivalent_titles_have_same_fingerprint():
    assert title_fingerprint("AI Changes Supply Chains!") == title_fingerprint(
        "ai changes supply chains"
    )


def test_normalise_title_strips_punctuation_and_spaces():
    assert normalise_title("  Breaking: Market Up 10% !  ") == "breaking market up 10"


def test_fingerprint_is_sha256_hex():
    fp = title_fingerprint("Sample Title")
    assert len(fp) == 64
    assert isinstance(fp, str)
