"""Builds the HTML Dashboard and Shop pages for both roles and checks the data and the page script."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app import htmlpage
from streamlit.testing.v1 import AppTest

failed = False


def chk(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + str(extra)) if (extra and not ok) else ""))
    failed = failed or not ok


d = htmlpage.real_data("Admin", "dashboard")
cat = d["catalog"]
chk("99 items in the page data", len(cat) == 99, f"found {len(cat)}")
chk("the hidden table set is not in the page", all(p["id"] != "HOUSEHOLD_2_483" for p in cat))
chk("product names are unique", len({p["name"] for p in cat}) == len(cat))
chk("all prices are positive rupee amounts", all(p["price"] > 0 for p in cat))
chk("every status is one the page understands",
    all(p["status"] in {"Healthy", "Low stock", "Out of stock", "No count"} for p in cat))
missing = [p["id"] for p in cat if not p["img"]]
chk("every item has a picture", not missing, f"no picture: {missing}")
pl = d["pulse"]
chk("demand chart has 14 matching days", len(pl["actual"]) == len(pl["pred"]) == len(pl["labels"]) == 14, {k: len(v) for k, v in pl.items()})
print("INFO  items with no stock count:", sum(p["status"] == "No count" for p in cat))
print("INFO  statuses:", {s: sum(p["status"] == s for p in cat) for s in {p["status"] for p in cat}})

pages = {}
for role in ("Admin", "Cashier"):
    for view in ("dashboard", "shop"):
        try:
            page = htmlpage.build(view, role)
        except Exception as e:
            chk(f"{role} {view}: page builds", False, e)
            continue
        pages[(role, view)] = page
        ok = ("__realInit();" in page and "const REAL =" in page and "__REAL__" not in page
              and "renderShrinkage(); renderQueue(); loadPhotos();" not in page)
        chk(f"{role} {view}: page built ({len(page) // 1024} KB)", ok)

node = shutil.which("node")
if node and pages:
    js = re.search(r"<script>(.*)</script>", next(iter(pages.values())), re.S).group(1)
    tmp = Path(tempfile.gettempdir()) / "sw_page_check.js"
    tmp.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
    chk("page script has no syntax errors", r.returncode == 0, r.stderr[:300])
else:
    print("SKIP  page script syntax check (node is not installed)")

for role, user, nav in [("Admin", "admin@demo.io", "Dashboard"), ("Admin", "admin@demo.io", "Shop"),
                        ("Cashier", "cashier@demo.io", "Shop")]:
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
    at.session_state["user"] = {"username": user, "role": role}
    at.session_state["nav"] = nav
    at.run()
    errs = [e.value for e in at.exception]
    chk(f"{role}: {nav} page opens in the app", not errs, "; ".join(errs))

sys.exit(1 if failed else 0)