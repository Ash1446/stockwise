"""Step 9 checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step9.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from stockwise import config
from stockwise.features import build_features, training_frame
from stockwise.forecast import fit_model, forecast_next_days, rolling_forecast
from stockwise.metrics import accuracy_table
from stockwise.schema import validate_sales


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


def note(condition, message):
    print(("PASS  " if condition else "NOTE  ") + message)


raw = pd.read_csv(config.DATA_DIR / "sample_sales_upload.csv")
v = validate_sales(raw)
feat = build_features(v.data)
print("Items:", v.items["item_id"].nunique(), "| rows:", len(feat), "\n")

# --- 1. Rolling backtest (same protocol as Colab Steps 2 and 5) ---
t0 = time.time()
res = rolling_forecast(feat)
print(f"Backtest took {time.time() - t0:.0f}s")
check(len(res) == 16800, f"{len(res):,} out-of-sample rows (expect 16,800)")
check(res.groupby("block").size().eq(2800).all(), "6 blocks of 2,800 rows")
check(not res["pred"].isna().any() and (res["pred"] >= 0).all(), "forecasts are present and never negative")
check((res["method"] == "model").all(), "all 100 items forecast by the model")

tab = accuracy_table(res, {"Naive: same day last week": "lag7",
                           "Baseline: 28-day rolling mean": "roll28",
                           "XGBoost (module)": "pred"})
print("\n" + tab.round(3).to_string(index=False) + "\n")
mae = tab.set_index("model")["MAE"]
check(abs(mae["Naive: same day last week"] - 1.250) < 0.0015
      and abs(mae["Baseline: 28-day rolling mean"] - 1.031) < 0.0015,
      "baselines reproduce Colab exactly (lag7 1.250, rolling mean 1.031)")
note(mae["XGBoost (module)"] < mae["Baseline: 28-day rolling mean"], "XGBoost beats the rolling-mean baseline")
note(abs(mae["XGBoost (module)"] - 0.999) < 0.05, "XGBoost MAE is close to Colab's 0.999")

# --- 2. Next-7-day forecast ---
t0 = time.time()
model = fit_model(training_frame(feat))
fut = forecast_next_days(v.data, v.items, model, horizon=7)
print(f"\nTraining and 7-day forecast took {time.time() - t0:.0f}s")
check(len(fut) == 100 * 7, f"{len(fut)} forecast rows (100 items x 7 days)")
check(not fut["forecast"].isna().any() and (fut["forecast"] >= 0).all(), "forecasts present and non-negative")
last_dates = v.items.set_index("item_id")["last_date"]
first = fut[fut["day_ahead"] == 1].set_index("item_id")["date"]
check((first == last_dates.reindex(first.index) + pd.Timedelta(days=1)).all(),
      "each forecast starts the day after the item's last date")
print(fut.groupby("item_id")["forecast"].sum().round(1).head(5).to_string())

# --- 3. A short-history item gets the simple fallback ---
short = raw[raw["item_id"] == raw["item_id"].iloc[0]].head(40).copy()
short["item_id"] = "SHORT_ITEM"
v2 = validate_sales(pd.concat([raw, short], ignore_index=True))
fut2 = forecast_next_days(v2.data, v2.items, model, horizon=7)
s = fut2[fut2["item_id"] == "SHORT_ITEM"]
expected = float(short["units_sold"].tail(28).mean())
check(len(s) == 7 and (s["method"] == "fallback").all(), "short item is forecast with the fallback method")
check(((s["forecast"] - expected).abs() < 1e-9).all(), f"fallback equals its recent 28-day average ({expected:.2f})")

print("\nALL CHECKS PASSED")