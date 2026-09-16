import json

def main():
    with open("scratch/audit_raw_golds.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        qid = item["id"]
        qtext = item["question"]
        golds = item["gold_audit"]
        print(f"=== {qid}: {qtext} ===")
        if not golds:
            print("  (No gold articles expected)")
        for g in golds:
            aid = g.get("article_id")
            title = g.get("title", "N/A")
            cls = g.get("classification")
            src = g.get("source", "")
            sum_snippet = (g.get("summary") or "")[:90].replace("\n", " ")
            print(f"  [{cls}] ID {aid}: '{title}' ({src})")
            print(f"      Summary: {sum_snippet}")

if __name__ == "__main__":
    main()
