"""Step 10 checks. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\check_step10.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

from stockwise import config
from stockwise.detect import detect
from stockwise.features import build_features
from stockwise.forecast import rolling_forecast
from stockwise.schema import validate_sales
from stockwise.simulate import simulate_shrinkage


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        raise SystemExit(1)


def note(condition, message):
    print(("PASS  " if condition else "NOTE  ") + message)


# --- 0. A tiny synthetic test: one clear spike must be found, normal noise must not ---
rng = np.random.default_rng(1)
n = 80
toy = pd.DataFrame({"item_id": "A", "date": pd.date_range("2026-01-01", periods=n),
                    "expected": 5.0})
toy["actual_drop"] = 5.0 + rng.integers(-1, 2, size=n)
toy.loc[60, "actual_drop"] += 20
d = detect(toy)
check(d.loc[60, "flag"] == 1 and d.loc[60, "severity"] == "High", "a +20 unit spike is flagged as High")
check(d["flag"].sum() == 1, "ordinary +/-1 noise raises no false alarms")
check(d["z"].iloc[:28].isna().all() and d["z"].iloc[28:].notna().all(), "first 28 days are not scored, the rest are")

# --- 1. Real data: forecasts for the last 168 days, then simulated shrinkage ---
raw = pd.read_csv(config.DATA_DIR / "sample_sales_upload.csv")
v = validate_sales(raw)
feat = build_features(v.data)
res = rolling_forecast(feat)
sim = simulate_shrinkage(res)
check(len(sim) == 16800 and int(sim["anomaly_label"].sum()) == 1200, "16,800 rows with 1,200 simulated anomalies (7.14%)")

cut = int(sim["day_num"].max()) - 84


def evaluate(det):
    t = det[(det["day_num"] > cut) & det["z"].notna()]
    y, f = t["anomaly_label"], t["flag"]
    return {"rows": len(t), "anomalies": int(y.sum()), "flags": int(f.sum()),
            "false_alarms": int(((f == 1) & (y == 0)).sum()),
            "precision": precision_score(y, f, zero_division=0), "recall": recall_score(y, f),
            "F1": f1_score(y, f), "PR-AUC": average_precision_score(y, t["z"])}


sim["expected"] = sim["pred"]
det_f = detect(sim, mode="forecast")
sim["expected"] = sim["units_sold"]
det_r = detect(sim, mode="recorded_sales")

table = pd.DataFrame({"forecast mode": evaluate(det_f), "recorded-sales mode": evaluate(det_r)}).T
print("\nTest half (last 84 days), z >= " + str(config.Z_CUT) + ":")
print(table.round(3).to_string() + "\n")

ef, er = evaluate(det_f), evaluate(det_r)
note(ef["rows"] == 8400 and ef["anomalies"] == 606, "same test half as Colab (8,400 rows, 606 anomalies)")
check(er["precision"] >= 0.99 and er["recall"] >= 0.90, "recorded-sales mode is near-perfect (the ceiling)")
check(ef["precision"] >= 0.90 and ef["recall"] >= 0.80, "forecast mode catches most losses with few false alarms")
note(abs(ef["F1"] - 0.907) < 0.03, "forecast-mode F1 is close to Colab's 0.907")

# --- 2. Severity bands ---
t = det_f[(det_f["day_num"] > cut) & (det_f["flag"] == 1)]
sev = (t.groupby("severity")
        .agg(flags=("anomaly_label", "size"), share_real=("anomaly_label", "mean"),
             avg_est_missing=("est_missing_units", "mean"))
        .round(2).reindex(["Low", "Medium", "High"]))
print("\nBy severity (forecast mode):")
print(sev.to_string() + "\n")
check(sev.loc["High", "share_real"] >= 0.95, "High-severity flags are almost always real")
tp = t[t["anomaly_label"] == 1]
mae = (tp["est_missing_units"] - tp["injected_loss"]).abs().mean()
note(mae < 3, f"estimated units missing is within {mae:.2f} units of the true loss on average")

# --- 3. Sensitivity setting ---
loose = detect(sim.assign(expected=sim["pred"]), z_cut=2.5)
strict = detect(sim.assign(expected=sim["pred"]), z_cut=5.0)
check(loose["flag"].sum() > det_f["flag"].sum() > strict["flag"].sum(), "lower cutoff flags more, higher cutoff flags fewer")
check(det_f["z"].isna().sum() == 28 * 100, "the first 28 days of each of the 100 items are not scored")

print("\nALL CHECKS PASSED")