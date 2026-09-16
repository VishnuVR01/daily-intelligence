import os
import sys
import time
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

sys.path.insert(0, os.getcwd())

from app.db import SessionLocal
from app.models import Source, Article
from ingestion.rss import fetch_feed
import urllib.request
import ssl

def audit_active_sources_live():
    db = SessionLocal()
    try:
        active_sources = db.query(Source).filter(Source.active == True).order_by(Source.id.asc()).all()
        print(f"Auditing {len(active_sources)} active sources live...")
        
        results = []
        reachable_count = 0
        failed_count = 0
        zero_entries_count = 0
        http_errors_count = 0
        timeout_count = 0
        parser_failures_count = 0
        
        for idx, src in enumerate(active_sources, 1):
            print(f"[{idx:02d}/{len(active_sources):02d}] Fetching ID {src.id}: '{src.name}' ({src.feed_url})...", end="", flush=True)
            start_t = time.time()
            
            status = "UNKNOWN"
            error_msg = None
            items = []
            
            if not src.feed_url:
                status = "FAILED_MISSING_URL"
                error_msg = "No feed_url configured"
                failed_count += 1
            else:
                try:
                    items = fetch_feed(src.feed_url, src.name)
                    elapsed = time.time() - start_t
                    if len(items) > 0:
                        status = "REACHABLE_OK"
                        reachable_count += 1
                        print(f" OK ({len(items)} items in {elapsed:.2f}s)")
                    else:
                        status = "ZERO_ENTRIES"
                        zero_entries_count += 1
                        print(f" ZERO_ENTRIES in {elapsed:.2f}s")
                except urllib.error.HTTPError as he:
                    status = f"HTTP_ERROR_{he.code}"
                    error_msg = str(he)
                    http_errors_count += 1
                    failed_count += 1
                    print(f" HTTP_ERROR {he.code}")
                except (urllib.error.URLError, TimeoutError, socket.timeout) as te:
                    status = "TIMEOUT_OR_NETWORK_ERROR"
                    error_msg = str(te)
                    timeout_count += 1
                    failed_count += 1
                    print(f" TIMEOUT/NET_ERROR: {te}")
                except Exception as exc:
                    status = "PARSER_FAILURE"
                    error_msg = str(exc)
                    parser_failures_count += 1
                    failed_count += 1
                    print(f" PARSER_FAILURE: {exc}")
                    
            latest_pub = max([i.published_at for i in items if i.published_at], default=None) if items else None
            
            results.append({
                "source_id": src.id,
                "name": src.name,
                "feed_url": src.feed_url,
                "status": status,
                "error_message": error_msg,
                "items_fetched": len(items),
                "latest_item_published": latest_pub.isoformat() if latest_pub else None
            })
            
        print("\n" + "=" * 70)
        print("SOURCE AUDIT SUMMARY")
        print("=" * 70)
        print(f"Total Active Sources Configured: {len(active_sources)}")
        print(f"Reachable Sources (with items): {reachable_count}")
        print(f"Sources Returning Zero Entries: {zero_entries_count}")
        print(f"Failed Sources: {failed_count}")
        print(f"  HTTP Errors: {http_errors_count}")
        print(f"  Timeout/Network Errors: {timeout_count}")
        print(f"  Parser Failures: {parser_failures_count}")
        
        output_path = "scratch/source_audit_live_results.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved raw audit details to {output_path}")

    finally:
        db.close()

if __name__ == "__main__":
    audit_active_sources_live()
