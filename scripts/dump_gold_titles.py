import json

def main():
    with open("scratch/deep_gold_audit.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        qid = item["id"]
        print(f"=== {qid}: {item['question']} ===")
        if not item['gold_details']:
            print("  (No gold articles expected)")
        for g in item['gold_details']:
            aid = g.get('id')
            title = g.get('title', 'N/A')
            src = g.get('source', '')
            cat = g.get('primary_category', '')
            status = g.get('classification', 'VALID')
            print(f"  ID {aid} [{status}]: '{title}' | Src: {src} | Cat: {cat}")

if __name__ == "__main__":
    main()
