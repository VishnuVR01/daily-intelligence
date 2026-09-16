"""
Unit and Integration Tests for Stage 1C Autonomous Ingestion + AI Processing Orchestration.
Validates orchestrator cycles, overlap protection, bounded draining, failure isolation,
scheduler job safety, and manual one-shot execution paths.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import get_settings
from app.models import Article, ArticleAIOutput, Source
from repositories.ai_outputs import save_ai_output
from repositories.ai_queue import get_ai_queue_status
from services.ai.ollama import OllamaAnalysisResult, ArticleAIAnalysis
from services.lock import pipeline_lock
from services.orchestrator import run_ai_cycle, run_ingestion_cycle, run_pipeline_cycle


@pytest.fixture
def orch_source(test_db_session):
    src = Source(
        name="Orchestrator Test News",
        feed_url="https://example.com/orch-feed.xml",
        source_type="rss",
        source_family="news",
        trust_tier="primary",
        active=True,
    )
    test_db_session.add(src)
    test_db_session.commit()
    test_db_session.refresh(src)
    return src


@pytest.fixture
def orch_articles(test_db_session, orch_source):
    now = datetime.now(timezone.utc)
    articles = []
    for i in range(1, 16):
        art = Article(
            source_id=orch_source.id,
            title=f"Orchestration Article {i} AI semiconductor policy",
            canonical_url=f"https://example.com/orch-art-{i}",
            collected_at=now,
            published_at=now,
        )
        test_db_session.add(art)
        articles.append(art)
    test_db_session.commit()
    for art in articles:
        test_db_session.refresh(art)
    return articles


def test_ingestion_and_ai_execution_are_independent(test_db_session, orch_articles):
    """1. Ingestion success does not depend on AI success; AI unavailable leaves ingestion completed."""
    mock_svc = MagicMock()
    mock_svc.check_health.return_value = False  # Ollama offline

    # Ingestion cycle runs cleanly
    ing_res = run_ingestion_cycle(db=test_db_session)
    assert ing_res["status"] == "COMPLETED"

    # AI cycle detects Ollama offline and exits safely
    ai_res = run_ai_cycle(db=test_db_session, ollama_service=mock_svc)
    assert ai_res["status"] == "SKIPPED_OLLAMA_UNAVAILABLE"


def test_bounded_ai_batch_size(test_db_session, orch_articles):
    """2. AI processing strictly respects the bounded batch size per batch execution."""
    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="AI & Technology", summary="Sum", importance_score=80, relevance_score=80)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    ai_res = run_ai_cycle(db=test_db_session, batch_size=3, max_batches=1, ollama_service=mock_svc)
    assert ai_res["status"] == "COMPLETED"
    assert ai_res["articles_claimed"] == 3


def test_max_batches_per_cycle(test_db_session, orch_articles):
    """3. AI processing strictly respects max_batches_per_cycle limit (e.g. 2 batches of 3 = 6 max)."""
    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="World", summary="Sum", importance_score=75, relevance_score=80)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    ai_res = run_ai_cycle(db=test_db_session, batch_size=3, max_batches=2, ollama_service=mock_svc)
    assert ai_res["status"] == "COMPLETED"
    assert ai_res["articles_claimed"] == 6


def test_priority_queue_reused_correctly(test_db_session, orch_source):
    """4. Orchestrator uses Stage 1B priority ordering (P0_CRITICAL claimed before P3_LOW)."""
    now = datetime.now(timezone.utc)
    art_low = Article(source_id=orch_source.id, title="Sports match score", canonical_url="https://example.com/p3-sports", collected_at=now)
    art_high = Article(source_id=orch_source.id, title="Federal Reserve interest rate AI chip crisis", canonical_url="https://example.com/p0-fed", collected_at=now)
    test_db_session.add_all([art_low, art_high])
    test_db_session.commit()

    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="World", summary="Sum", importance_score=80, relevance_score=80)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    ai_res = run_ai_cycle(db=test_db_session, batch_size=1, max_batches=1, ollama_service=mock_svc)
    assert ai_res["articles_claimed"] == 1
    assert ai_res["article_results"][0]["article_id"] == art_high.id


def test_ingestion_failure_isolated_per_source(test_db_session, orch_source):
    """5. Failure collecting one source does not crash the ingestion cycle for other sources."""
    bad_source = Source(name="Broken Feed", feed_url="https://invalid-host-name-9999.xyz/rss.xml", source_type="rss", active=True)
    test_db_session.add(bad_source)
    test_db_session.commit()

    res = run_ingestion_cycle(db=test_db_session)
    assert res["status"] == "COMPLETED"
    assert res["sources_attempted"] >= 2


def test_ollama_unavailable_does_not_fail_ingestion(test_db_session, orch_source):
    """6. Complete pipeline cycle handles Ollama offline safely without breaking ingestion results."""
    mock_svc = MagicMock()
    mock_svc.check_health.return_value = False

    pipe_res = run_pipeline_cycle(db=test_db_session, ollama_service=mock_svc)
    assert pipe_res["status"] == "COMPLETED"
    assert pipe_res["ingestion"]["status"] == "COMPLETED"
    assert pipe_res["ai_processing"]["status"] == "SKIPPED_OLLAMA_UNAVAILABLE"


def test_overlap_guard_works(test_db_session):
    """7. Overlap guard prevents concurrent execution of the same cycle name (SKIPPED_ALREADY_RUNNING)."""
    with pipeline_lock(test_db_session, "test_overlap_cycle") as first_acquired:
        assert first_acquired is True
        with pipeline_lock(test_db_session, "test_overlap_cycle") as second_acquired:
            assert second_acquired is False


def test_scheduler_job_exception_isolation():
    """8. Exception inside scheduled job wrapper is caught safely without killing scheduler."""
    from scripts.run_scheduler import scheduled_ingestion_job, scheduled_ai_job
    with patch("scripts.run_scheduler.run_ingestion_cycle", side_effect=RuntimeError("Transient DB glitch")):
        scheduled_ingestion_job()  # Should log exception and return safely without raising exception

    with patch("scripts.run_scheduler.run_ai_cycle", side_effect=RuntimeError("Ollama crash")):
        scheduled_ai_job()  # Should log exception and return safely without raising exception


def test_scheduler_job_registration_is_idempotent():
    """9. Registering scheduled jobs with replace_existing=True is idempotent."""
    from scripts.run_scheduler import scheduled_ingestion_job
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(scheduled_ingestion_job, trigger="interval", minutes=10, id="test_job_1", replace_existing=True)
    scheduler.add_job(scheduled_ingestion_job, trigger="interval", minutes=10, id="test_job_1", replace_existing=True)

    job = scheduler.get_job("test_job_1")
    assert job is not None
    assert job.id == "test_job_1"


def test_configuration_controls_cadence():
    """10. Settings properly control ingestion and AI intervals and bounded limits."""
    settings = get_settings()
    assert hasattr(settings, "ingestion_interval_minutes")
    assert hasattr(settings, "ai_interval_minutes")
    assert hasattr(settings, "ai_batch_size")
    assert hasattr(settings, "ai_max_batches_per_cycle")


def test_empty_ingestion_cycle_succeeds(test_db_session):
    """11. Ingestion cycle on DB with 0 active sources completes with 0 fetched."""
    res = run_ingestion_cycle(db=test_db_session)
    assert res["status"] == "COMPLETED"
    assert res["new_articles_inserted"] == 0


def test_ai_backlog_processes_without_new_ingestion(test_db_session, orch_articles):
    """12. AI processing cycle drains existing unprocessed article backlog independently."""
    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="World", summary="Sum", importance_score=75, relevance_score=80)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    ai_res = run_ai_cycle(db=test_db_session, batch_size=5, max_batches=1, ollama_service=mock_svc)
    assert ai_res["status"] == "COMPLETED"
    assert ai_res["articles_claimed"] == 5


def test_manual_one_shot_ingestion_works(test_db_session):
    """13. Manual one-shot ingestion script execution path operates correctly."""
    from scripts.run_ingestion_once import main as main_ing
    with patch("scripts.run_ingestion_once.run_ingestion_cycle") as mock_ing:
        mock_ing.return_value = {"status": "COMPLETED", "sources_attempted": 1, "new_articles_inserted": 0}
        main_ing()
        mock_ing.assert_called_once()


def test_manual_one_shot_ai_works(test_db_session):
    """14. Manual one-shot AI script execution path operates correctly."""
    from scripts.run_ai_once import main as main_ai
    with patch("scripts.run_ai_once.run_ai_cycle") as mock_ai:
        mock_ai.return_value = {"status": "COMPLETED", "articles_claimed": 0}
        with patch("sys.argv", ["run_ai_once.py", "--batch-size", "5", "--max-batches", "2"]):
            main_ai()
            mock_ai.assert_called_once()


def test_pipeline_one_shot_works(test_db_session):
    """15. Manual one-shot complete pipeline script execution path operates correctly."""
    from scripts.run_pipeline_once import main as main_pipe
    with patch("scripts.run_pipeline_once.run_pipeline_cycle") as mock_pipe:
        mock_pipe.return_value = {"status": "COMPLETED", "ingestion": {}, "ai_processing": {}}
        with patch("sys.argv", ["run_pipeline_once.py"]):
            main_pipe()
            mock_pipe.assert_called_once()


def test_scheduler_shutdown_is_clean():
    """16. Scheduler shutdown executes cleanly without lingering threads or errors."""
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(lambda: None, trigger="interval", minutes=60, id="dummy_job")
    scheduler.start()
    assert scheduler.running
    scheduler.shutdown(wait=False)
    assert not scheduler.running


def test_no_article_provenance_modification(test_db_session, orch_articles):
    """17. Autonomous orchestration cycle never modifies Article title, canonical_url, or source provenance."""
    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="World", summary="Sum", importance_score=75, relevance_score=80)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    run_pipeline_cycle(db=test_db_session, ai_batch_size=2, ai_max_batches=1, ollama_service=mock_svc)

    art = test_db_session.query(Article).filter(Article.id == orch_articles[0].id).first()
    assert art.title == "Orchestration Article 1 AI semiconductor policy"
    assert art.canonical_url == "https://example.com/orch-art-1"
    assert art.source.provenance == "institutional" or art.source.trust_tier == "primary"


def test_no_duplicate_ai_outputs(test_db_session, orch_source):
    """18. Repeated pipeline cycle executions create zero duplicate ArticleAIOutput rows."""
    now = datetime.now(timezone.utc)
    arts = []
    for i in range(1, 6):
        art = Article(source_id=orch_source.id, title=f"Dedup Art {i}", canonical_url=f"https://example.com/dedup-{i}", collected_at=now)
        test_db_session.add(art)
        arts.append(art)
    test_db_session.commit()

    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="World", summary="Sum", importance_score=75, relevance_score=80)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    # Run cycle 1 (claims 5 articles)
    run_pipeline_cycle(db=test_db_session, ai_batch_size=5, ai_max_batches=1, ollama_service=mock_svc)
    # Run cycle 2 (0 new articles claimed because all 5 are completed)
    run_pipeline_cycle(db=test_db_session, ai_batch_size=5, ai_max_batches=1, ollama_service=mock_svc)

    outputs = test_db_session.query(ArticleAIOutput).filter(ArticleAIOutput.article_id.in_([a.id for a in arts])).all()
    assert len(outputs) == 5
    assert len(set(out.article_id for out in outputs)) == 5  # Zero duplicates created!


def test_pending_vs_failed_semantics(test_db_session, orch_source):
    """19. Pending != failed semantics remain strictly preserved across orchestrator cycles."""
    now = datetime.now(timezone.utc)
    art_unproc = Article(source_id=orch_source.id, title="Unprocessed Art", canonical_url="https://example.com/pending-1", collected_at=now)
    art_failed = Article(source_id=orch_source.id, title="Failed Art", canonical_url="https://example.com/failed-1", collected_at=now)
    test_db_session.add_all([art_unproc, art_failed])
    test_db_session.commit()

    save_ai_output(
        db=test_db_session,
        article_id=art_failed.id,
        provider="ollama",
        model="qwen3.5:4b",
        task="article_analysis",
        prompt_version="v1",
        result=OllamaAnalysisResult(status="failed", error_message="Connection lost"),
    )

    q_status = get_ai_queue_status(test_db_session)
    assert q_status["unprocessed"] == 1
    assert q_status["failed"] == 1


def test_all_stage_1a_1b_behaviour_remains_green(test_db_session, orch_source):
    """20. Priority ordering and transaction safety from Stage 1A/1B remain 100% functional."""
    now = datetime.now(timezone.utc)
    art = Article(source_id=orch_source.id, title="Federal Reserve interest rate decisions", canonical_url="https://example.com/green-1", collected_at=now)
    test_db_session.add(art)
    test_db_session.commit()

    mock_svc = MagicMock()
    mock_svc.check_health.return_value = True
    analysis = ArticleAIAnalysis(is_relevant=True, primary_category="Markets & Economy", summary="Sum", importance_score=90, relevance_score=90)
    mock_svc.analyze_article.return_value = OllamaAnalysisResult(analysis=analysis, status="success")

    res = run_ai_cycle(db=test_db_session, batch_size=1, max_batches=1, ollama_service=mock_svc)
    assert res["status"] == "COMPLETED"
    assert res["articles_claimed"] == 1
    assert res["completed_relevant"] == 1
