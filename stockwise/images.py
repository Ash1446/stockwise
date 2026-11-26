"""Local product pictures (in data/product_images)."""
import base64
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "product_images"


def path(item_id):
    p = DIR / f"{item_id}.jpg"
    return p if p.exists() else None


@lru_cache(maxsize=None)
def data_uri(item_id):
    p = path(item_id)
    if p is None:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


@lru_cache(maxsize=None)
def thumb_uri(item_id, width=300, height=200):
    """Small version of the picture, embedded straight into the page."""
    p = path(item_id)
    if p is None:
        return None
    with Image.open(p) as im:
        im = im.convert("RGB")
        im.thumbnail((width, height))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=74)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")