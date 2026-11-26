"""Downloads one real photo per catalogue item into data/product_images (JPEG, max 480 px).
Order: your own file in data/product_images_manual, then the Wikipedia article photo, then a Wikipedia search."""
import csv
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

OUT = ROOT / "data" / "product_images"
MANUAL = ROOT / "data" / "product_images_manual"
OUT.mkdir(parents=True, exist_ok=True)
MANUAL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "StockwiseStudentProject/1.0 (college project)"}
API = "https://en.wikipedia.org/w/api.php"
BAD = (".svg", "flag_of", "commons-logo", "wiktionary", "disambig")


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def api(params):
    q = dict(params, format="json", formatversion="2")
    raw = get(API + "?" + urllib.parse.urlencode(q))
    return json.loads(raw) if raw else {}


def ok_url(u):
    return bool(u) and not any(b in u.lower() for b in BAD)


def title_thumb(title):
    j = api({"action": "query", "titles": title, "prop": "pageimages", "piprop": "thumbnail",
             "pithumbsize": 600, "redirects": 1})
    for p in j.get("query", {}).get("pages", []):
        u = (p.get("thumbnail") or {}).get("source")
        if ok_url(u):
            return u
    return None


def search_thumb(query):
    j = api({"action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 0,
             "gsrlimit": 6, "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": 600})
    pages = sorted(j.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
    for p in pages:
        u = (p.get("thumbnail") or {}).get("source")
        if ok_url(u):
            return p["title"], u
    return None


def save_jpeg(raw, dest):
    im = Image.open(io.BytesIO(raw))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if im.width < 120 or im.height < 120:
        return False
    im.thumbnail((480, 480))
    im.save(dest, "JPEG", quality=85)
    return True


report = []
for iid, c in sorted(catalog.CATALOG.items()):
    dest = OUT / f"{iid}.jpg"
    source = "MISSING"
    manual = next((p for p in MANUAL.glob(f"{iid}.*")), None)
    if manual and save_jpeg(manual.read_bytes(), dest):
        source = "manual"
    elif dest.exists():
        old = {r[0]: r[2] for r in csv.reader(open(OUT / "_report.csv", encoding="utf-8"))} if (OUT / "_report.csv").exists() else {}
        source = old.get(iid, "kept")
    else:
        url, how = title_thumb(c["wiki"]), "wikipedia: " + c["wiki"]
        if not url:
            for q in dict.fromkeys([c["name"], c["name"].split("(")[0].strip()]):
                hit = search_thumb(q)
                if hit:
                    how, url = "SEARCH: " + hit[0], hit[1]
                    break
        raw = get(url) if url else None
        if raw and save_jpeg(raw, dest):
            source = how
        time.sleep(0.25)
    report.append((iid, c["name"], source))
    print(f"{iid:16} {c['name']:28} {source}")

with open(OUT / "_report.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(report)

missing = [r[0] for r in report if r[2] == "MISSING"]
searched = [r[0] for r in report if r[2].startswith("SEARCH")]
print(f"\n{len(report) - len(missing)} of {len(report)} items have a picture")
print("MISSING (add your own in data/product_images_manual):", missing or "none")
print("CHECK THESE, found by search so more likely wrong:", searched or "none")