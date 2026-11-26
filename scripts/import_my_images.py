r"""Imports your own product photos (named by product, e.g. "basmati rice.jpg") from Major Project\images.
Usage: python scripts\import_my_images.py [folder]"""
import csv
import difflib
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "images"
OUT = ROOT / "data" / "product_images"
MANUAL = ROOT / "data" / "product_images_manual"
OUT.mkdir(parents=True, exist_ok=True)
MANUAL.mkdir(parents=True, exist_ok=True)
EXT = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp", ".gif"}


def norm(s):
    s = s.lower().replace("woollen", "woolen").replace("chilly", "chilli")
    return re.sub(r"[^a-z0-9]", "", s)


index = {}
for iid, c in catalog.CATALOG.items():
    names = {c["name"], re.sub(r"\(.*?\)", "", c["name"]), iid}
    names.update(re.findall(r"\((.*?)\)", c["name"]))
    for n in names:
        k = norm(n)
        if k:
            index.setdefault(k, iid)

if not SRC.exists():
    sys.exit(f"Folder not found: {SRC}")

done, unmatched, close, unreadable, seen = {}, [], [], [], {}
for f in sorted(SRC.iterdir()):
    if f.suffix.lower() not in EXT:
        continue
    stem = re.sub(r"\s*\(\d+\)$", "", f.stem).strip()
    k = norm(stem)
    iid, how = index.get(k), "exact"
    if iid is None:
        m = difflib.get_close_matches(k, list(index), n=1, cutoff=0.86)
        if m:
            iid, how = index[m[0]], "close"
    if iid is None:
        unmatched.append(f.name)
        continue
    try:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((480, 480))
        im.save(OUT / f"{iid}.jpg", "JPEG", quality=88)
        im.save(MANUAL / f"{iid}.jpg", "JPEG", quality=88)
    except Exception as e:
        unreadable.append(f"{f.name} ({e.__class__.__name__})")
        continue
    if iid in seen:
        print(f"WARNING: {f.name} and {seen[iid]} both match {iid}; kept {f.name}")
    seen[iid] = f.name
    done[iid] = f.name
    label = catalog.CATALOG[iid]["name"]
    print(f"{'OK   ' if how == 'exact' else 'CLOSE'} {f.name:34} -> {iid:16} {label}")
    if how == "close":
        close.append(f"{f.name} -> {label}")

rp = OUT / "_report.csv"
rows = {r[0]: r for r in csv.reader(open(rp, encoding="utf-8"))} if rp.exists() else {}
for iid, c in catalog.CATALOG.items():
    rows.setdefault(iid, [iid, c["name"], "kept"])
    rows[iid][1] = c["name"]
    if iid in done:
        rows[iid][2] = "manual"
with open(rp, "w", newline="", encoding="utf-8") as fh:
    csv.writer(fh).writerows(sorted(rows.values()))

none = [i for i in catalog.CATALOG if not (OUT / f"{i}.jpg").exists()]
print(f"\nImported {len(done)} of {len(catalog.CATALOG)} items from {SRC}")
print("UNMATCHED files (name does not match any product):", unmatched or "none")
print("CLOSE matches, please confirm:", close or "none")
print("COULD NOT READ:", unreadable or "none")
print("Items still with NO picture:", none or "none")