"""Step 8 checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step8.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from stockwise import config
from stockwise.features import build_features, training_frame
from stockwise.schema import validate_sales


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


raw = pd.read_csv(config.DATA_DIR / "sample_sales_upload.csv")
print("Uploaded file:", raw.shape, "| columns:", list(raw.columns), "\n")

# --- 1. A normal upload ---
res = validate_sales(raw)
check(res.ok, "normal upload is accepted")
print("  warnings:", res.warnings or "none")
n_items = res.items["item_id"].nunique()
added = len(res.data) - len(raw)
check(added >= 0 and n_items == raw["item_id"].nunique(), f"{n_items} items, no rows lost ({added:,} gap day(s) filled)")
print(res.items["mode"].value_counts().to_string(), "\n")

# --- 2. Features ---
feat = build_features(res.data)
train = training_frame(feat)
check(all(c in feat.columns for c in config.FEATURE_COLUMNS), "all feature columns exist")
check(len(train) == len(res.data) - 28 * n_items,
      f"{len(train):,} training rows (first 28 days of each item dropped)")
check(not train[config.FEATURE_COLUMNS].isna().any().any(), "no missing values in training rows")

# --- 3. No leakage: changing today's sales must not change today's features ---
data = res.data
first_item = data["item_id"].iloc[0]
pos = data.index[data["item_id"] == first_item][100]
changed = data.copy()
changed.loc[pos, "units_sold"] += 50
feat2 = build_features(changed)
cols = config.FEATURE_COLUMNS
check(feat.loc[pos, cols].equals(feat2.loc[pos, cols]), "today's features ignore today's sales (no leakage)")
check(feat.loc[pos + 1, "roll7"] != feat2.loc[pos + 1, "roll7"], "tomorrow's features do use today's sales")

# --- 4. Bad files give clear messages instead of crashing ---
r = validate_sales(raw.drop(columns=["units_sold"]))
check((not r.ok) and "units_sold" in r.errors[0], "missing column is reported: " + (r.errors[0] if r.errors else ""))

renamed = raw.rename(columns={"item_id": "SKU", "date": "Sale Date", "units_sold": "Qty", "price": "Unit Price"})
check(validate_sales(renamed).ok, "common alternative column names are understood (SKU, Sale Date, Qty, Unit Price)")

item0 = raw["item_id"].iloc[0]
extra = pd.DataFrame([
    {"item_id": item0, "date": "not-a-date", "units_sold": 3, "price": 2.5, "category": "X", "event": 0},
    {"item_id": item0, "date": raw["date"].iloc[0], "units_sold": -4, "price": 2.5, "category": "X", "event": 0},
])
r = validate_sales(pd.concat([raw.head(50), extra], ignore_index=True))
check(r.ok and len(r.warnings) >= 3, "bad date, negative units and a duplicate are fixed with warnings")
for w in r.warnings:
    print("  -", w)

print("\nALL CHECKS PASSED")