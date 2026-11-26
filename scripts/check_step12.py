"""Step 12 checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step12.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

from stockwise import config, db
from stockwise.counts import drops_from_counts, run_detection
from stockwise.simulate import simulate_counts, simulate_shrinkage


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


def note(condition, message):
    print(("PASS  " if condition else "NOTE  ") + message)


if not db.DB_PATH.exists() or db.DB_PATH.stat().st_size < 1_000_000:
    raise SystemExit("Run scripts\\build_sample_db.py first (data\\stockwise.db is missing).")

TMP = config.DATA_DIR / "test_stockwise.db"
shutil.copy(db.DB_PATH, TMP)                     # work on a copy, the real database is untouched

# --- 1. Simulated counts and deliveries, saved like a store would record them ---
sales = db.read_table("sales", TMP)
exp = db.read_table("expected_demand", TMP)
frame = sales.merge(exp[["item_id", "date"]], on=["item_id", "date"], how="inner")
sim = simulate_shrinkage(frame)
counts, deliveries = simulate_counts(sim)
check(len(frame) == 16800 and int(sim["anomaly_label"].sum()) == 1200, "16,800 days with 1,200 simulated anomalies")
check(len(counts) == 16800 + 100, f"{len(counts):,} counts (one per day plus a baseline per item), {len(deliveries):,} deliveries")
note(counts["counted_stock"].min() >= 0, f"lowest simulated count is {counts['counted_stock'].min():.0f} (never below zero)")
db.upsert("stock_counts", counts, TMP)
db.upsert("deliveries", deliveries, TMP)

# --- 2. Counts and deliveries give back exactly the simulated drops ---
drops = drops_from_counts(db.read_table("stock_counts", TMP), db.read_table("deliveries", TMP))
m = drops.merge(sim[["item_id", "date", "actual_drop"]], on=["item_id", "date"], suffixes=("_counts", "_sim"))
check(len(drops) == 16800 and len(m) == 16800 and (m["actual_drop_counts"] - m["actual_drop_sim"]).abs().max() < 1e-6,
      "stock drops rebuilt from counts and deliveries match the simulation exactly")

# --- 3. Detection from counts, evaluated against the hidden simulated labels ---
labels = sim[["item_id", "date", "anomaly_label", "injected_loss"]]


def evaluate(det):
    d = det.merge(labels, on=["item_id", "date"], how="inner")
    cut = d["date"].max() - pd.Timedelta(days=84)
    t = d[(d["date"] > cut) & d["z"].notna()]
    y, f = t["anomaly_label"], t["flag"]
    return t, {"rows": len(t), "anomalies": int(y.sum()), "flags": int(f.sum()),
               "false_alarms": int(((f == 1) & (y == 0)).sum()),
               "precision": precision_score(y, f, zero_division=0), "recall": recall_score(y, f),
               "F1": f1_score(y, f), "PR-AUC": average_precision_score(y, t["z"])}


det_f = run_detection("forecast", path=TMP)
det_r = run_detection("recorded_sales", path=TMP, save=False)
t_f, ef = evaluate(det_f)
_, er = evaluate(det_r)
print("\nTest half (last 84 days), flags computed from the stored counts:")
print(pd.DataFrame({"forecast mode": ef, "recorded-sales mode": er}).T.round(3).to_string() + "\n")
note(ef["rows"] == 8400 and ef["anomalies"] == 606, "same test half as before (8,400 rows, 606 anomalies)")
check(ef["precision"] >= 0.90 and ef["recall"] >= 0.80, "forecast mode: most losses found, few false alarms")
check(er["precision"] >= 0.99 and er["recall"] >= 0.90, "recorded-sales mode reaches the ceiling")
note(ef["flags"] == 549, "forecast mode gives the same 549 flags as the direct computation in Step 10")

stored = db.read_table("detections", TMP)
check(len(stored) == len(det_f) and int(stored["flag"].sum()) == int(det_f["flag"].sum()),
      f"{len(stored):,} detection rows saved to the database ({int(stored['flag'].sum())} flagged)")

# --- 4. Missing counts are skipped, not guessed ---
item0 = counts["item_id"].iloc[0]
c0 = counts[counts["item_id"] == item0].sort_values("date")
gap_dates = c0["date"].iloc[50:53]
gapped = counts[~((counts["item_id"] == item0) & counts["date"].isin(gap_dates))]
d2 = drops_from_counts(gapped, deliveries)
check(len(d2) == 16800 - 4, "3 missing daily counts remove exactly 4 days of drops (the 3 days and the day after)")

# --- 5. The most urgent flags, as the app will show them ---
top = (t_f[t_f["flag"] == 1].sort_values("est_missing_units", ascending=False)
       .head(5)[["item_id", "date", "est_missing_units", "severity"]])
print("\nFive biggest flags:")
print(top.to_string(index=False))

TMP.unlink()
print("\nALL CHECKS PASSED")