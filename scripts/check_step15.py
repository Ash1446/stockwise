"""Step 15 checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step15.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from stockwise import config, db
from stockwise.settings import default_settings, ensure_item_settings


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


if not db.DB_PATH.exists() or db.DB_PATH.stat().st_size < 1_000_000:
    raise SystemExit("data\\stockwise.db is missing. Run build_sample_db.py first.")

TMP = config.DATA_DIR / "test_stockwise.db"
shutil.copy(db.DB_PATH, TMP)                       # work on a copy

# --- 1. New tables are added without touching existing data ---
db.init_db(TMP)
sizes = {t: len(db.read_table(t, TMP)) for t in db.TABLES}
new = ["item_settings", "users", "transactions", "transaction_items", "write_offs", "audit_log", "day_close"]
check(all(t in sizes for t in new), "all 7 new tables exist")
check(sizes["items"] == 100 and sizes["sales"] == 155950 and sizes["expected_demand"] == 16800,
      "existing data is untouched (100 items, 155,950 sales rows, 16,800 expected-demand rows)")

# --- 2. Demo defaults ---
items = db.read_table("items", TMP)
sales = db.read_table("sales", TMP)
fc = db.read_table("forecasts", TMP)
d = default_settings(items, sales, fc, demo=True)
m = d.merge(items[["item_id", "category"]], on="item_id")
food = m["category"].str.upper().str.startswith("FOODS")
check(len(d) == 100 and d["item_id"].is_unique, "one settings row per item")
check(m.loc[~food, "perishable"].sum() == 0, "no non-food item is perishable")
share = m.loc[food, "perishable"].mean()
check(0.15 <= share <= 0.45, f"{share:.0%} of food items are perishable (demo assumption)")
check(set(d.loc[d["perishable"] == 1, "shelf_life_days"]) <= {2.0, 3.0}, "perishable shelf lives are 2 or 3 days")
check(d.loc[d["perishable"] == 0, "shelf_life_days"].isna().all(), "non-perishables have no shelf life")
check((d["min_stock"] >= 1).all() and (d["target_stock"] > d["min_stock"]).all(), "required stock is always above minimum stock")
lim = d["purchase_limit"].notna()
check(8 <= lim.sum() <= 14 and (d.loc[lim, "purchase_limit"] == 5).all(), f"{int(lim.sum())} high-demand items get a limit of 5 per bill")
check(default_settings(items, sales, fc, demo=True).equals(d), "defaults are repeatable")

# --- 3. Real-store defaults invent nothing ---
d0 = default_settings(items, sales, fc, demo=False)
check(d0["perishable"].sum() == 0 and d0["purchase_limit"].isna().all(), "real-store defaults: no invented perishables or limits")

# --- 4. Saving, keeping the admin's edits, and filling gaps ---
check(ensure_item_settings(TMP, demo=True) == 100, "100 settings rows created")
check(ensure_item_settings(TMP, demo=True) == 0, "running it again changes nothing")
first = items["item_id"].iloc[0]
db.upsert("item_settings", pd.DataFrame([{"item_id": first, "perishable": 0, "shelf_life_days": np.nan,
                                          "min_stock": 99.0, "target_stock": 300.0, "purchase_limit": np.nan}]), TMP)
ensure_item_settings(TMP, demo=True)
kept = db.read_table("item_settings", TMP).set_index("item_id").loc[first, "min_stock"]
check(kept == 99.0, "an admin's edit is kept when defaults are filled in")
with db.connect(TMP) as con:
    con.execute("DELETE FROM item_settings WHERE item_id = ?", (first,))
check(ensure_item_settings(TMP, demo=True) == 1, "a missing item gets its settings back")
ensure_item_settings(TMP, demo=True, overwrite=True)
check(db.read_table("item_settings", TMP).set_index("item_id").loc[first, "min_stock"] != 99.0,
      "overwrite resets everything to the defaults")

TMP.unlink()
print("\nALL CHECKS PASSED")