import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import SessionLocal
from app.models import Article, ArticleAIOutput

def main():
    db = SessionLocal()
    print("RAG-005 Gold Article Audit:")
    for aid in [3763, 3768, 3770, 3772, 3775, 3778, 3780]:
        art = db.query(Article).filter(Article.id == aid).first()
        ai = db.query(ArticleAIOutput).filter(ArticleAIOutput.article_id == aid).first()
        if art:
            print(f"ID {aid}: '{art.title}' | Src: {art.source.name if art.source else 'Unknown'}")
            if ai:
                print(f"   Category: {ai.primary_category} | Relevant: {ai.is_relevant}")
                print(f"   Summary: {ai.summary}")
        else:
            print(f"ID {aid}: NOT FOUND IN DB!")

if __name__ == "__main__":
    main()
