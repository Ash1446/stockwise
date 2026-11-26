"""Writes scripts/image_sheet.html: each item with its picture, name, pack and rupee price, to check by eye."""
import csv
import time
import html
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog, images

rep = {}
rp = ROOT / "data" / "product_images" / "_report.csv"
if rp.exists():
    rep = {r[0]: r[2] for r in csv.reader(open(rp, encoding="utf-8"))}

parts = []
for g in catalog.GROUPS:
    parts.append(f"<h2>{g}</h2><div class='grid'>")
    for iid, c in sorted(catalog.CATALOG.items()):
        if c["group"] != g:
            continue
        has = images.path(iid) is not None
        pic = (f"<img src='../data/product_images/{iid}.jpg?v={int(time.time())}' alt=''>" if has
               else "<div class='no'>NO PICTURE</div>")
        src = rep.get(iid, "")
        flag = " flag" if src.startswith("SEARCH") or not has else ""
        parts.append(f"<div class='c{flag}'><div class='t'>{pic}</div><b>{html.escape(c['name'])}</b>"
                     f"<div>{html.escape(c['pack'])} &middot; Rs {c['price']:,}</div>"
                     f"<small>{iid}<br>{html.escape(src)}</small></div>")
    parts.append("</div>")
page = ("<!doctype html><meta charset='utf-8'><title>Image check</title><style>"
        "body{font-family:Segoe UI,Arial;margin:24px;background:#f7f8fa}h2{margin:28px 0 10px}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}"
        ".c{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:10px;font-size:13px}"
        ".c.flag{border:2px solid #f59e0b}"
        ".t{height:130px;background:#eef1f5;border-radius:8px;overflow:hidden;margin-bottom:8px;display:grid;place-items:center}"
        ".t img{width:100%;height:100%;object-fit:contain}.no{color:#b91c1c;font-weight:700}"
        "small{color:#6b7686}</style><h1>Does each picture match its name?</h1>"
        "<p>Orange border = found by search or missing, check these first.</p>" + "".join(parts))
dest = ROOT / "scripts" / "image_sheet.html"
dest.write_text(page, encoding="utf-8")
print("wrote", dest)
os.startfile(dest)