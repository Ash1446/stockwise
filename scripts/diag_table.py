import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

hits = [i for i, c in catalog.CATALOG.items() if "table" in c["name"].lower() or "plate" in c["name"].lower()]
print("catalogue entries:", [(i, catalog.CATALOG[i]["name"]) for i in hits])
src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
found = False
if src and src.exists():
    for f in sorted(src.iterdir()):
        n = f.name.lower()
        if "table" in n or "plate" in n or "dinner" in n:
            found = True
            try:
                im = Image.open(f)
                im.load()
                print("file:", f.name, "-> opens OK", im.size)
            except Exception as e:
                print("file:", f.name, "-> CANNOT OPEN:", type(e).__name__, str(e)[:80])
if not found:
    print("no file with table/plate/dinner in its name in your pictures folder")
for i in hits:
    p = ROOT / "data" / "product_images" / f"{i}.jpg"
    print(i, "picture in app folder:", p.exists())