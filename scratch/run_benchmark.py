import sys
sys.path.insert(0, ".")
import time
from app.db import SessionLocal
from app.models import Article
from repositories.ai_outputs import save_ai_output
from services.ai.ollama import OllamaService

BENCHMARK_IDS = [
    2779,  # Sports (Mbappe / Real Madrid)
    2490,  # Sports (Zverev vs Shelton)
    2491,  # Sports (Rybakina vs Sabalenka)
    3143,  # Entertainment/Movie (Yle drama film)
    3154,  # Local interest (Concert venue hours)
    2926,  # Geopolitics
    2927,  # Geopolitics (US / Russia / Ukraine)
    2928,  # Geopolitics (US Army Sec Driscoll)
    3162,  # Geopolitics / World (China & India border diplomacy)
    3159,  # AI & Technology (Professor on AI risks)
    3153,  # AI & Technology (Anthropic CEO on AI safety)
    3144,  # Geopolitics / World (BRICS summit in India)
]

def run():
    db = SessionLocal()
    ollama_svc = OllamaService()

    provider = "ollama"
    model = ollama_svc.model
    task = "article_analysis"
    prompt_version = ollama_svc.prompt_version

    print("=====================================================================================================================")
    print(f"{'ID':<6} {'STATUS':<14} {'CAT':<20} {'IMP':<4} {'REL':<4} {'MS':<6} {'TITLE':<45} {'REJECTION / CAT REASON'}")
    print("---------------------------------------------------------------------------------------------------------------------")

    attempted = 0
    relevant_count = 0
    out_of_scope_count = 0
    failed_count = 0
    total_ms = 0

    for art_id in BENCHMARK_IDS:
        article = db.query(Article).filter(Article.id == art_id).first()
        if not article:
            print(f"Article ID {art_id} not found.")
            continue

        attempted += 1
        article_dict = {
            "id": article.id,
            "title": article.title,
            "raw_summary": article.raw_summary,
            "extracted_text": article.extracted_text,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "collected_at": article.collected_at.isoformat() if article.collected_at else None,
            "source_name": article.source.name if article.source else "Unknown",
            "source_family": article.source.source_family if article.source else "news",
        }

        result = ollama_svc.analyze_article(article_dict)
        total_ms += result.processing_ms

        save_ai_output(
            db=db,
            article_id=article.id,
            provider=provider,
            model=model,
            task=task,
            prompt_version=prompt_version,
            result=result,
            force=True,
        )

        if result.analysis:
            if result.analysis.is_relevant:
                relevant_count += 1
                cat_str = result.analysis.primary_category or "N/A"
                imp = result.analysis.importance_score
                rel = result.analysis.relevance_score
                reason = result.analysis.primary_category
                status_str = "RELEVANT"
            else:
                out_of_scope_count += 1
                cat_str = "[OUT OF SCOPE]"
                imp = 0
                rel = 0
                reason = result.analysis.rejection_reason or "Out of scope"
                status_str = "OUT_OF_SCOPE"
        else:
            failed_count += 1
            cat_str = "N/A"
            imp = 0
            rel = 0
            reason = result.error_message or "Failed"
            status_str = result.status.upper()

        title_sub = article.title[:44]
        reason_sub = str(reason)[:35]
        print(f"{art_id:<6} {status_str:<14} {cat_str:<20} {imp:<4} {rel:<4} {result.processing_ms:<6} {title_sub:<45} {reason_sub}")

    print("=====================================================================================================================")
    avg_ms = int(total_ms / attempted) if attempted > 0 else 0
    tech_success_count = relevant_count + out_of_scope_count
    tech_success_rate = (tech_success_count / attempted * 100.0) if attempted > 0 else 0.0

    print("\n========================================")
    print("      MIXED BENCHMARK SUMMARY RESULTS   ")
    print("========================================")
    print(f"Attempted:                {attempted}")
    print(f"Relevant:                 {relevant_count}")
    print(f"Out of scope:             {out_of_scope_count}")
    print(f"Failed:                   {failed_count}")
    print(f"Technical success rate:   {tech_success_rate:.1f}%")
    print(f"Average latency:          {avg_ms} ms ({avg_ms/1000:.2f} s)")
    print("========================================\n")
    db.close()

if __name__ == "__main__":
    run()
