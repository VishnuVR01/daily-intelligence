import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from app.models import Article, ArticleAIOutput, Source
from repositories.ai_outputs import get_articles_for_ai_processing, save_ai_output
from services.ai.ollama import OllamaService, OllamaAnalysisResult
from services.ai.schemas import ArticleAIAnalysis


# 1. Test Valid Relevant Structured Output Parsing
def test_valid_relevant_structured_output():
    json_data = {
        "is_relevant": True,
        "primary_category": "AI & Technology",
        "rejection_reason": None,
        "topics": ["Artificial Intelligence", "Hardware"],
        "countries": ["United States"],
        "entities": [{"name": "NVIDIA", "type": "company"}],
        "summary": "NVIDIA announced a new GPU architecture designed for edge computing. The chips offer 3x higher energy efficiency.",
        "importance_score": 75,
        "relevance_score": 90,
        "event_type": "product_launch",
    }
    raw_str = json.dumps(json_data)
    analysis = ArticleAIAnalysis.model_validate_json(raw_str)
    assert analysis.is_relevant is True
    assert analysis.primary_category == "AI & Technology"
    assert analysis.rejection_reason is None
    assert analysis.importance_score == 75
    assert analysis.relevance_score == 90
    assert len(analysis.entities) == 1
    assert analysis.entities[0].name == "NVIDIA"


# 1b. Test Valid Out-of-Scope Structured Output Parsing
def test_valid_out_of_scope_structured_output():
    json_data = {
        "is_relevant": False,
        "primary_category": None,
        "rejection_reason": "routine sports coverage",
        "topics": ["Tennis", "US Open"],
        "countries": ["United States"],
        "entities": [{"name": "Ben Shelton", "type": "person"}],
        "summary": "Alexander Zverev defeated Ben Shelton at the US Open.",
        "importance_score": 0,
        "relevance_score": 0,
        "event_type": "sports_match",
    }
    raw_str = json.dumps(json_data)
    analysis = ArticleAIAnalysis.model_validate_json(raw_str)
    assert analysis.is_relevant is False
    assert analysis.primary_category is None
    assert analysis.rejection_reason == "routine sports coverage"
    assert analysis.importance_score == 0
    assert analysis.relevance_score == 0


# 2. Test Invalid JSON Handling
def test_invalid_json_handling():
    svc = OllamaService(base_url="http://localhost:11434")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "message": {"content": "Not a JSON output at all..."}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_cm):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "invalid_json"
        assert result.analysis is None
        assert "Invalid JSON" in result.error_message


# 2b. Test Request Payload Parameters (think=False at top level, JSON Schema, temp=0, num_predict=1024)
def test_ollama_request_payload_parameters():
    svc = OllamaService(base_url="http://localhost:11434")
    mock_response = MagicMock()
    mock_response.status = 200
    valid_json = {
        "is_relevant": True,
        "primary_category": "World",
        "rejection_reason": None,
        "topics": ["News"],
        "countries": ["UK"],
        "entities": [],
        "summary": "Valid summary text.",
        "importance_score": 50,
        "relevance_score": 50,
        "event_type": "news",
    }
    mock_response.read.return_value = json.dumps({
        "done": True,
        "done_reason": "stop",
        "message": {"content": json.dumps(valid_json)}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    captured_request = None
    def fake_urlopen(req, timeout=None):
        nonlocal captured_request
        captured_request = req
        return mock_cm

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "success"
        assert result.analysis.primary_category == "World"

        # Verify request body parameters
        body = json.loads(captured_request.data.decode("utf-8"))
        assert body["format"] == ArticleAIAnalysis.model_json_schema()
        assert body["stream"] is False
        assert body["think"] is False
        assert body["options"]["temperature"] == 0
        assert body["options"]["num_predict"] == 1024


# 2c. Test Empty Content Handling
def test_ollama_empty_content_handling():
    svc = OllamaService(base_url="http://localhost:11434")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "done": True,
        "done_reason": "stop",
        "message": {"content": ""}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_cm):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "failed"
        assert result.analysis is None
        assert "empty content" in result.error_message.lower()


# 2d. Test done_reason=length Truncation Failure
def test_ollama_done_reason_length_handling():
    svc = OllamaService(base_url="http://localhost:11434")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "done": True,
        "done_reason": "length",
        "message": {"content": ""}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_cm):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "failed"
        assert result.done_reason == "length"
        assert "length limit" in result.error_message.lower() or "done_reason='length'" in result.error_message.lower()


# 3. Test Invalid Category Validation for Relevant Articles
def test_invalid_category_validation():
    json_data = {
        "is_relevant": True,
        "primary_category": "Invalid Nonexistent Category",
        "rejection_reason": None,
        "topics": ["News"],
        "countries": [],
        "entities": [],
        "summary": "Test summary text.",
        "importance_score": 50,
        "relevance_score": 50,
        "event_type": "news",
    }
    with pytest.raises(ValueError, match="Category 'Invalid Nonexistent Category' is invalid"):
        ArticleAIAnalysis.model_validate_json(json.dumps(json_data))


# 3b. Test Out-of-Scope Sports Article Handling (No Longer Fails Validation)
def test_out_of_scope_sports_example():
    json_data = {
        "is_relevant": False,
        "primary_category": None,
        "rejection_reason": "routine sports coverage",
        "topics": ["Tennis"],
        "countries": [],
        "entities": [],
        "summary": "Sports match recap.",
        "importance_score": 0,
        "relevance_score": 0,
        "event_type": "sports",
    }
    analysis = ArticleAIAnalysis.model_validate_json(json.dumps(json_data))
    assert analysis.is_relevant is False
    assert analysis.primary_category is None
    assert analysis.rejection_reason == "routine sports coverage"


# 4. Test Out-of-Range Scores
def test_out_of_range_scores():
    json_data_high = {
        "is_relevant": True,
        "primary_category": "World",
        "rejection_reason": None,
        "topics": [],
        "countries": [],
        "entities": [],
        "summary": "Test summary.",
        "importance_score": 150,
        "relevance_score": 50,
        "event_type": "news",
    }
    with pytest.raises(ValueError, match="out of allowed range"):
        ArticleAIAnalysis.model_validate_json(json.dumps(json_data_high))

    json_data_low = json_data_high.copy()
    json_data_low["importance_score"] = 50
    json_data_low["relevance_score"] = -10
    with pytest.raises(ValueError, match="out of allowed range"):
        ArticleAIAnalysis.model_validate_json(json.dumps(json_data_low))


# 5. Test Ollama Unavailable Connection Error
def test_ollama_unavailable():
    svc = OllamaService(base_url="http://localhost:11434")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "unavailable"
        assert "unavailable" in result.error_message.lower()


# 6. Test Timeout Handling
def test_ollama_timeout():
    svc = OllamaService(base_url="http://localhost:11434", timeout_seconds=2)
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "timeout"
        assert "timed out" in result.error_message.lower()


# 7. Test Missing Extracted Text Fallback
def test_missing_extracted_text_fallback():
    svc = OllamaService()
    article_data = {
        "title": "Headline Only",
        "source_name": "Test Source",
        "source_family": "news",
        "raw_summary": "This is the raw RSS summary text.",
        "extracted_text": None,
    }
    prompt = svc.prepare_article_prompt(article_data)
    assert "Headline Only" in prompt
    assert "This is the raw RSS summary text." in prompt


# 8. Test Duplicate Processing Idempotency & Force Reprocessing
def test_duplicate_processing_and_force(test_db_session):
    source = Source(name="Test AI Source", source_family="news", category="AI & Technology")
    test_db_session.add(source)
    test_db_session.commit()

    article = Article(
        source_id=source.id,
        title="Test Idempotency Article",
        canonical_url="https://example.com/idempotency-test-1",
        raw_summary="Summary text for idempotency testing.",
    )
    test_db_session.add(article)
    test_db_session.commit()

    provider = "ollama"
    model = "qwen3.5:4b"
    task = "article_analysis"
    version = "v1"

    # Initially unprocessed
    unprocessed = get_articles_for_ai_processing(
        test_db_session, article_id=article.id, unprocessed_only=True, provider=provider, model=model, task=task, prompt_version=version
    )
    assert len(unprocessed) == 1

    # Save output 1
    analysis1 = ArticleAIAnalysis(
        is_relevant=True,
        primary_category="AI & Technology",
        summary="Initial AI summary.",
        importance_score=60,
        relevance_score=80,
    )
    res1 = OllamaAnalysisResult(analysis=analysis1, status="success", processing_ms=100)
    saved1 = save_ai_output(test_db_session, article.id, provider, model, task, version, res1)
    assert saved1.summary == "Initial AI summary."
    assert saved1.is_relevant is True
    assert saved1.rejection_reason is None

    # Verify article is now excluded from unprocessed query
    unprocessed_after = get_articles_for_ai_processing(
        test_db_session, article_id=article.id, unprocessed_only=True, provider=provider, model=model, task=task, prompt_version=version
    )
    assert len(unprocessed_after) == 0

    # Save output 2 without force -> returns existing output 1
    analysis2 = ArticleAIAnalysis(
        is_relevant=True,
        primary_category="AI & Technology",
        summary="Updated AI summary.",
        importance_score=90,
        relevance_score=95,
    )
    res2 = OllamaAnalysisResult(analysis=analysis2, status="success", processing_ms=150)
    saved2 = save_ai_output(test_db_session, article.id, provider, model, task, version, res2, force=False)
    assert saved2.summary == "Initial AI summary."

    # Save output 2 WITH force=True -> overwrites output 1
    saved3 = save_ai_output(test_db_session, article.id, provider, model, task, version, res2, force=True)
    assert saved3.summary == "Updated AI summary."
    assert saved3.importance_score == 90
