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


# 9. Test Local Mode: localhost works without API key & no Authorization header sent
def test_local_mode_no_auth_header():
    svc = OllamaService(base_url="http://localhost:11434", model="qwen3.5:4b", api_key="")
    assert svc.mode == "LOCAL"

    captured_headers = None
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "done": True,
        "done_reason": "stop",
        "message": {"content": json.dumps({
            "is_relevant": True,
            "primary_category": "World",
            "rejection_reason": None,
            "topics": ["News"],
            "countries": [],
            "entities": [],
            "summary": "Local summary.",
            "importance_score": 60,
            "relevance_score": 70,
            "event_type": "event",
        })}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    def fake_urlopen(req, timeout=None):
        nonlocal captured_headers
        captured_headers = req.headers
        return mock_cm

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = svc.analyze_article({"title": "Local Article", "raw_summary": "Local summary"})
        assert result.status == "success"
        # Verify no Authorization header is present
        assert "Authorization" not in captured_headers
        assert "authorization" not in captured_headers


# 10. Test Cloud Mode: ollama.com uses Bearer authentication & cloud model
def test_cloud_mode_bearer_authentication():
    secret_key = "ollama_cloud_secret_xyz123"
    svc = OllamaService(
        base_url="https://ollama.com",
        model="cloud-llama3-70b",
        api_key=secret_key,
    )
    assert svc.mode == "CLOUD"

    captured_headers = None
    captured_body = None
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "done": True,
        "done_reason": "stop",
        "message": {"content": json.dumps({
            "is_relevant": True,
            "primary_category": "AI & Technology",
            "rejection_reason": None,
            "topics": ["Cloud AI"],
            "countries": [],
            "entities": [],
            "summary": "Cloud summary.",
            "importance_score": 85,
            "relevance_score": 90,
            "event_type": "event",
        })}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    def fake_urlopen(req, timeout=None):
        nonlocal captured_headers, captured_body
        captured_headers = req.headers
        captured_body = json.loads(req.data.decode("utf-8"))
        return mock_cm

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = svc.analyze_article({"title": "Cloud Article", "raw_summary": "Cloud summary"})
        assert result.status == "success"
        # Verify Authorization header contains Bearer token
        auth_header = captured_headers.get("Authorization")
        assert auth_header == f"Bearer {secret_key}"
        # Verify configured cloud model is passed in payload
        assert captured_body["model"] == "cloud-llama3-70b"


# 11. Test Health Status diagnostic does not expose API key
def test_get_health_status_safe_diagnostics():
    secret_key = "super_secret_never_leak_me"
    svc = OllamaService(
        base_url="https://ollama.com",
        model="cloud-model-v1",
        api_key=secret_key,
    )
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "models": [{"name": "cloud-model-v1"}]
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_cm):
        status = svc.get_health_status()
        assert status["provider"] == "ollama"
        assert status["mode"] == "cloud"
        assert status["available"] is True
        assert status["model_configured"] is True
        # Ensure secret is nowhere in the returned dict
        assert secret_key not in str(status)


# 12. Test HTTP 401 Unauthorized handling in Cloud Mode
def test_cloud_401_unauthorized_handled_safely():
    secret_key = "invalid_secret_key"
    svc = OllamaService(
        base_url="https://ollama.com",
        model="cloud-model",
        api_key=secret_key,
    )
    http_401 = urllib.error.HTTPError(
        url="https://ollama.com/api/chat",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_401):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "failed"
        assert "401" in result.error_message
        assert "Authentication failed" in result.error_message
        # Crucial security check: secret key never leaks into error message
        assert secret_key not in result.error_message


# 13. Test Cloud Timeout handling
def test_cloud_timeout_handled_safely():
    secret_key = "my_cloud_secret"
    svc = OllamaService(
        base_url="https://ollama.com",
        model="cloud-model",
        api_key=secret_key,
        timeout_seconds=60,
    )
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
        result = svc.analyze_article({"title": "Test Title", "raw_summary": "Test Summary"})
        assert result.status == "timeout"
        assert "60s" in result.error_message
        assert secret_key not in result.error_message


# 14. Test Cloud Chat Completion & chat_json helper
def test_cloud_chat_json_helper():
    svc = OllamaService(
        base_url="https://ollama.com",
        model="cloud-model",
        api_key="my_key",
    )
    rag_response = {
        "answer": "This is a grounded answer [1].",
        "key_themes": ["Geopolitics"],
        "confidence": "high",
        "insufficient_evidence": False,
        "cited_record_numbers": [1],
    }
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "message": {"role": "assistant", "content": json.dumps(rag_response)}
    }).encode("utf-8")

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_cm):
        res = svc.chat_json([{"role": "user", "content": "Question"}])
        assert res is not None
        assert res["answer"] == "This is a grounded answer [1]."
        assert res["cited_record_numbers"] == [1]


# 15. Test Unavailable Cloud Service does not crash web routes
def test_unavailable_cloud_service_does_not_crash_web_routes(test_db_session):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # When Ollama chat fails or times out
    with patch.object(OllamaService, "chat_json", return_value=None):
        # API research endpoint
        resp = client.post("/api/research", json={"question": "Test question about markets"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "Archive research is temporarily unavailable." in data["answer"] or data.get("insufficient_evidence") in (True, False)

        # GET /research route
        resp_view = client.get("/research?q=Test+question")
        assert resp_view.status_code == 200
        assert b"Archive Research" in resp_view.content or b"Grounded RAG" in resp_view.content

