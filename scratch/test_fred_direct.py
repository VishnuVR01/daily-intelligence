import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
})

try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        print(f"Status: {resp.status}")
        data = resp.read().decode('utf-8')
        lines = data.strip().split('\n')
        print(f"Total lines: {len(lines)}")
        print("First 5 lines:")
        for line in lines[:5]:
            print("  ", line)
        print("Last 5 lines:")
        for line in lines[-5:]:
            print("  ", line)
except Exception as exc:
    print(f"Error: {exc}")
