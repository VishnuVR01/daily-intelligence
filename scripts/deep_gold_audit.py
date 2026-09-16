"""
Deep audit of all expected article IDs across all 25 benchmark questions.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Article, ArticleAIOutput, Source

def main():
    db = SessionLocal()
    with open("benchmarks/rag_v1.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    report = []

    for q in questions:
        qid = q["id"]
        qtext = q["question"]
        cat = q["category"]
        expected_ids = q.get("expected_article_ids", [])
        
        q_item = {
            "id": qid,
            "category": cat,
            "question": qtext,
            "expected_min_evidence": q.get("expected_min_evidence", 0),
            "should_be_answerable": q.get("should_be_answerable", True),
            "expected_article_ids": expected_ids,
            "gold_details": []
        }
        
        for aid in expected_ids:
            art = db.query(Article).filter(Article.id == aid).first()
            if not art:
                q_item["gold_details"].append({
                    "id": aid,
                    "status": "NOT_FOUND",
                    "classification": "STALE_ID_OR_DATA_DRIFT"
                })
                continue
                
            ai = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == aid).first()
            src_name = art.source.name if art.source else "Unknown"
            title = art.title or ""
            
            if not ai:
                q_item["gold_details"].append({
                    "id": aid,
                    "title": title,
                    "source": src_name,
                    "classification": "UNANALYZED"
                })
                continue
                
            if not ai.is_relevant:
                q_item["gold_details"].append({
                    "id": aid,
                    "title": title,
                    "source": src_name,
                    "relevance_score": ai.relevance_score,
                    "rejection_reason": ai.rejection_reason,
                    "classification": "OUT_OF_SCOPE"
                })
                continue

            q_item["gold_details"].append({
                "id": aid,
                "title": title,
                "source": src_name,
                "published_at": art.published_at.isoformat() if art.published_at else None,
                "relevance_score": ai.relevance_score,
                "importance_score": ai.importance_score,
                "primary_category": ai.primary_category,
                "summary": ai.summary
            })
            
        report.append(q_item)

    with open("scratch/deep_gold_audit.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    print(f"Deep audit written to scratch/deep_gold_audit.json for {len(report)} questions.")

if __name__ == "__main__":
    main()
