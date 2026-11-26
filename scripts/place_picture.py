r"""Usage: python scripts\place_picture.py <picture file> <item_id>
Saves your picture as the item's picture (kept in data\product_images_manual so it is never overwritten)."""
import csv
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

src, iid = Path(sys.argv[1]), sys.argv[2]
im = Image.open(src)
im.load()
im = im.convert("RGB")
dest = ROOT / "data" / "product_images_manual" / f"{iid}.jpg"
dest.parent.mkdir(parents=True, exist_ok=True)
im.save(dest, "JPEG", quality=90)
print("saved", dest.name, im.size, "->", catalog.CATALOG[iid]["name"])
rp = ROOT / "data" / "product_images" / "_report.csv"
if rp.exists():
    rows = list(csv.reader(open(rp, encoding="utf-8")))
    for r in rows:
        if r[0] == iid:
            r[1], r[2] = catalog.CATALOG[iid]["name"], "manual"
    csv.writer(open(rp, "w", newline="", encoding="utf-8")).writerows(rows)