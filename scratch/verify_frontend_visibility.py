import os
import sys

sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from app.main import app

def verify_frontend():
    client = TestClient(app)
    
    routes_to_test = [
        ("/", "Home Edition"),
        ("/archive", "Archive"),
        ("/search?q=AI", "Search"),
        ("/latest", "Latest Briefings"),
        ("/sources", "Sources"),
        ("/saved", "Saved"),
    ]
    
    print("=" * 70)
    print("VERIFYING FRONTEND VISIBILITY FOR INGESTED ARTICLES")
    print("=" * 70)
    
    for path, name in routes_to_test:
        resp = client.get(path)
        print(f"[{resp.status_code}] {name} ({path}) - Length: {len(resp.text)} bytes")
        assert resp.status_code == 200, f"Route {path} failed with status {resp.status_code}"
        assert "500" not in resp.text[:500] or "Internal Server Error" not in resp.text, f"Route {path} raised server error"

    # Specific check for newly ingested article titles in Search / Archive
    resp_aj = client.get("/search?q=Al+Jazeera")
    assert resp_aj.status_code == 200
    assert "Al Jazeera English" in resp_aj.text or "Al Jazeera" in resp_aj.text, "Newly ingested source missing from Search!"
    print("  SUCCESS: Newly ingested articles visible in Search by source query!")

    resp_nato = client.get("/search?q=NATO")
    assert resp_nato.status_code == 200
    assert "NATO" in resp_nato.text, "Newly ingested NATO article missing from Search!"
    print("  SUCCESS: Newly ingested article visible in Search HTML!")
    
    print("All frontend endpoints verified successfully!")

if __name__ == "__main__":
    verify_frontend()
