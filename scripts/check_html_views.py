"""Checks the HTML-look Demand forecast and Shrinkage pages."""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
failed = False
def chk(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + str(extra)) if (extra and not ok) else ""))
    failed = failed or not ok

from app import htmlviews
from app.views import forecast
pl = forecast.build_payload()
chk("forecast data covers many items", len(pl["items"]) >= 90, len(pl["items"]))
chk("every item has 7 forecast days and a name", all(len(i["fc"]) == 7 and i["name"] for i in pl["items"]))
chk("history is at most 60 days", all(0 < len(i["hist"]) <= 60 for i in pl["items"]))
page = htmlviews.forecast_page(pl)
chk("forecast page built with the real data", "const FC = {" in page and "__FC__" not in page and "fc-product" in page)
sh = {"flagged": 1, "items": 1, "expected": 10, "counted": 5, "variance": -5, "value": "\u20b950",
      "rows": [{"id": "X", "name": "Test", "category": "Foods", "date": "01 Jan 2016", "opening": 20, "received": 0,
                "sold": 5, "expected": 10, "counted": 5, "severity": "High", "review": "Open"}]}
chk("shrinkage page built", "const SH = {" in htmlviews.shrinkage_page(sh) and "__SH__" not in htmlviews.shrinkage_page(sh))

from streamlit.testing.v1 import AppTest
for role, user in (("Admin", "admin@demo.io"), ("Cashier", "cashier@demo.io")):
    for nav in ("Demand forecast", "Shrinkage detection"):
        at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
        at.session_state["user"] = {"username": user, "role": role}
        at.session_state["nav"] = nav
        at.run()
        errs = [e.value for e in at.exception]
        chk(f"{role}: {nav} opens", not errs, errs)
sys.exit(1 if failed else 0)