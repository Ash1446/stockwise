"""Step 11 checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step11.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from stockwise import config, db
from stockwise.pipeline import run_pipeline


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


def counts(path):
    return {t: len(db.read_table(t, path)) for t in db.TABLES}


TMP = config.DATA_DIR / "test_stockwise.db"
TMP2 = config.DATA_DIR / "test_stockwise_short.db"
for p in (TMP, TMP2):
    if p.exists():
        p.unlink()

raw = pd.read_csv(config.DATA_DIR / "sample_sales_upload.csv")

# --- 1. A normal upload ends up in the database ---
out = run_pipeline(raw, TMP)
check(out["ok"], f"pipeline finished in {out['seconds']}s")
c = counts(TMP)
print("  rows per table:", c)
check(c["items"] == 100 and c["sales"] == 155950, "100 items and 155,950 sales rows stored")
check(c["expected_demand"] == 16800 and c["forecasts"] == 700, "16,800 expected-demand rows and 700 forecast rows stored")
sales = db.read_table("sales", TMP)
check(abs(sales["units_sold"].sum() - raw["units_sold"].sum()) < 1e-6, "total units sold survive the round trip")
check(sales["date"].min() == pd.to_datetime(raw["date"]).min(), "dates are stored and read back correctly")
fc = db.read_table("forecasts", TMP)
check(fc["forecast"].notna().all() and (fc["forecast"] >= 0).all(), "stored forecasts are present and non-negative")

# --- 2. Uploading the same file again does not duplicate anything ---
run_pipeline(raw, TMP)
check(counts(TMP) == c, "re-upload gives identical row counts (no duplicates)")

# --- 3. Counts and investigations can be saved and corrected ---
cnt = pd.DataFrame({"item_id": ["A", "A", "B"], "date": ["2026-01-01", "2026-01-02", "2026-01-01"],
                    "counted_stock": [10.0, 9.0, 5.0]})
db.upsert("stock_counts", cnt, TMP)
cnt.loc[0, "counted_stock"] = 12.0
db.upsert("stock_counts", cnt, TMP)
sc = db.read_table("stock_counts", TMP)
check(len(sc) == 3 and sc.loc[(sc["item_id"] == "A") & (sc["date"] == "2026-01-01"), "counted_stock"].iloc[0] == 12.0,
      "a corrected stock count replaces the old value")
db.set_investigation("A", "2026-01-01", "investigated", "checked the shelf", path=TMP)
db.set_investigation("A", "2026-01-01", "open", "reopened", path=TMP)
inv = db.read_table("investigations", TMP)
check(len(inv) == 1 and inv["status"].iloc[0] == "open", "investigation status updates in place")

# --- 4. A bad file is rejected and the database is untouched ---
before = counts(TMP)
bad = run_pipeline(raw.drop(columns=["units_sold"]), TMP)
check((not bad["ok"]) and bad["errors"], "bad file is rejected: " + (bad["errors"][0] if bad["errors"] else ""))
check(counts(TMP) == before, "database is unchanged after a rejected upload")

# --- 5. A store where every item has short history still works ---
parts = [raw[raw["item_id"] == i].head(40) for i in raw["item_id"].unique()[:3]]
out2 = run_pipeline(pd.concat(parts, ignore_index=True), TMP2)
check(out2["ok"] and out2["model_items"] == 0 and out2["fallback_items"] == 3, "3 short-history items accepted, all on the fallback")
fc2 = db.read_table("forecasts", TMP2)
check(len(fc2) == 21 and (fc2["method"] == "fallback").all() and fc2["forecast"].notna().all(),
      "21 fallback forecasts stored (3 items x 7 days)")

for p in (TMP, TMP2):
    p.unlink()
print("\nALL CHECKS PASSED")