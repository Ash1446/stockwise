"""Downloads the lead-photo address for every product title from Wikipedia once, into data\photos.json."""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

out = ROOT / "data" / "photos.json"
cache = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
titles = sorted({c["wiki"] for c in catalog.CATALOG.values()})
for t in titles:
    if cache.get(t):
        continue
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "StockwiseStudentProject/1.0 (college project)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.load(r)
        cache[t] = (j.get("thumbnail") or {}).get("source")
    except Exception as e:
        cache[t] = None
        print("ERR", t, e)
    time.sleep(0.15)
out.write_text(json.dumps(cache, indent=1), encoding="utf-8")
missing = [t for t in titles if not cache.get(t)]
print(f"{len(titles) - len(missing)} of {len(titles)} photo titles found")
if missing:
    print("NO PHOTO for:", missing)