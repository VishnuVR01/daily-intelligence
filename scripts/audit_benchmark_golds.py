"""
Audit all gold article IDs in benchmarks/rag_v1.json against local PostgreSQL archive and save JSON report.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source, Country

def main():
    db = SessionLocal()
    with open("benchmarks/rag_v1.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    results = []

    for q in questions:
        q_id = q["id"]
        q_text = q["question"]
        expected_ids = q.get("expected_article_ids", [])
        
        q_res = {
            "id": q_id,
            "category": q["category"],
            "question": q_text,
            "expected_article_ids": expected_ids,
            "gold_audit": []
        }
        
        for aid in expected_ids:
            art = db.query(Article).filter(Article.id == aid).first()
            if not art:
                q_res["gold_audit"].append({
                    "article_id": aid,
                    "classification": "STALE_ID_OR_DATA_DRIFT",
                    "reason": "Article ID not found in local DB"
                })
                continue
            
            ai = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == aid).first()
            src_name = art.source.name if art.source else "Unknown"
            title = art.title or ""
            pub_at = art.published_at.isoformat() if art.published_at else None
            col_at = art.collected_at.isoformat() if art.collected_at else None
            
            if not ai:
                q_res["gold_audit"].append({
                    "article_id": aid,
                    "title": title,
                    "source": src_name,
                    "classification": "UNANALYZED",
                    "reason": "No AI output record exists (is_relevant=None)"
                })
                continue
            
            if not ai.is_relevant:
                q_res["gold_audit"].append({
                    "article_id": aid,
                    "title": title,
                    "source": src_name,
                    "classification": "OUT_OF_SCOPE",
                    "reason": f"is_relevant=False ({ai.rejection_reason})"
                })
                continue
            
            q_res["gold_audit"].append({
                "article_id": aid,
                "title": title,
                "source": src_name,
                "published_at": pub_at,
                "collected_at": col_at,
                "ai_relevant": ai.is_relevant,
                "relevance_score": ai.relevance_score,
                "importance_score": ai.importance_score,
                "primary_category": ai.primary_category,
                "summary": ai.summary,
                "classification": "PENDING_SEMANTIC_REVIEW"
            })
            
        results.append(q_res)

    with open("scratch/audit_raw_golds.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved raw gold audit to scratch/audit_raw_golds.json for {len(results)} questions.")

if __name__ == "__main__":
    main()
