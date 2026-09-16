import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput
from services.ai.ollama import OllamaService
from repositories.ai_outputs import save_ai_output

def run_controlled_ai_batch():
    db = SessionLocal()
    try:
        latest_before_id = 3819
        # Fetch 5 newly inserted articles
        articles = (
            db.query(Article)
            .filter(Article.id > latest_before_id)
            .order_by(Article.id.asc())
            .limit(5)
            .all()
        )
        
        print("=" * 70)
        print(f"RUNNING CONTROLLED AI PROCESSING BATCH ({len(articles)} articles)")
        print("=" * 70)
        
        service = OllamaService()
        print(f"Ollama Health Diagnostic: {service.get_health_status()}")
        
        ai_results = []
        for idx, art in enumerate(articles, 1):
            src_name = art.source.name if art.source else "Unknown Source"
            print(f"\n[{idx}/{len(articles)}] Processing Article ID {art.id}: '{art.title[:60]}...' ({src_name})")
            
            art_data = {
                "title": art.title,
                "source_name": src_name,
                "source_family": art.source.source_type if art.source else "news",
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "collected_at": art.collected_at.isoformat() if art.collected_at else None,
                "raw_summary": art.raw_summary,
                "extracted_text": None
            }
            
            res = service.analyze_article(art_data)
            print(f"  Status: {res.status} | Processing Time: {res.processing_ms}ms")
            
            # Save to DB idempotently
            saved_out = save_ai_output(
                db=db,
                article_id=art.id,
                provider="ollama",
                model=service.model,
                task="article_analysis",
                prompt_version=service.prompt_version,
                result=res
            )
            db.commit()
            
            # Verify article row in DB is completely intact
            art_check = db.query(Article).filter(Article.id == art.id).first()
            assert art_check is not None, f"Article {art.id} was corrupted!"
            
            analysis = res.analysis
            is_rel = analysis.is_relevant if analysis else False
            rel_score = analysis.relevance_score if analysis else 0
            imp_score = analysis.importance_score if analysis else 0
            cat = analysis.primary_category if analysis else None
            has_summary = bool(analysis.summary) if analysis else False
            has_topics = bool(analysis.topics) if analysis else False
            has_entities = bool(analysis.entities) if analysis else False
            
            info = {
                "article_id": art.id,
                "title": art.title,
                "source": src_name,
                "ai_status": res.status,
                "is_relevant": is_rel,
                "relevance_score": rel_score,
                "importance_score": imp_score,
                "primary_category": cat,
                "summary_generated": has_summary,
                "topics_generated": has_topics,
                "entities_generated": has_entities,
                "summary_preview": analysis.summary[:100] + "..." if (analysis and analysis.summary) else None
            }
            ai_results.append(info)
            print(f"  Relevant: {is_rel} | Score: {imp_score} | Category: {cat} | Summary: {has_summary} | Topics: {has_topics}")

        with open("scratch/controlled_ai_batch_results.json", "w", encoding="utf-8") as f:
            json.dump(ai_results, f, indent=2)
            
        print("\n" + "=" * 70)
        print("AI Processing Batch Complete! Results saved to scratch/controlled_ai_batch_results.json")

    finally:
        db.close()

if __name__ == "__main__":
    run_controlled_ai_batch()
