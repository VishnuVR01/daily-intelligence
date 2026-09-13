from datetime import datetime, date, timezone
from typing import Any, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Source


def get_articles_for_ai_processing(
    db: Session,
    limit: Optional[int] = 10,
    unprocessed_only: bool = True,
    today_only: bool = False,
    article_id: Optional[int] = None,
    provider: str = "ollama",
    model: str = "qwen3.5:4b",
    task: str = "article_analysis",
    prompt_version: str = "v1",
) -> List[Article]:
    """
    Fetches articles to process with AI according to specified filters.
    If unprocessed_only=True, excludes articles that already have an ArticleAIOutput record
    matching (article_id, provider, model, task, prompt_version).
    """
    query = db.query(Article)

    if article_id:
        query = query.filter(Article.id == article_id)

    if today_only:
        today = datetime.now(timezone.utc).date()
        query = query.filter(func.date(Article.published_at) == today)

    if unprocessed_only:
        subquery = select(ArticleAIOutput.article_id).filter(
            ArticleAIOutput.provider == provider,
            ArticleAIOutput.model == model,
            ArticleAIOutput.task == task,
            ArticleAIOutput.prompt_version == prompt_version,
        )
        query = query.filter(Article.id.not_in(subquery))

    query = query.order_by(Article.published_at.desc().nullslast(), Article.id.desc())

    if limit:
        query = query.limit(limit)

    return query.all()


def save_ai_output(
    db: Session,
    article_id: int,
    provider: str,
    model: str,
    task: str,
    prompt_version: str,
    result: Any,  # OllamaAnalysisResult
    force: bool = False,
) -> ArticleAIOutput:
    """
    Saves or updates (if force=True) an ArticleAIOutput record idempotently.
    """
    existing = (
        db.query(ArticleAIOutput)
        .filter(
            ArticleAIOutput.article_id == article_id,
            ArticleAIOutput.provider == provider,
            ArticleAIOutput.model == model,
            ArticleAIOutput.task == task,
            ArticleAIOutput.prompt_version == prompt_version,
        )
        .first()
    )

    if existing and not force:
        return existing

    output_obj = existing or ArticleAIOutput(
        article_id=article_id,
        provider=provider,
        model=model,
        task=task,
        prompt_version=prompt_version,
    )

    output_obj.status = result.status
    output_obj.processing_ms = result.processing_ms
    output_obj.error_message = result.error_message
    output_obj.processed_at = datetime.now(timezone.utc)

    if result.raw_output:
        output_obj.output_json = result.raw_output

    if result.analysis:
        output_obj.summary = result.analysis.summary
        output_obj.primary_category = result.analysis.primary_category
        output_obj.is_relevant = result.analysis.is_relevant
        output_obj.rejection_reason = result.analysis.rejection_reason
        output_obj.importance_score = result.analysis.importance_score
        output_obj.relevance_score = result.analysis.relevance_score
    elif result.raw_output:
        output_obj.summary = result.raw_output.get("summary")
        output_obj.primary_category = result.raw_output.get("primary_category")
        output_obj.is_relevant = result.raw_output.get("is_relevant")
        output_obj.rejection_reason = result.raw_output.get("rejection_reason")
        output_obj.importance_score = result.raw_output.get("importance_score")
        output_obj.relevance_score = result.raw_output.get("relevance_score")

    if not existing:
        db.add(output_obj)

    db.commit()
    db.refresh(output_obj)
    return output_obj
