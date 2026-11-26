r"""Puts every product picture on a 600x400 canvas with the whole product visible (nothing cropped).
Originals come from data\product_images_manual when present. Safe to run again."""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

OUT = ROOT / "data" / "product_images"
MANUAL = ROOT / "data" / "product_images_manual"
W, H = 600, 400
RES = getattr(Image, "Resampling", Image).LANCZOS


def pad(src, dest):
    with Image.open(src) as im0:
        im = im0.convert("RGB")
    px = [im.getpixel(p) for p in [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)]]
    bg = tuple(sum(c[i] for c in px) // 4 for i in range(3))
    scale = min(H / im.height, H / im.width)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), RES)
    canvas = Image.new("RGB", (W, H), bg)
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    canvas.save(dest, "JPEG", quality=88)


done = skipped = 0
for iid in catalog.CATALOG:
    m, o = MANUAL / f"{iid}.jpg", OUT / f"{iid}.jpg"
    src = m if m.exists() else (o if o.exists() else None)
    if src is None:
        continue
    if src == o:
        with Image.open(o) as t:
            if t.size == (W, H):
                skipped += 1
                continue
    pad(src, o)
    done += 1
print(f"padded {done} pictures, {skipped} were already done")