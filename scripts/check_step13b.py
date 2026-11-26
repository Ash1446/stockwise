"""Step 13b checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step13b.py
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from stockwise import config, db
from stockwise.counts import run_detection, validate_counts


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


def note(condition, message):
    print(("PASS  " if condition else "NOTE  ") + message)


if not db.DB_PATH.exists() or db.DB_PATH.stat().st_size < 1_000_000:
    raise SystemExit("data\\stockwise.db is missing. Run build_sample_db.py and load_demo_counts.py first.")

# --- 1. Counts-file validation ---
raw = pd.DataFrame({"Item": ["A", "A", "B", "Z", "B", "A"],
                    "Date": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-01", "not a date", "2026-01-01"],
                    "Counted": [10, 9, -1, 5, 3, 11], "Received": [0, 2, 0, 0, 0, 0]})
c, d, errs, warns = validate_counts(raw, {"A", "B"})
check(not errs and len(c) == 2, "messy counts file is cleaned down to 2 usable counts")
check(c.loc[(c["item_id"] == "A") & (c["date"] == "2026-01-01"), "counted_stock"].iloc[0] == 11, "duplicate keeps the last value")
check(len(warns) == 3 and d["units"].sum() == 2, "3 warnings (bad rows, unknown item, duplicate) and deliveries are kept")
_, _, errs, _ = validate_counts(pd.DataFrame({"item_id": ["A"], "date": ["2026-01-01"]}), {"A"})
check(bool(errs) and "counted_stock" in errs[0], "missing column is reported: " + errs[0])

# --- 2. One count in, one answer out (on a copy of the database) ---
TMP = config.DATA_DIR / "test_stockwise.db"
shutil.copy(db.DB_PATH, TMP)
items = db.read_table("items", TMP)
counts = db.read_table("stock_counts", TMP)
fc = db.read_table("forecasts", TMP)
last = counts.sort_values("date").groupby("item_id").tail(1).set_index("item_id")
cand = (items.set_index("item_id").join(last[["date", "counted_stock"]])
        .query("counted_stock > 150").sort_values("mean_daily_units"))
item = cand.index[0]
prev = float(cand.loc[item, "counted_stock"])
day = cand.loc[item, "date"] + pd.Timedelta(days=1)
row = fc[(fc["item_id"] == item) & (fc["date"] == day)]
check(len(row) == 1, f"a forecast exists for {item} on {day:%d %b %Y}")
expected = float(row["forecast"].iloc[0])
before = len(db.read_table("detections", TMP))


def enter(counted):
    db.upsert("stock_counts", pd.DataFrame([{"item_id": item, "date": day, "counted_stock": counted}]), TMP)
    db.upsert("deliveries", pd.DataFrame([{"item_id": item, "date": day, "units": 0.0}]), TMP)
    det = run_detection("forecast", path=TMP, items=[item])
    return det[(det["item_id"] == item) & (det["date"] == day)].iloc[0]


r = enter(round(prev - expected))
check(r["flag"] == 0, f"a normal count (drop = expected demand of {expected:.1f}) is not flagged")
r = enter(prev - round(expected) - 40)
check(r["flag"] == 1 and 30 <= r["est_missing_units"] <= 50,
      f"a count 40 units too low is flagged ({r['severity']} severity, about {r['est_missing_units']:.0f} units)")
check(len(db.read_table("detections", TMP)) == before + 1, "re-checking one item adds one row and leaves the others alone")

full = run_detection(path=TMP, save=False)
sub = run_detection(path=TMP, save=False, items=[item])
a = full[full["item_id"] == item].reset_index(drop=True)
check(len(a) == len(sub) and np.allclose(a["z"], sub["z"], equal_nan=True), "single-item check gives the same scores as the full run")
TMP.unlink()

# --- 3. The app itself, driven page by page ---
def no_errors(at, label):
    if at.exception:
        print("      error:", [e.value for e in at.exception][:2])
    check(not at.exception, label)


try:
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=120)
    at.session_state["logged_in"] = True
    at.run()
    no_errors(at, "Dashboard renders without errors")
    for name in ["Inventory", "Stock counts", "Demand forecast", "Shrinkage detection", "Upload data"]:
        at.sidebar.radio(key="nav").set_value(name).run()
        no_errors(at, f"{name} page renders without errors")

    at.sidebar.radio(key="nav").set_value("Inventory").run()
    views = [b for b in at.button if b.key and str(b.key).startswith("view_")]
    check(len(views) == 24, f"Inventory shows 24 item cards on the first page ({len(views)} found)")
    views[0].click().run()
    no_errors(at, "an item page opens without errors")
    [b for b in at.button if "Enter a count" in b.label][0].click().run()
    no_errors(at, "'Enter a count' jumps to Stock counts without errors")
    check(at.session_state["nav"] == "Stock counts" and at.session_state["count_item"], "...and passes the item along")
except Exception as e:
    note(False, f"the app test could not run ({type(e).__name__}: {e}). Open the app by hand instead.")

print("\nALL CHECKS PASSED")